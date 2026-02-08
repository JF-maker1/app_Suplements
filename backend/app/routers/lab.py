import logging
from typing import Dict, Any, Optional, List, Union
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

from app.services.orchestrator import OrchestratorService

logger = logging.getLogger(__name__)

router = APIRouter()

# --- Service Initialization ---
# We use the Orchestrator as the single source of truth now.
# This ensures the Lab sees exactly what the Chat Widget sees.
orchestrator = OrchestratorService()

# --- Models ---
class LabQuery(BaseModel):
    query: str

class LabResponse(BaseModel):
    # Mapping Orchestrator Result to Lab UI expectations
    intent: str
    generated_sql: Optional[str] = None
    results: Optional[Union[List[Dict[str, Any]], Dict[str, Any], str]] = None
    orchestrator_raw: Dict[str, Any] # Full debug dump for "Raw API Response" panel
    error: Optional[str] = None

# --- Endpoint ---
@router.post("/analyze", response_model=LabResponse)
async def analyze_query(payload: LabQuery = Body(...)):
    user_query = payload.query
    if not user_query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        # 1. Delegate to the Brain (Real Logic)
        # We pass empty history as Lab requests are typically atomic
        result = await orchestrator.process_user_query(user_query, history=[])
        
        # 2. Extract Metadata for Lab UI Backward Compatibility
        meta = result.metadata or {}
        
        # 3. Construct Response
        return LabResponse(
            intent=meta.get("intent", "UNKNOWN"),
            generated_sql=meta.get("sql"),
            # If payload exists (Table/Cards), use it. Otherwise use content (Text).
            results=result.payload if result.payload else result.content,
            orchestrator_raw=result.model_dump()
        )

    except Exception as e:
        logger.error(f"Lab Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))