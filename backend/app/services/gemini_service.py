import os
import time
import json
import logging
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from starlette.concurrency import run_in_threadpool
from app.schemas import ProductAnalysisResult
from app.config import settings

# Logger
logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        
        # DEFINICE ROTACE MODELŮ (Robustness Fix)
        # 1. 2.0 Flash - Rychlý, moderní (Primary)
        # 2. 2.5 Flash - Experimentální/Vylepšený (Secondary)
        # 3. 1.5 Flash - Stabilní fallback (Legacy)
        self.model_rotation = [
            "models/gemini-2.0-flash",
            "models/gemini-2.5-flash",
            "models/gemini-1.5-flash"
        ]

    def _resolve_and_sanitize(self, schema: dict, defs: dict = None) -> dict:
        """
        CRITICAL FIX for Gemini Protobuf/OpenAPI compatibility.
        1. Resolves $ref
        2. Flattens anyOf
        3. Removes forbidden keys (title, default, etc.)
        """
        if defs is None:
            defs = schema.get("$defs", {})

        if "$ref" in schema:
            ref_key = schema["$ref"].split("/")[-1]
            return self._resolve_and_sanitize(defs.get(ref_key, {}), defs)

        if "anyOf" in schema:
            # Zjednodušení: Bereme první variantu (často non-null typ)
            return self._resolve_and_sanitize(schema["anyOf"][0], defs)

        if schema.get("type") == "object":
            new_props = {}
            for k, v in schema.get("properties", {}).items():
                new_props[k] = self._resolve_and_sanitize(v, defs)
            schema["properties"] = new_props
            
            # Clean forbidden keys
            for key in ["title", "default", "additionalProperties", "$defs"]:
                schema.pop(key, None)

        elif schema.get("type") == "array":
            schema["items"] = self._resolve_and_sanitize(schema["items"], defs)
            schema.pop("title", None)

        # Final cleanup for primitives
        for key in ["title", "default", "format"]:
            schema.pop(key, None)

        return schema

    def _get_sanitized_schema(self) -> dict:
        """Extracts JSON Schema from Pydantic and sanitizes it for Gemini."""
        raw_schema = ProductAnalysisResult.model_json_schema()
        return self._resolve_and_sanitize(raw_schema)

    async def analyze_image(self, file_path: str, mime_type: str = "image/jpeg") -> ProductAnalysisResult:
        """
        Orchestrates the analysis with Model Rotation logic.
        """
        logger.info(f"Initiating Gemini analysis for {file_path}")
        
        # 1. Upload to Gemini File API (Blocking)
        gemini_file = await run_in_threadpool(
            genai.upload_file, 
            path=file_path, 
            mime_type=mime_type
        )
        
        # Wait for processing
        while gemini_file.state.name == "PROCESSING":
            await run_in_threadpool(time.sleep, 1)
            gemini_file = await run_in_threadpool(genai.get_file, gemini_file.name)
            
        if gemini_file.state.name == "FAILED":
            raise ValueError("Gemini File API processing failed.")

        sanitized_schema = self._get_sanitized_schema()
        
        generation_config = GenerationConfig(
            response_mime_type="application/json",
            response_schema=sanitized_schema
        )

        prompt = """
        Analyze this supplement product image. 
        Extract data strictly according to the schema.
        - For 'composition', include ALL active ingredients listed.
        - If values are missing, use null.
        - Translate text to Czech if in another language, but keep brand names original.
        """

        last_error = None

        # 2. ROTATION LOOP (Robustness logic)
        for model_name in self.model_rotation:
            logger.info(f"👉 Attempting analysis with model: {model_name}")
            try:
                model = genai.GenerativeModel(model_name)
                
                # CRITICAL: Pass generation_config as kwarg!
                response = await run_in_threadpool(
                    model.generate_content,
                    contents=[gemini_file, prompt],
                    generation_config=generation_config
                )
                
                # 3. Parse & Cleanup
                result_json = json.loads(response.text)
                await run_in_threadpool(gemini_file.delete)
                
                logger.info(f"✅ Success with model: {model_name}")
                return ProductAnalysisResult(**result_json)

            except Exception as e:
                logger.warning(f"⚠️ Model {model_name} failed. Error: {e}")
                last_error = e
                continue # Try next model
        
        # 4. Final Cleanup on Failure
        try:
            await run_in_threadpool(gemini_file.delete)
        except:
            pass
            
        logger.error("❌ CRITICAL: All models in rotation failed.")
        raise ValueError(f"Analysis failed across all models. Last error: {last_error}")