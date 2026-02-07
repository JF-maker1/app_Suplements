import logging
import json
import asyncio
import random
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any
import google.generativeai as genai
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Agentic Chat"])

# --- Models ---

class ChatMessage(BaseModel):
    role: str # "user" or "model"
    content: str

class ChatRequest(BaseModel):
    query: str
    history: List[ChatMessage] = []

class AgentCommand(BaseModel):
    command: str = "EXECUTE_REPORT"
    report_id: str
    params: Optional[Dict[str, Any]] = {}

class AgentResponse(BaseModel):
    type: str = Field(..., description="'message' or 'command'")
    content: Optional[str] = None # For text responses
    payload: Optional[AgentCommand] = None # For command responses

# --- Configuration ---

# 1. DEFINICE DOSTUPNÝCH KLÍČŮ (Načítáme z configu)
API_KEYS = []
if settings.GOOGLE_API_KEY: API_KEYS.append(settings.GOOGLE_API_KEY)
if getattr(settings, 'GOOGLE_API_KEY_2', None): API_KEYS.append(settings.GOOGLE_API_KEY_2)
if getattr(settings, 'GOOGLE_API_KEY_3', None): API_KEYS.append(settings.GOOGLE_API_KEY_3)
if getattr(settings, 'GOOGLE_API_KEY_4', None): API_KEYS.append(settings.GOOGLE_API_KEY_4)
if getattr(settings, 'GOOGLE_API_KEY_5', None): API_KEYS.append(settings.GOOGLE_API_KEY_5)

logger.info(f"Agent Chat initialized with {len(API_KEYS)} API keys for rotation.")

# 2. ROTACE MODELŮ (Priorita: Stabilita pro Chat)
MODEL_ROTATION = [
    "models/gemini-1.5-flash",          # Nejrychlejší a nejstabilnější pro chat
    "models/gemini-flash-latest",       # Záloha
    "models/gemini-2.0-flash"           # Moderní (ale náchylný na limity)
]

# Definice dostupných nástrojů (Reports)
AVAILABLE_TOOLS_CONTEXT = """
AVAILABLE DATA REPORTS (SQL VIEWS):
1. ID: "report_magnesium_overview"
   - Description: Comparison table of all magnesium supplements. Columns: Name, Form, Dosage, Price.
   - Use when user asks for: "magnesium comparison", "list of magnesiums", "best magnesium", "srovnej hořčíky".

2. ID: "report_protein_overview"
   - Description: List of protein powders sorted by protein content/price.
   - Use when user asks for: "protein comparison", "cheapest protein", "srovnej proteiny".

INSTRUCTIONS:
1. TOOL USE: If the user query matches a Report, return strict JSON:
   {"command": "EXECUTE_REPORT", "report_id": "...", "params": {...}}

2. GENERAL CHAT: If the query is a general question, answer concisely in the user's language. Return strict JSON:
   {"message": "Your answer text here"}

3. FORMAT: Output MUST be a valid JSON Object {}. Do not output raw strings or lists.
"""

@router.post("/chat", response_model=AgentResponse)
async def agent_chat(request: ChatRequest):
    """
    Endpoint pro Hybridního Agenta s implementovanou ROTACÍ KLÍČŮ I MODELŮ.
    """
    
    # Příprava Promptu
    system_instruction = f"""
    You are an expert nutritional assistant and RDM App Operator.
    {AVAILABLE_TOOLS_CONTEXT}
    
    Current User Query: {request.query}
    """

    llm_output = None
    last_error = None
    
    # --- MULTI-KEY & MULTI-MODEL ROTATION LOOP ---
    max_retries = 3
    
    for attempt in range(max_retries):
        if not API_KEYS:
            logger.critical("No API keys available for Agent Chat!")
            break

        # A) Náhodný klíč (Load Balancing)
        current_key = random.choice(API_KEYS)
        
        # B) Model dle pořadí
        current_model = MODEL_ROTATION[attempt % len(MODEL_ROTATION)]
        
        try:
            # PŘEPNUTÍ KLÍČE (Konfigurace globálního klienta pro tento request)
            genai.configure(api_key=current_key)
            model = genai.GenerativeModel(current_model)
            
            # Volání API
            response = await model.generate_content_async(
                system_instruction,
                generation_config={"response_mime_type": "application/json"} 
            )
            
            llm_output = json.loads(response.text)
            
            # logger.info(f"Agent: Success (Model: {current_model})")
            break # Úspěch -> konec smyčky

        except Exception as e:
            # logger.warning(f"Agent: Attempt {attempt+1} failed ({current_model}): {e}")
            last_error = e
            # Kratičká pauza a zkusíme jiný klíč/model
            await asyncio.sleep(0.5)

    # --- VYHODNOCENÍ ---
    if llm_output is None:
        logger.error(f"Agent Chat CRITICAL: All attempts failed. Last error: {last_error}")
        return AgentResponse(
            type="message",
            content="Omlouvám se, server je momentálně vytížen. Zkuste to prosím za chvíli."
        )

    # --- ROUTING LOGIC ---
    try:
        if isinstance(llm_output, dict):
            if llm_output.get("command") == "EXECUTE_REPORT":
                return AgentResponse(
                    type="command",
                    payload=AgentCommand(
                        report_id=llm_output["report_id"],
                        params=llm_output.get("params", {})
                    ),
                    content="Generuji report..."
                )
            else:
                text_content = (
                    llm_output.get("message") or 
                    llm_output.get("answer") or 
                    str(llm_output)
                )
                return AgentResponse(type="message", content=text_content)
        
        elif isinstance(llm_output, list):
            return AgentResponse(type="message", content=" ".join([str(x) for x in llm_output]))
            
        else:
            return AgentResponse(type="message", content=str(llm_output))
            
    except Exception as e:
        logger.error(f"Agent Parsing Error: {e}")
        return AgentResponse(type="message", content="Došlo k chybě při zpracování odpovědi.")