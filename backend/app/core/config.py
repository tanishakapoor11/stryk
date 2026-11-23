from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Runtime configuration.

    `database_url` is any SQLAlchemy URL. SQLite is the zero-setup default for
    local development; point it at PostgreSQL for deployment. Nothing in the
    data-access layer is dialect specific.
    """

    model_config = SettingsConfigDict(env_prefix="STRYK_", env_file=".env", extra="ignore")

    database_url: str = f"sqlite:///{ROOT / 'data' / 'processed' / 'stryk.db'}"
    data_dir: Path = ROOT / "data"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    log_level: str = "INFO"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
