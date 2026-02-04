import logging
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import scan
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
    description="Sprint 04: Intelligence & Optimization"
)

# --- CORS KONFIGURACE (CRITICAL FIX) ---
# Povolujeme všechny originy (*), aby Frontend mohl volat Backend
# z jakékoli IP adresy (localhost, 192.168.x.x, atd.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Povolit vše pro vývoj
    allow_credentials=True,
    allow_methods=["*"],  # Povolit GET, POST, PATCH, OPTIONS...
    allow_headers=["*"],
)

# Registrace Routerů
app.include_router(scan.router)

@app.get("/")
async def root():
    return {"status": "online", "message": "RDM AI Scraper Backend is running"}