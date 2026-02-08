import logging
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# INTEGRATION POINT 1: Import 'lab' router
from app.routers import scan, agent_chat, lab  
from app.config import settings

# Konfigurace Loggování
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicializace aplikace
app = FastAPI(
    title="RDM AI Scraper API",
    version="0.8.0",
    description="Sprint 05: Hybrid Intelligence & Agentic Orchestration"
)

# --- CORS KONFIGURACE ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrace Routerů
app.include_router(scan.router)
app.include_router(agent_chat.router)
# INTEGRATION POINT 2: Register '/lab' router
app.include_router(lab.router, prefix="/lab", tags=["Data Lab"])

@app.get("/")
async def root():
    return {
        "status": "online", 
        "message": "RDM AI Scraper Backend is running",
        "features": ["Vision Analysis", "Hybrid Agent", "Vector Search", "Data Lab"]
    }