import re
import json
import logging
import random
import asyncio
from typing import Dict, Any, List, Optional
import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from app.config import settings
from app.services.db import SupabaseService

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. SECURITY VALIDATOR (TR-01)
# ==============================================================================
class SecurityValidator:
    FORBIDDEN_KEYWORDS = [
        "DROP", "DELETE", "INSERT", "UPDATE", "ALTER", 
        "GRANT", "REVOKE", "TRUNCATE", "EXEC", "EXECUTE", 
        "CREATE", "REPLACE", "function", "procedure"
    ]

    @staticmethod
    def is_safe_sql(query: str) -> bool:
        if not query: return False
        q_norm = query.strip()
        q_upper = q_norm.upper()
        
        if not q_upper.startswith("SELECT"):
            logger.warning("SQL Security: Query does not start with SELECT.")
            return False
            
        if ";" in q_norm:
            logger.warning("SQL Security: Query contains semicolon.")
            return False
            
        for keyword in SecurityValidator.FORBIDDEN_KEYWORDS:
            if re.search(fr"\b{keyword}\b", q_upper):
                logger.warning(f"SQL Security: Forbidden keyword detected: {keyword}")
                return False
        return True

# ==============================================================================
# 2. SQL SERVICE (ROBUST)
# ==============================================================================
class SqlService:
    def __init__(self):
        self.db = SupabaseService()
        self._init_gemini()
        
    def _init_gemini(self):
        self.api_keys = []
        if settings.GOOGLE_API_KEY: self.api_keys.append(settings.GOOGLE_API_KEY)
        if getattr(settings, 'GOOGLE_API_KEY_2', None): self.api_keys.append(settings.GOOGLE_API_KEY_2)
        if getattr(settings, 'GOOGLE_API_KEY_3', None): self.api_keys.append(settings.GOOGLE_API_KEY_3)
        if getattr(settings, 'GOOGLE_API_KEY_4', None): self.api_keys.append(settings.GOOGLE_API_KEY_4)
        if getattr(settings, 'GOOGLE_API_KEY_5', None): self.api_keys.append(settings.GOOGLE_API_KEY_5)
        
        # Model Rotation for SQL Gen
        self.model_rotation = [
            "models/gemini-1.5-flash-latest",
            "models/gemini-flash-latest",
            "models/gemini-1.5-pro-latest",
            "models/gemini-pro"
        ]

    def _get_random_key(self):
        if not self.api_keys: raise ValueError("No API Keys available.")
        return random.choice(self.api_keys)

    async def generate_sql(self, user_query: str) -> str:
        prompt = f"""
        You are a Postgres SQL Expert. 
        Convert the user question into a SQL query for the table `ai_analytics_view`.
        Table Schema: product_name, brand, price, currency, category, calories, protein, carbs, fat, created_at.
        Rules: Return ONLY raw SQL. No markdown. Use ILIKE.
        User Question: "{user_query}"
        SQL:
        """
        
        max_retries = max(len(self.api_keys) * 2, 4)
        last_error = None

        for attempt in range(max_retries):
            current_key = self._get_random_key()
            
            # Select Model (Round Robin)
            current_model = self.model_rotation[attempt % len(self.model_rotation)]

            try:
                genai.configure(api_key=current_key)
                model = genai.GenerativeModel(current_model)
                
                response = await model.generate_content_async(prompt)
                sql = response.text.strip().replace("```sql", "").replace("```", "").strip()
                if sql:
                    return sql
            except Exception as e:
                last_error = e
                await asyncio.sleep(0.5)

        logger.error(f"SqlService Generation Error: {last_error}")
        raise last_error

    async def execute_sql(self, sql_query: str) -> List[Dict[str, Any]]:
        if not SecurityValidator.is_safe_sql(sql_query):
            raise ValueError("Security Violation: Unsafe SQL detected.")
        try:
            # VOLÁNÍ RPC FUNKCE VYTVOŘENÉ V KROKU 2
            response = self.db.client.rpc("exec_sql", {"query": sql_query}).execute()
            return response.data
        except Exception as e:
            logger.error(f"SQL Execution Failed: {e}")
            raise e

