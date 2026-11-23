"""Bring the database schema up to date.

Every entry point that writes (scripts/ingest.py, scripts/migrate.py) calls
:func:`upgrade` instead of ``Base.metadata.create_all``. A database built by
the old create_all path has the pre-competition tables but no Alembic version
row; it is stamped at the baseline revision first so the upgrade adds only
what is missing and keeps every existing row.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.core.db import engine as default_engine

log = logging.getLogger("stryk.migrate")
BACKEND = Path(__file__).resolve().parents[2]
BASELINE = "0001"


def _config(connection) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    cfg.attributes["connection"] = connection
    return cfg


def upgrade(engine: Optional[Engine] = None, revision: str = "head") -> str:
    """Upgrade to ``revision``; returns the revision the database ended at."""
    engine = engine or default_engine
    with engine.connect() as conn:
        tables = set(inspect(conn).get_table_names())
        cfg = _config(conn)
        if "alembic_version" not in tables and "match" in tables:
            log.info("pre-migration database detected; stamping baseline %s", BASELINE)
            command.stamp(cfg, BASELINE)
        command.upgrade(cfg, revision)
        conn.commit()
        if conn.dialect.name == "sqlite":
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        return conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar()


def downgrade(revision: str, engine: Optional[Engine] = None) -> None:
    engine = engine or default_engine
    with engine.connect() as conn:
        command.downgrade(_config(conn), revision)
        conn.commit()
