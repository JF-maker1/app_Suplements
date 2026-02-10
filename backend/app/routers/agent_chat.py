import logging
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

from app.services.orchestrator import OrchestratorService, OrchestratorResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Agentic Chat"])


# --- Models ---
# Input model remains compatible with Frontend
class ChatMessage(BaseModel):
    role: str  # "user" or "model"
    content: str


class ChatRequest(BaseModel):
    query: str
    history: List[ChatMessage] = []


# --- Service Initialization ---
# Global instance of the Orchestrator
orchestrator = OrchestratorService()


@router.post("/chat", response_model=OrchestratorResult)
async def agent_chat(request: ChatRequest):
    """
    Endpoint pro Hybridního Agenta (v08.0 Orchestrator).
    Deleguje logiku na OrchestratorService (ReAct Loop).

    Returns:
        OrchestratorResult: {
            type: "text" | "product_cards" | "data_table",
            content: str,
            payload: Any,
            metadata: Dict
        }
    """
    logger.info(f"Agent Request: {request.query}")

    try:
        # 1. Prepare Context
        # Convert Pydantic models to dicts for the service layer
        history_dicts = [m.model_dump() for m in request.history]

        # 2. Delegate to Orchestrator (The Brain)
        result = await orchestrator.process_user_query(
            query=request.query, history=history_dicts
        )

        return result

    except Exception as e:
        logger.error(f"Agent Router Critical Error: {e}")
        # Fail-Safe Response
        return OrchestratorResult(
            type="text",
            content="Omlouvám se, došlo k interní chybě serveru při zpracování dotazu.",
            metadata={"error": str(e)},
        )
