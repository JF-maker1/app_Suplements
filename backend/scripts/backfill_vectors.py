import asyncio
import os
import sys
import logging
import time

# 1. PATH SETUP
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_root = os.path.dirname(current_dir)
sys.path.append(backend_root)

# 2. IMPORTS
from app.services.vector_service import VectorService
from app.services.db import SupabaseService

# 3. LOGGING
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - VEC_BACKFILL - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def run_vector_backfill():
    """
    Iterates through products without embeddings and generates them.
    """
    logger.info("🚀 Starting Vector Backfill Process (Cycle 7)")
    
    # Initialize Services
    try:
        vector_service = VectorService()
        db_service = SupabaseService()
    except Exception as e:
        logger.critical(f"❌ Service Init Failed: {e}")
        return

    BATCH_SIZE = 10
    SLEEP_DELAY = 2.0 # Respect Gemini Rate Limits
    
    total_processed = 0
    total_errors = 0

    while True:
        # A. Fetch Batch (Idempotence: Only fetch NULL embeddings)
        try:
            # Note: We filter for rows where 'embedding' IS NULL
            # Supabase-py 'is_' syntax: column, value
            response = db_service.client.table("scans")\
                .select("*")\
                .is_("embedding", "null")\
                .order("created_at", desc=True)\
                .limit(BATCH_SIZE)\
                .execute()
            
            batch = response.data
        except Exception as e:
            logger.critical(f"❌ DB Fetch Failed: {e}")
            break

        if not batch:
            logger.info("🏁 No more records to process. Backfill Complete.")
            break

        logger.info(f"📦 Processing batch of {len(batch)} records...")

        # B. Process Batch
        for item in batch:
            scan_id = item.get("id")
            full_name = item.get("full_name") or "Unknown Product"
            
            # Construct Rich Semantic Text
            # Combine Name + Brand + Description + Categories
            meta = item.get("extra_metadata", {}) or {}
            brand = meta.get("brand") or item.get("brand") or ""
            marketing = meta.get("marketing", {}) or {}
            description = marketing.get("description") or ""
            claims = ", ".join(marketing.get("claims", []))
            
            # Semantic Blob
            semantic_text = f"""
            Product: {full_name}
            Brand: {brand}
            Description: {description}
            Claims: {claims}
            """
            
            logger.info(f"   🔹 Embedding: {full_name}...")
            
            # Generate Vector
            embedding = await vector_service.generate_embedding(semantic_text)
            
            if embedding:
                # Save to DB
                try:
                    db_service.client.table("scans").update({
                        "embedding": embedding
                    }).eq("id", scan_id).execute()
                    total_processed += 1
                except Exception as e:
                    logger.error(f"   ❌ DB Update Failed for {scan_id}: {e}")
                    total_errors += 1
            else:
                logger.warning(f"   ⚠️ Embedding Generation Failed for {scan_id}")
                total_errors += 1

        # C. Rate Limit
        logger.info(f"⏳ Sleeping {SLEEP_DELAY}s...")
        time.sleep(SLEEP_DELAY)

    logger.info("="*40)
    logger.info(f"🏁 BACKFILL FINISHED.")
    logger.info(f"Total Processed: {total_processed}")
    logger.info(f"Total Errors: {total_errors}")
    logger.info("="*40)

if __name__ == "__main__":
    asyncio.run(run_vector_backfill())