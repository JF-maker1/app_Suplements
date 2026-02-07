import logging
import google.generativeai as genai
from typing import List, Optional
from app.config import settings

logger = logging.getLogger(__name__)

class VectorService:
    """
    Služba pro generování embeddings (vektorů).
    Kompatibilní s 'pgvector' (dimenze 768).
    """

    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        # Model 'text-embedding-004' generuje 768-dimenzionální vektory,
        # což přesně odpovídá naší SQL definici VECTOR(768).
        self.model_name = "models/text-embedding-004"

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Vygeneruje vektor pro daný text.
        Vrací list floatů (dimenze 768) nebo None při chybě.
        """
        if not text or len(text.strip()) == 0:
            return None

        try:
            # Volání Google Embeddings API
            result = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type="retrieval_document" # Optimalizace pro ukládání do DB
            )
            
            embedding = result.get('embedding')
            
            # Validace dimenze (Paranoia check)
            if embedding and len(embedding) != 768:
                logger.warning(f"VectorService: Generated embedding has wrong dimension: {len(embedding)}")
                return None
                
            return embedding

        except Exception as e:
            logger.error(f"VectorService: Failed to generate embedding: {e}")
            return None