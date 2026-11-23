"""Upgrade the database schema to the latest revision, keeping all data.

    python scripts/migrate.py

Safe to run repeatedly. A database built before migrations existed is detected
and upgraded in place. Reload a running API afterwards:
    curl -X POST http://127.0.0.1:8000/api/admin/reload
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.core.migrate import upgrade  # noqa: E402

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings.data_dir.joinpath("processed").mkdir(parents=True, exist_ok=True)
    print(f"database at revision {upgrade()}")
