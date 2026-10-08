import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "TradeGuard API"
    APP_ENV: str = "development"
    SECRET_KEY: str = "development-secret-key-replace-in-production"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tradeguard"
    TRADING_MODE: str = "SIMULATOR"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",  # Vite default
        "http://localhost:3000",  # Next.js / React default
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    model_config = SettingsConfigDict(
        # Look for .env in the root directory
        env_file=os.path.join(os.path.dirname(__file__), "../../../../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

settings = Settings()
