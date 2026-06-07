"""Application configuration."""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_name: str = "PR Changelog Generator"
    debug: bool = False
    secret_key: str = os.urandom(32).hex()

    # Database
    database_url: str = "postgresql+asyncpg://localhost/pr_changelog"

    # GitHub App
    github_app_id: str = ""
    github_private_key: str = ""  # PEM content or path
    github_webhook_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""

    # AI
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-pro"

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro: str = ""
    stripe_price_team: str = ""

    # Email
    resend_api_key: str = ""
    resend_from_email: str = "changelog@yourapp.com"

    # App URL
    app_url: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