# ==============================================================================
# 3. REPORT SERVICE
# ==============================================================================
class ReportService:
    def __init__(self):
        self.db = SupabaseService()
        
    def get_monthly_spend(self) -> List[Dict[str, Any]]:
        try:
            return self.db.client.table("view_monthly_spend").select("*").execute().data
        except Exception as e:
            logger.error(f"ReportService Error: {e}")
            return []

    def get_category_distribution(self) -> List[Dict[str, Any]]:
        try:
            return self.db.client.table("view_category_distribution").select("*").execute().data
        except Exception as e:
            logger.error(f"ReportService Error: {e}")
            return []

# ==============================================================================
# 4. INTENT SERVICE (HARDENED PROMPT)
# ==============================================================================
class IntentService:
    def __init__(self):
        self.api_keys = []
        if settings.GOOGLE_API_KEY: self.api_keys.append(settings.GOOGLE_API_KEY)
        if getattr(settings, 'GOOGLE_API_KEY_2', None): self.api_keys.append(settings.GOOGLE_API_KEY_2)
        if getattr(settings, 'GOOGLE_API_KEY_3', None): self.api_keys.append(settings.GOOGLE_API_KEY_3)
        if getattr(settings, 'GOOGLE_API_KEY_4', None): self.api_keys.append(settings.GOOGLE_API_KEY_4)
        if getattr(settings, 'GOOGLE_API_KEY_5', None): self.api_keys.append(settings.GOOGLE_API_KEY_5)
        
        self.model_rotation = [
            "models/gemini-1.5-flash-latest",
            "models/gemini-flash-latest",
            "models/gemini-2.0-flash"
        ]

    async def classify_intent(self, user_query: str) -> Dict[str, str]:
        # --- PROMPT ENGINEERING: LOCALIZED FEW-SHOT ---
        # Oprava: Přidány explicitní české příklady a "negativní" pravidla pro General Chat.
        prompt = f"""
        You are the Router for a Supplement E-shop. Your job is to classify user queries into 3 categories.
        
        CATEGORIES:
        
        1. SQL_ANALYSIS (Structured Data):
           - Target: Hard facts about Price, Quantity, Brand, Composition stats, Sorting.
           - Keywords: "Cena", "Kolik stojí", "Nejlevnější", "Srovnej", "Vypiš", "Seznam", "Nejvíc".
           - Examples: 
             "Jaká je cena SuperKick?" -> SQL_ANALYSIS
             "Najdi nejlevnější protein" -> SQL_ANALYSIS
             "Který produkt má nejvíce hořčíku?" -> SQL_ANALYSIS
           
        2. VECTOR_SEARCH (Semantic/Needs):
           - Target: Vague requests, Health Goals, Symptoms, Recommendations, Finding products by description.
           - Keywords: "Na spaní", "Únava", "Bolest", "Energie", "Doporuč", "Něco na...", "Hledám", "Vitamín".
           - Examples: 
             "Něco na spaní" -> VECTOR_SEARCH
             "Jsem stále unavený" -> VECTOR_SEARCH
             "Co je dobré na regeneraci po běhu?" -> VECTOR_SEARCH
             "Vitamín C" -> VECTOR_SEARCH
             "Chci produkt s melatoninem" -> VECTOR_SEARCH
           
        3. GENERAL_CHAT (Chit-Chat):
           - Target: Greetings, Identity questions, Completely off-topic (Weather, Politics).
           - RULE: If the user asks for health advice ("How to sleep better?"), treat it as VECTOR_SEARCH (to find products), NOT General Chat.
           - Examples: 
             "Ahoj" -> GENERAL_CHAT
             "Jak se máš?" -> GENERAL_CHAT
             "Napiš báseň" -> GENERAL_CHAT
             "Díky" -> GENERAL_CHAT

        QUERY: "{user_query}"
        
        OUTPUT FORMAT: STRICT JSON only.
        {{ "intent": "CATEGORY" }}
        """
        
        if not self.api_keys: return {"intent": "GENERAL_CHAT"}
        
        max_retries = max(len(self.api_keys) * 2, 4)

        for attempt in range(max_retries):
            current_key = random.choice(self.api_keys)
            current_model = self.model_rotation[attempt % len(self.model_rotation)]

            try:
                genai.configure(api_key=current_key)
                model = genai.GenerativeModel(current_model)
                
                response = await model.generate_content_async(
                    prompt, 
                    generation_config=GenerationConfig(response_mime_type="application/json")
                )
                
                return json.loads(response.text)
                
            except Exception as e:
                await asyncio.sleep(0.3)

        return {"intent": "GENERAL_CHAT"}