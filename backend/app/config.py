import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App
    APP_NAME: str = "RDM Supplement Analyzer API"
    ENV: str = "dev"
    
    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_BUCKET: str = "raw-scans"
    
    # Google
    GOOGLE_API_KEY: str

    class Config:
        env_file = ".env"

settings = Settings()