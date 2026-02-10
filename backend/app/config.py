from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "RDM Supplement Analyzer API"
    ENV: str = "dev"

    # Supabase Config
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_BUCKET: str = "raw-scans"

    # Google Gemini Config (Primary)
    GOOGLE_API_KEY: str

    # Rotation Keys (Optional)
    # Pokud nejsou v .env, budou None a rotace je přeskočí
    GOOGLE_API_KEY_2: Optional[str] = None
    GOOGLE_API_KEY_3: Optional[str] = None

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignoruje neznámé proměnné v .env (pro bezpečnost)


settings = Settings()
