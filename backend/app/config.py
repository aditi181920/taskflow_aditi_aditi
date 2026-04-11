"""
Application settings loaded from environment variables.

Uses pydantic-settings to validate and type-cast env vars at startup,
failing fast if any required variable is missing.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # PostgreSQL (async driver for app, sync driver for Alembic)
    DATABASE_URL: str
    DATABASE_URL_SYNC: str

    # JWT signing
    JWT_SECRET: str
    JWT_EXPIRY_HOURS: int = 24

    # bcrypt work factor — 12 is the spec minimum
    BCRYPT_COST: int = 12

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
