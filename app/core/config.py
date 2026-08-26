from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Carga las variables de entorno desde el archivo .env / Railway."""

    DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_JWKS_URL: str
    SUPABASE_KEY: str
    SUPABASE_STORAGE_BUCKET: str = "flayers"

    # Orígenes CORS separados por coma. Ejemplo:
    # CORS_ORIGINS=http://localhost:5173,https://tu-frontend.vercel.app
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        return origins or ["http://localhost:5173"]

    @property
    def sqlalchemy_database_url(self) -> str:
        """Normaliza postgres:// → postgresql:// (compatibilidad de drivers)."""
        url = self.DATABASE_URL.strip()
        if url.startswith("postgres://"):
            return "postgresql://" + url[len("postgres://") :]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
