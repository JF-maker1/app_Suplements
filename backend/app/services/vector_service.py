import logging
import random
import asyncio
import google.generativeai as genai
from typing import List, Optional, Dict, Any
from starlette.concurrency import run_in_threadpool
from app.config import settings
from app.services.db import SupabaseService

logger = logging.getLogger(__name__)

class VectorService:
    """
    Služba pro generování embeddings a sémantické vyhledávání.
    PATCH 7-DIMENSION-UPGRADE: Používá 'models/gemini-embedding-001' (3072 dim)
    """

    def __init__(self):
        # 1. KEY SHARDING (Load Balancing)
        self.api_keys = []
        if settings.GOOGLE_API_KEY: self.api_keys.append(settings.GOOGLE_API_KEY)
        if getattr(settings, 'GOOGLE_API_KEY_2', None): self.api_keys.append(settings.GOOGLE_API_KEY_2)
        if getattr(settings, 'GOOGLE_API_KEY_3', None): self.api_keys.append(settings.GOOGLE_API_KEY_3)

        if not self.api_keys:
            logger.warning("VectorService: No API Keys found! Service will fail.")

        # 2. MODEL DEFINITION
        # Detected valid model for this environment.
        # Outputs 3072 dimensions, compatible with 'vector(3072)' in Postgres (IVFFlat).
        self.model_rotation = [
            "models/gemini-embedding-001"
        ]
        
        # 3. DB CONNECTION (Fail-Safe)
        try:
            self.db = SupabaseService()
        except Exception as e:
            logger.error(f"VectorService: DB Connection failed: {e}")
            self.db = None

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generates 3072-dim embedding with retry logic and key rotation.
        """
        if not text or len(text.strip()) == 0:
            return None

        # Max retries logic
        max_retries = max(len(self.api_keys) * 2, 4)
        last_error = None

        for attempt in range(max_retries):
            # A. Key Selection (Random Load Balancing)
            if not self.api_keys:
                break
            current_key = random.choice(self.api_keys)

            # B. Model Selection
            current_model = self.model_rotation[0] # Using the single confirmed model

            try:
                # C. Configure & Execute
                def _call_api():
                    genai.configure(api_key=current_key)
                    # Note: gemini-embedding-001 usually accepts 'task_type'
                    return genai.embed_content(
                        model=current_model,
                        content=text,
                        task_type="retrieval_document" 
                    )

                result = await run_in_threadpool(_call_api)
                embedding = result.get('embedding')
                
                # D. Validation (3072 Dimensions)
                if embedding and len(embedding) == 3072:
                    return embedding
                elif embedding:
                    logger.warning(f"⚠️ Dimension Mismatch: Got {len(embedding)}, expected 3072.")
                else:
                    logger.warning(f"⚠️ Empty embedding returned. Model: {current_model}")

            except Exception as e:
                last_error = e
                # Exponential Backoff for 429 errors
                if "429" in str(e):
                    await asyncio.sleep(1 * (attempt + 1))
                else:
                    await asyncio.sleep(0.5)

        logger.error(f"VectorService: All attempts failed. Last error: {last_error}")
        return None

    async def search_vectors(self, query_text: str, limit: int = 5, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        Semantic Search via Supabase RPC with robustness.
        """
        if not self.db:
            logger.error("VectorService: DB client unavailable.")
            return []

        try:
            # 1. Generate Query Vector
            vector = await self.generate_embedding(query_text)
            
            if not vector:
                return []

            # 2. Call RPC (match_documents)
            def _execute_rpc():
                return self.db.client.rpc(
                    'match_documents',
                    {
                        'query_embedding': vector,
                        'match_threshold': threshold,
                        'match_count': limit
                    }
                ).execute()

            response = await run_in_threadpool(_execute_rpc)

            results = response.data if response.data else []
            logger.info(f"Vector Search: Found {len(results)} matches for query '{query_text}'")
            return results

        except Exception as e:
            logger.error(f"Vector Search Critical Error: {e}")
            return []