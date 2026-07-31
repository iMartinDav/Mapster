"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Mapster"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    # CORS
    FRONTEND_URL: str = "http://localhost:5173"
    CUSTOM_DOMAIN: str = ""

    # Database (Neon Postgres)
    DATABASE_URL: str = "postgresql://postgres@localhost:5432/mapster"
    DATABASE_URL_ASYNC: str = "postgresql+asyncpg://postgres@localhost:5432/mapster"

    # Job store / cache (Upstash Redis). Leave blank to fall back to in-memory jobs.
    UPSTASH_REDIS_REST_URL: str = ""
    UPSTASH_REDIS_REST_TOKEN: str = ""

    # Admin
    ADMIN_KEY: str = ""

    # Concurrency
    MAX_CONCURRENT_GENERATIONS: int = 1

    # Job TTL in seconds (default 30 minutes)
    JOB_TTL_SECONDS: int = 30 * 60

    model_config = {"env_file": ".env", "case_sensitive": True}

    @property
    def cors_origins(self) -> list[str]:
        origins = [self.FRONTEND_URL]
        if self.CUSTOM_DOMAIN:
            origins.append(self.CUSTOM_DOMAIN)
        if "localhost" in self.FRONTEND_URL:
            return ["*"]
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
