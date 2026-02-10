import json
import logging
import asyncio
import random
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from starlette.concurrency import run_in_threadpool
from app.schemas import ProductAnalysisResult
from app.config import settings

# Logger
logger = logging.getLogger(__name__)


class GeminiService:
    def __init__(self):
        # 1. NAČTENÍ VŠECH DOSTUPNÝCH KLÍČŮ (Key Sharding)
        self.api_keys = []
        if settings.GOOGLE_API_KEY:
            self.api_keys.append(settings.GOOGLE_API_KEY)

        # Check optional keys from settings (requires config.py update or getattr safety)
        if getattr(settings, "GOOGLE_API_KEY_2", None):
            self.api_keys.append(settings.GOOGLE_API_KEY_2)
        if getattr(settings, "GOOGLE_API_KEY_3", None):
            self.api_keys.append(settings.GOOGLE_API_KEY_3)
        if getattr(settings, "GOOGLE_API_KEY_4", None):
            self.api_keys.append(settings.GOOGLE_API_KEY_4)
        if getattr(settings, "GOOGLE_API_KEY_5", None):
            self.api_keys.append(settings.GOOGLE_API_KEY_5)

        logger.info(
            f"GeminiService initialized with {len(self.api_keys)} API keys for rotation."
        )

        # 2. MODEL ROTATION (Success First -> Stability -> Fallback)
        self.model_rotation = [
            "models/gemini-flash-latest",  # Alias pro nejnovější stabilní
            "models/gemini-2.0-flash",  # Rychlý, moderní
            "models/gemini-1.5-flash-latest",  # Fallback stabilní
            "models/gemini-1.5-pro-latest",  # Silnější model (pomalejší, jiné limity)
        ]

    def _resolve_and_sanitize(self, schema: dict, defs: dict = None) -> dict:
        """
        Sanitizes Pydantic JSON Schema for Gemini API compatibility.
        Removes $defs, anyOf, and forbidden keys.
        """
        if defs is None:
            defs = schema.get("$defs", {})

        if "$ref" in schema:
            ref_key = schema["$ref"].split("/")[-1]
            return self._resolve_and_sanitize(defs.get(ref_key, {}), defs)

        if "anyOf" in schema:
            return self._resolve_and_sanitize(schema["anyOf"][0], defs)

        if schema.get("type") == "object":
            new_props = {}
            for k, v in schema.get("properties", {}).items():
                new_props[k] = self._resolve_and_sanitize(v, defs)
            schema["properties"] = new_props

            for key in ["title", "default", "additionalProperties", "$defs"]:
                schema.pop(key, None)

        elif schema.get("type") == "array":
            schema["items"] = self._resolve_and_sanitize(schema["items"], defs)
            schema.pop("title", None)

        for key in ["title", "default", "format"]:
            schema.pop(key, None)

        return schema

    def _get_sanitized_schema(self) -> dict:
        raw_schema = ProductAnalysisResult.model_json_schema()
        return self._resolve_and_sanitize(raw_schema)

    async def analyze_image(
        self, file_path: str, mime_type: str = "image/jpeg"
    ) -> ProductAnalysisResult:
        """
        Orchestrates the analysis with Atomic Key+Model Rotation.
        Re-uploads the file for each key attempt because files are scoped to the API Key.
        """
        logger.info(f"Initiating Gemini analysis loop for {file_path}")

        sanitized_schema = self._get_sanitized_schema()
        generation_config = GenerationConfig(
            response_mime_type="application/json", response_schema=sanitized_schema
        )

        prompt = """
        Analyze this supplement product image. 
        Extract data strictly according to the schema.
        - For 'composition', include ALL active ingredients listed.
        - If values are missing, use null.
        - Translate text to Czech if in another language, but keep brand names original.
        """

        last_error = None

        # Max retries = Number of keys * 2 (give each key a couple of chances with different models)
        # Or a fixed number to prevent infinite loops.
        max_retries = 4

        for attempt in range(max_retries):
            # A) Select Key (Random Load Balancing)
            if not self.api_keys:
                raise ValueError("No API keys configured.")

            current_key = random.choice(self.api_keys)

            # B) Select Model (Round Robin based on attempt)
            current_model = self.model_rotation[attempt % len(self.model_rotation)]

            gemini_file = None

            try:
                # logger.info(f"👉 Attempt {attempt+1}/{max_retries} | Model: {current_model} | Key: ...{current_key[-4:]}")

                # 1. CONFIGURE GLOBAL STATE FOR THIS ATTEMPT
                genai.configure(api_key=current_key)

                # 2. UPLOAD FILE (Atomic for this Key)
                # Musíme nahrát soubor znovu, protože File API je vázané na projekt/klíč.
                gemini_file = await run_in_threadpool(
                    genai.upload_file, path=file_path, mime_type=mime_type
                )

                # Wait for processing
                while gemini_file.state.name == "PROCESSING":
                    await asyncio.sleep(1)
                    gemini_file = await run_in_threadpool(
                        genai.get_file, gemini_file.name
                    )

                if gemini_file.state.name == "FAILED":
                    raise ValueError("Gemini File API processing failed state.")

                # 3. GENERATE
                model = genai.GenerativeModel(current_model)
                response = await run_in_threadpool(
                    model.generate_content,
                    contents=[gemini_file, prompt],
                    generation_config=generation_config,
                )

                # 4. CLEANUP & PARSE
                await run_in_threadpool(gemini_file.delete)
                result_json = json.loads(response.text)

                logger.info(f"✅ Analysis Success (Model: {current_model})")
                return ProductAnalysisResult(**result_json)

            except Exception as e:
                # logger.warning(f"⚠️ Attempt {attempt+1} failed: {e}")
                last_error = e

                # Clean up file if upload succeeded but generation failed
                if gemini_file:
                    try:
                        await run_in_threadpool(gemini_file.delete)
                    except Exception:
                        pass

                # Backoff before next retry
                await asyncio.sleep(2)
                continue

        logger.error(
            f"❌ CRITICAL: All analysis attempts failed. Last error: {last_error}"
        )
        raise ValueError(f"Analysis failed. Last error: {last_error}")
