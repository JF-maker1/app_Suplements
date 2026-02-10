import logging
import random
import asyncio
import google.generativeai as genai
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.services.data_access import IntentService, SqlService
from app.services.vector_service import VectorService

logger = logging.getLogger(__name__)

# --- UNIFIED RESPONSE MODEL ---


class OrchestratorResult(BaseModel):
    """
    Standardizovaný výstup pro Frontend (ChatWidget).
    Podporuje text, karty produktů (Vector) a tabulky (SQL).
    """

    type: str = Field(
        ..., description="Typ obsahu: 'text', 'product_cards', 'data_table'"
    )
    content: Optional[str] = Field(None, description="Textová odpověď pro uživatele")
    payload: Optional[Any] = Field(
        None, description="Strukturovaná data (List[Dict] nebo Dict)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        {}, description="Debug info: intent, latency, tool_used"
    )


# --- SERVICE DEFINITION ---


class OrchestratorService:
    def __init__(self):
        # 1. Initialize Sub-Agents
        self.intent_service = IntentService()
        self.sql_service = SqlService()
        self.vector_service = VectorService()

        # 2. Key Management for General Chat
        self.api_keys = []
        if settings.GOOGLE_API_KEY:
            self.api_keys.append(settings.GOOGLE_API_KEY)
        if getattr(settings, "GOOGLE_API_KEY_2", None):
            self.api_keys.append(settings.GOOGLE_API_KEY_2)
        if getattr(settings, "GOOGLE_API_KEY_3", None):
            self.api_keys.append(settings.GOOGLE_API_KEY_3)
        if getattr(settings, "GOOGLE_API_KEY_4", None):
            self.api_keys.append(settings.GOOGLE_API_KEY_4)
        if getattr(settings, "GOOGLE_API_KEY_5", None):
            self.api_keys.append(settings.GOOGLE_API_KEY_5)

        # 3. Model Rotation (Robust Pattern applied here too)
        # Prioritizes latest stable aliases to prevent 404 errors on specific versions
        self.chat_model_rotation = [
            "models/gemini-1.5-flash-latest",
            "models/gemini-flash-latest",
            "models/gemini-2.0-flash",
            "models/gemini-1.5-pro-latest",
        ]

    async def process_user_query(
        self, query: str, history: List[Dict[str, str]] = []
    ) -> OrchestratorResult:
        """
        Main ReAct Loop:
        1. Classify Intent
        2. Route to specialized Agent
        3. Synthesize Result
        4. Fallback if needed
        """
        if not query:
            return OrchestratorResult(
                type="text", content="Omlouvám se, ale neslyšel jsem otázku."
            )

        # KROK 1: Klasifikace Záměru (Robust Intent Service handles retries internally)
        try:
            intent_result = await self.intent_service.classify_intent(query)
            intent = intent_result.get("intent", "GENERAL_CHAT")
            logger.info(f"🧠 Orchestrator Intent: {intent} | Query: {query}")
        except Exception as e:
            logger.error(f"Intent Classification Failed: {e}")
            intent = "GENERAL_CHAT"

        # KROK 2: Routing (The Brain)

        # --- A. SEMANTIC SEARCH (VECTOR) ---
        if intent == "VECTOR_SEARCH":
            return await self._handle_vector_search(query, intent)

        # --- B. DATA ANALYSIS (SQL) ---
        elif intent == "SQL_ANALYSIS":
            return await self._handle_sql_analysis(query, intent)

        # --- C. GENERAL CONVERSATION ---
        else:
            return await self._handle_general_chat(query, history, intent)

    # --- HANDLERS ---

    async def _handle_vector_search(
        self, query: str, intent: str
    ) -> OrchestratorResult:
        """Executes Semantic Search -> Returns Product Cards"""
        try:
            # Voláme robustní VectorService (již implementováno)
            products = await self.vector_service.search_vectors(
                query, limit=5, threshold=0.4
            )

            if not products:
                logger.info(
                    "Vector Search returned empty. Falling back to General Chat."
                )
                return await self._handle_general_chat(
                    query,
                    [],
                    intent,
                    system_prefix="Uživatel hledal produkt, ale v databázi jsem nic nenašel. Omluv se a nabídni pomoc.",
                )

            # Format response
            return OrchestratorResult(
                type="product_cards",
                content=f"Našel jsem {len(products)} produktů, které by tě mohly zajímat:",
                payload=products,
                metadata={"intent": intent, "source": "vector_db"},
            )
        except Exception as e:
            logger.error(f"Vector Handler Error: {e}")
            return await self._handle_general_chat(
                query, [], intent, system_prefix="Došlo k chybě při vyhledávání."
            )

    async def _handle_sql_analysis(self, query: str, intent: str) -> OrchestratorResult:
        """Generates & Executes SQL -> Returns Data Table"""
        try:
            # 1. Generate SQL (Robust SQL Service handles retries internally)
            sql_query = await self.sql_service.generate_sql(query)
            if not sql_query:
                raise ValueError("Failed to generate SQL")

            # 2. Execute SQL
            data = await self.sql_service.execute_sql(sql_query)

            if not data:
                return OrchestratorResult(
                    type="text",
                    content="Pro tento dotaz nemám v databázi žádná data.",
                    metadata={"intent": intent, "sql": sql_query},
                )

            # Format response
            return OrchestratorResult(
                type="data_table",
                content="Zde je přehled dat z databáze:",
                payload=data,
                metadata={"intent": intent, "sql": sql_query},
            )

        except Exception as e:
            logger.error(f"SQL Handler Error: {e}")
            return await self._handle_general_chat(
                query,
                [],
                intent,
                system_prefix="Pokusil jsem se vytáhnout data z databáze, ale dotaz byl příliš složitý. Odpověz obecně.",
            )

    async def _handle_general_chat(
        self,
        query: str,
        history: List[Dict[str, str]],
        intent: str,
        system_prefix: str = "",
    ) -> OrchestratorResult:
        """Standard LLM Conversation with Key & Model Rotation"""

        if not self.api_keys:
            return OrchestratorResult(
                type="text",
                content="Omlouvám se, nemám spojení s AI (API Keys missing).",
            )

        # Construct Prompt
        short_history = history[-5:] if history else []

        system_prompt = f"""
        Jsi RDM Asistent, expert na doplňky stravy.
        Odpovídej stručně, česky a k věci.
        {system_prefix}
        """

        # --- ROBUST RETRY LOOP FOR CHAT ---
        max_retries = max(len(self.api_keys) * 2, 4)
        last_error = None

        for attempt in range(max_retries):
            # A. Select Key
            current_key = random.choice(self.api_keys)

            # B. Select Model (Round Robin)
            current_model = self.chat_model_rotation[
                attempt % len(self.chat_model_rotation)
            ]

            try:

                def _chat_generate():
                    genai.configure(api_key=current_key)
                    model = genai.GenerativeModel(
                        current_model, system_instruction=system_prompt
                    )

                    # Convert history
                    chat = model.start_chat(
                        history=[
                            {"role": m["role"], "parts": [m["content"]]}
                            for m in short_history
                            if m["role"] in ["user", "model"]
                        ]
                    )

                    response = chat.send_message(query)
                    return response.text

                text_response = await run_in_threadpool(_chat_generate)

                return OrchestratorResult(
                    type="text",
                    content=text_response,
                    metadata={"intent": intent, "model": current_model},
                )

            except Exception as e:
                # logger.warning(f"Chat Attempt {attempt+1} failed ({current_model}): {e}")
                last_error = e
                await asyncio.sleep(0.5 + (0.5 * attempt))

        logger.error(
            f"Chat Handler Critical Error: All attempts failed. Last: {last_error}"
        )
        return OrchestratorResult(
            type="text",
            content="Omlouvám se, momentálně nemohu odpovědět (Server Busy/Model Unavailable).",
            metadata={"error": str(last_error)},
        )
