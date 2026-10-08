import os
from decimal import Decimal
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Identity ──────────────────────────────────────────────────────────────
    PROJECT_NAME: str = "TradeGuard API"
    APP_ENV: str = "development"
    # No default — must be set in .env (see .env.example). Pydantic fails fast.
    SECRET_KEY: str

    # ── Database ──────────────────────────────────────────────────────────────
    # Both URLs required; no default — fail clearly if missing.
    DATABASE_URL: str
    TEST_DATABASE_URL: str

    # ── Trading mode ──────────────────────────────────────────────────────────
    # SIMULATOR | ORGANIZER_SANDBOX | LIVE — never switch silently.
    TRADING_MODE: str = "SIMULATOR"

    # ── Gemini ────────────────────────────────────────────────────────────────
    # Never logged or returned to the client.
    GEMINI_API_KEY: str = ""

    # ── CORS — public frontend origins only ──────────────────────────────────
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",   # Vite default
        "http://localhost:3000",   # React / Next.js
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    # ── Risk limits (configurable, validated) ─────────────────────────────────
    # Maximum single-order quantity in integer instrument units (INV-17)
    MAX_ORDER_QUANTITY_UNITS: int = Field(default=10_000, ge=1)
    # Maximum single-order notional in INR (decimal string in env)
    MAX_ORDER_NOTIONAL_INR: Decimal = Field(default=Decimal("5000000"), ge=Decimal("1"))
    # Maximum single rule notional in INR
    MAX_RULE_NOTIONAL_INR: Decimal = Field(default=Decimal("1000000"), ge=Decimal("1"))

    # ── Quote freshness ────────────────────────────────────────────────────────
    # Maximum acceptable quote age in milliseconds before considered stale
    MAX_QUOTE_AGE_MS: int = Field(default=5_000, ge=100)
    # Maximum allowed drift in basis points before holding the action
    MAX_DRIFT_BPS: int = Field(default=50, ge=0)
    # Clock-skew tolerance in seconds (INV-18)
    CLOCK_SKEW_TOLERANCE_SECONDS: int = Field(default=5, ge=0)

    # ── Approval window ────────────────────────────────────────────────────────
    # How long a proposal approval challenge is valid (seconds)
    PROPOSAL_APPROVAL_TTL_SECONDS: int = Field(default=120, ge=10)

    # ── Worker ────────────────────────────────────────────────────────────────
    WORKER_POLL_INTERVAL_SECONDS: int = Field(default=2, ge=1)

    # ── Chat ──────────────────────────────────────────────────────────────────
    MAX_CHAT_TEXT_LENGTH: int = Field(default=2_000, ge=1)

    # ── Rate limiting ─────────────────────────────────────────────────────────
    APPROVAL_RATE_LIMIT_PER_MINUTE: int = Field(default=10, ge=1)

    @field_validator("TRADING_MODE")
    @classmethod
    def validate_trading_mode(cls, v: str) -> str:
        allowed = {"SIMULATOR", "ORGANIZER_SANDBOX", "LIVE"}
        if v not in allowed:
            raise ValueError(f"TRADING_MODE must be one of {allowed}; got {v!r}")
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if v == "development-secret-key-replace-in-production" and False:
            # Allow dev key in dev; production check done at runtime via APP_ENV
            pass
        if len(v) < 16:
            raise ValueError("SECRET_KEY must be at least 16 characters")
        return v

    model_config = SettingsConfigDict(
        # Resolve root .env: backend/app/core/ -> ../../.. -> project root
        env_file=os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    def safe_repr(self) -> dict:
        """Return a loggable config dict with secrets redacted."""
        return {
            "PROJECT_NAME": self.PROJECT_NAME,
            "APP_ENV": self.APP_ENV,
            "TRADING_MODE": self.TRADING_MODE,
            "MAX_ORDER_QUANTITY_UNITS": self.MAX_ORDER_QUANTITY_UNITS,
            "MAX_ORDER_NOTIONAL_INR": str(self.MAX_ORDER_NOTIONAL_INR),
            "MAX_QUOTE_AGE_MS": self.MAX_QUOTE_AGE_MS,
            "PROPOSAL_APPROVAL_TTL_SECONDS": self.PROPOSAL_APPROVAL_TTL_SECONDS,
            "SECRET_KEY": "***REDACTED***",
            "DATABASE_URL": "***REDACTED***",
            "TEST_DATABASE_URL": "***REDACTED***",
            "GEMINI_API_KEY": "***REDACTED***",
        }


settings = Settings()
