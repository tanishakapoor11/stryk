from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]

# pydantic-settings reads .env into Settings only; it never touches os.environ.
# Libraries that resolve their own credentials - the Anthropic SDK reading
# ANTHROPIC_API_KEY, for one - look there and nowhere else, so a key written
# into .env would otherwise be loaded and then silently ignored. Both
# locations are tried because the API is usually started from backend/ and the
# scripts from the repository root. A real environment variable always wins.
for _env_file in (ROOT / ".env", ROOT / "backend" / ".env"):
    load_dotenv(_env_file, override=False)


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
    #: Competition used when a request does not name one. Keeps pre-existing
    #: URLs (all IPL) meaning what they always meant.
    default_competition: str = "ipl"
    #: Model behind /api/ask. The job is a fixed-schema extraction rather than
    #: a reasoning problem, so the cheapest current model is the default; set
    #: STRYK_ASK_MODEL to compare a larger one on the same questions.
    ask_model: str = "claude-haiku-5-5"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
