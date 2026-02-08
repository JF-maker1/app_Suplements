import sys
import os
import logging
import random
import time

# 1. PATH SETUP (Aligns with existing project structure)
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_root = os.path.dirname(current_dir)
sys.path.append(backend_root)

# 2. IMPORTS
try:
    from app.services.db import SupabaseService
    from app.config import settings
except ImportError as e:
    print(f"❌ CRITICAL IMPORT ERROR: {e}")
    print(f"PYTHONPATH: {sys.path}")
    sys.exit(1)

# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - BRIDGE - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_bridge_test():
    logger.info("🌉 STARTING RPC CONNECTION BRIDGE TEST")
    
    # 1. Initialize Service (Tests Config + Auth)
    try:
        db = SupabaseService()
        logger.info(f"✅ Supabase Service Initialized (URL: {settings.SUPABASE_URL})")
    except Exception as e:
        logger.critical(f"❌ Service Init Failed: {e}")
        return

    # 2. Generate Dummy Vector (768 Dimensions)
    # Using random floats to simulate a real embedding
    # Range -0.1 to 0.1 is standard for normalized embeddings
    logger.info("🎲 Generating 768-dim dummy vector...")
    dummy_vector = [random.uniform(-0.1, 0.1) for _ in range(768)]
    
    # 3. Call RPC Function
    logger.info("📡 Calling 'match_documents' RPC...")
    start_time = time.time()
    
    try:
        # Note: supabase-py .rpc() executes directly
        response = db.client.rpc(
            'match_documents', 
            {
                'query_embedding': dummy_vector,
                'match_threshold': 0.0, # Zero threshold to force matching if ANY vectors exist
                'match_count': 1
            }
        ).execute()
        
        duration = time.time() - start_time
        
        # 4. Analyze Response
        data = response.data
        logger.info(f"✅ RPC Call Successful (Time: {duration:.3f}s)")
        logger.info(f"📦 Payload Type: {type(data)}")
        
        if isinstance(data, list):
            logger.info(f"📄 Rows Returned: {len(data)}")
            if len(data) > 0:
                logger.info(f"🔍 First Match: {data[0]}")
            else:
                logger.warning("⚠️ No matches found. (Expected if DB is empty of vectors)")
        else:
            logger.warning(f"⚠️ Unexpected payload format: {data}")

    except Exception as e:
        logger.critical(f"❌ RPC CALL FAILED: {e}")
        logger.error("Hint: Check if 'init_vector_db.sql' was run in Supabase Editor.")
        sys.exit(1)

if __name__ == "__main__":
    run_bridge_test()