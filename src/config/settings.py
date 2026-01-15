"""Environment configuration loader for application settings."""

import os
from dotenv import load_dotenv
from typing import Optional

# Load environment variables from /env/.env
env_path = os.path.join(os.path.dirname(__file__), "../../../env/.env")
load_dotenv(env_path)


class Settings:
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # JWT Authentication
    BETTER_AUTH_SECRET: str = os.getenv("BETTER_AUTH_SECRET", "")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRATION_HOURS: int = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

    # Application
    APP_NAME: str = "Phase 2 Todo Backend"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",  # Next.js frontend default port
        "http://127.0.0.1:3000",
        "https://frontend-todo-eight.vercel.app",
    ]

    # Cookie settings
    COOKIE_NAME: str = "token"
    COOKIE_MAX_AGE: int = 86400  # 24 hours in seconds
    COOKIE_SECURE: bool = False  # Must be False for localhost development
    COOKIE_HTTP_ONLY: bool = True
    COOKIE_SAME_SITE: str = "lax"  # "lax" allows cookies across localhost/127.0.0.1

    def validate(self) -> None:
        """Validate required settings are present."""
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable is required")

        if not self.BETTER_AUTH_SECRET:
            raise ValueError("BETTER_AUTH_SECRET environment variable is required")

        if len(self.BETTER_AUTH_SECRET) < 32:
            raise ValueError("BETTER_AUTH_SECRET must be at least 32 characters long")

    @property
    def database_url_async(self) -> str:
        """Get async-compatible database URL (postgresql+asyncpg://)."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("psql"):
            # Handle the psql format from env file
            return url.replace("psql 'postgresql://", "postgresql+asyncpg://").rstrip("'")
        return url


# Global settings instance
settings = Settings()

# Validate settings on import
try:
    settings.validate()
except ValueError as e:
    print(f"Configuration Error: {e}")
    raise
