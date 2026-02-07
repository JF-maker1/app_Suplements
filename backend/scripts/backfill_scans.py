import asyncio
import os
import sys
import logging
from typing import List, Dict, Any

# 1. PATH SETUP (Aby šel skript spustit z backend/scripts/)
# Přidáme root složku 'backend' do PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_root = os.path.dirname(current_dir)
sys.path.append(backend_root)

# 2. IMPORTS (Až po úpravě cesty)
from app.services.db import SupabaseService
from app.services.etl_service import EtlService

# 3. LOGGING CONFIG
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - BACKFILL - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def run_backfill():
    """
    Hlavní smyčka pro "uzdravení" dat.
    Najde skeny bez 'derived_data' a spustí AI-ETL.
    """
    logger.info("🚀 Starting Data Backfill Process (Cycle 5)")
    
    db = SupabaseService()
    etl = EtlService()
    
    # Statistiky
    stats = {"processed": 0, "success": 0, "failed": 0, "skipped": 0}
    
    # 4. FETCH DATA (Simple query for NULL derived_data)
    # Poznámka: Supabase/Postgrest neumí jednoduše "IS NULL" přes python SDK filter syntax ve všech verzích,
    # ale 'is' operátor by měl fungovat. Pro jistotu načteme dávku a filtrujeme.
    try:
        # Načteme poslední skeny (limit 100 pro tento běh, lze pustit opakovaně)
        response = db.client.table("scans")\
            .select("*")\
            .is_("derived_data", "null")\
            .order("created_at", desc=True)\
            .limit(100)\
            .execute()
            
        scans = response.data
    except Exception as e:
        logger.critical(f"❌ Failed to fetch scans from DB: {e}")
        return

    total_count = len(scans)
    logger.info(f"🔍 Found {total_count} scans requiring ETL normalization.")
    
    if total_count == 0:
        logger.info("✅ No scans to process. Database is clean.")
        return

    # 5. PROCESSING LOOP (Sequential)
    for index, scan in enumerate(scans):
        scan_id = scan.get("id")
        full_name = scan.get("full_name")
        
        # Sestavíme "Raw Text" ze starých metadat pro AI
        # Zkombinujeme název, značku a složení, aby AI měla kontext.
        raw_metadata = scan.get("extra_metadata", {})
        
        # Safety check: Pokud nejsou metadata, nemáme co analyzovat
        if not raw_metadata:
            logger.warning(f"⚠️ Skipping {scan_id}: No extra_metadata found.")
            stats["skipped"] += 1
            continue

        # Konstrukce textu pro LLM
        composition = raw_metadata.get("composition", {})
        marketing = raw_metadata.get("marketing", {})
        
        # Převedeme JSON na string, AI si s tím poradí
        raw_text_payload = f"""
        Product: {full_name}
        Brand: {raw_metadata.get("brand")}
        Composition Data: {composition}
        Marketing Claims: {marketing}
        Description: {marketing.get("description")}
        """
        
        logger.info(f"Processing {index + 1}/{total_count}: {full_name} ({scan_id})")
        
        # CALL ETL SERVICE
        success = await etl.process_scan(scan_id, raw_text_payload)
        
        if success:
            logger.info(f"✅ Normalized.")
            stats["success"] += 1
        else:
            logger.error(f"❌ Failed.")
            stats["failed"] += 1
            
        # Rate Limiting (zvýšeno pro Free Tier)
        logger.info("⏳ Waiting 10s to respect API Quota...")
        await asyncio.sleep(10.0)

    # 6. SUMMARY
    logger.info("=" * 40)
    logger.info("🏁 BACKFILL COMPLETE")
    logger.info(f"Total: {total_count}")
    logger.info(f"Success: {stats['success']}")
    logger.info(f"Failed: {stats['failed']}")
    logger.info(f"Skipped: {stats['skipped']}")
    logger.info("=" * 40)

if __name__ == "__main__":
    # Asyncio entry point
    asyncio.run(run_backfill())