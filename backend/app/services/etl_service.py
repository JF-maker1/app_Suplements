import logging
import json
import asyncio
import random
from typing import Dict, Any
import google.generativeai as genai
from app.config import settings
from app.services.db import SupabaseService

logger = logging.getLogger(__name__)


class EtlService:
    """
    Služba pro 'AI-ETL' (Data Cleaning).
    Implementuje MULTI-KEY ROTATION (obcházení limitů projektu) + MODEL ROTATION.
    Loaduje klíče bezpečně z Environment Variables via config.py.
    """

    def __init__(self):
        self.db = SupabaseService()

        # 1. ROTACE KLÍČŮ (KEY SHARDING)
        # Načteme všechny dostupné klíče z konfigurace
        self.api_keys = []

        # Vždy přidáme hlavní klíč
        if settings.GOOGLE_API_KEY:
            self.api_keys.append(settings.GOOGLE_API_KEY)

        # Přidáme záložní klíče, pokud existují v .env (a config.py je načetl)
        if getattr(settings, "GOOGLE_API_KEY_2", None):
            self.api_keys.append(settings.GOOGLE_API_KEY_2)
        if getattr(settings, "GOOGLE_API_KEY_3", None):
            self.api_keys.append(settings.GOOGLE_API_KEY_3)
        if getattr(settings, "GOOGLE_API_KEY_4", None):
            self.api_keys.append(settings.GOOGLE_API_KEY_4)
        if getattr(settings, "GOOGLE_API_KEY_5", None):
            self.api_keys.append(settings.GOOGLE_API_KEY_5)

        logger.info(
            f"ETL Service initialized with {len(self.api_keys)} API keys for rotation."
        )

        # 2. MODEL ROTATION (SEŘAZENO DLE RELEVANCE A SPOLEHLIVOSTI)
        # Strategie: Success First -> Stability -> Fallback -> Experimental
        self.model_rotation = [
            "models/gemini-flash-latest",  # Priorita 1: Prokázaná funkčnost ve vašem prostředí
            "models/gemini-1.5-flash-latest",  # Priorita 2: Alternativní alias pro stabilní verzi
            "models/gemini-1.5-pro-latest",  # Priorita 3: 'Pro' verze (jiný bucket limitů, pomalejší, ale stabilní)
            "models/gemini-1.5-flash",  # Priorita 4: Hardcoded verze (může házet 404, ale jako záloha ok)
            "models/gemini-2.0-flash",  # Priorita 5: Experimentální (často hází 429 Quota Exceeded)
        ]

    async def process_scan(self, scan_id: str, raw_text: str) -> bool:
        """
        Spustí normalizaci dat a uloží výsledek do 'derived_data'.
        """
        logger.info(f"ETL: Starting process for scan {scan_id}")

        derived_data = None
        last_error = None

        # Pokusíme se o extrakci (max 3 pokusy s různými kombinacemi klíčů/modelů)
        max_retries = 3

        for attempt in range(max_retries):
            # A) Vybereme náhodný klíč (Load Balancing)
            # Pokud nemáme žádné klíče, nemůžeme pokračovat
            if not self.api_keys:
                logger.critical("No API keys available! Check .env and config.py")
                return False

            current_key = random.choice(self.api_keys)

            # B) Vybereme model (cyklicky nebo náhodně, zde cyklicky dle pokusu)
            current_model = self.model_rotation[attempt % len(self.model_rotation)]

            try:
                # logger.info(f"👉 ETL Attempt {attempt+1}/{max_retries} | Model: {current_model} | Key: ...{current_key[-4:]}")

                # REKONFIGURACE GLOBÁLNÍHO KLIENTA PRO TENTO POKUS
                # Toto je klíčové: přepneme identitu pro Google API
                genai.configure(api_key=current_key)

                derived_data = await self._generate_with_model(current_model, raw_text)

                if derived_data:
                    logger.info(f"✅ ETL Success (Model: {current_model})")
                    break

            except Exception as e:
                # logger.warning(f"⚠️ Attempt {attempt+1} failed: {e}")
                last_error = e
                # Pokud selhal klíč (429), zkusíme jiný. Krátká pauza stačí, pokud máme více klíčů.
                await asyncio.sleep(1)

        # Pokud se nepodařilo získat data ani po všech pokusech
        if not derived_data:
            logger.error(
                f"ETL: All attempts failed for {scan_id}. Last error: {last_error}"
            )
            return False

        # 2. Database Update (Soft-Fail Logic)
        try:
            self.db.update_scan_data(scan_id, {"derived_data": derived_data})
            logger.info(f"ETL: Data saved for {scan_id}")
            return True

        except Exception as e:
            logger.error(f"ETL: DB Validation Failed. Rolling back. Error: {e}")
            try:
                # Fallback: Uložit NULL, aby se proces nezasekl
                self.db.update_scan_data(scan_id, {"derived_data": None})
            except Exception:
                pass
            return False

    async def _generate_with_model(self, model_name: str, text: str) -> Dict[str, Any]:
        """
        Pomocná metoda pro volání konkrétního modelu.
        """
        model = genai.GenerativeModel(model_name)

        # --- HOTFIX: CZECH LANGUAGE ENFORCEMENT ---
        prompt = """
        You are a Data Engineer. Extract structured data from this supplement description.
        STRICT JSON OUTPUT REQUIRED.
        
        Input Text:
        {text}

        Required JSON Schema:
        {
          "normalized_ingredients": [
            {
              "name": "Standardized Name (string, IN CZECH LANGUAGE)",
              "amount_mg": 123 (int, or null),
              "category": "Mineral/Vitamin/Herb/Other (string)"
            }
          ],
          "health_flags": {
            "is_vegan": boolean,
            "sugar_free": boolean,
            "contains_allergens": ["list", "of", "strings", "IN CZECH LANGUAGE"]
          }
        }
        
        Rules:
        1. "normalized_ingredients" MUST be an array.
        2. TRANSLATE all ingredient names and allergens to CZECH (e.g., 'Milk' -> 'Mléko', 'Whey' -> 'Syrovátka').
        3. Do not invent data. If unknown, use null.
        """

        final_prompt = prompt.replace("{text}", text)

        response = await model.generate_content_async(
            final_prompt, generation_config={"response_mime_type": "application/json"}
        )

        return json.loads(response.text)
