from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Carga las variables de entorno desde el archivo .env."""

    DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_JWKS_URL: str
    SUPABASE_KEY: str
    SUPABASE_STORAGE_BUCKET: str = "flyers"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
