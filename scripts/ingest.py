"""Ingest Cricsheet JSON into the Stryk database.

    python scripts/ingest.py                      # all IPL matches found
    python scripts/ingest.py --dataset wpl        # another downloaded dataset
    python scripts/ingest.py --limit 50           # quick smoke import
    python scripts/ingest.py --seasons 2024 2025  # add seasons incrementally
    python scripts/ingest.py --reset              # drop and rebuild

The schema is migrated (Alembic) before importing, so an existing database is
upgraded in place rather than rebuilt.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.core.migrate import upgrade  # noqa: E402
from app.ingestion import providers  # noqa: E402
import app.models  # noqa: E402,F401  (register metadata)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", default="ipl",
                    help="Cricsheet dataset key, e.g. ipl, wpl, t20s (see app/catalog/sources.json)")
    ap.add_argument("--dir", default=None, help="Override the directory (default data/raw/<dataset>_json)")
    ap.add_argument("--provider", default="cricsheet")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--seasons", type=int, nargs="*", default=None)
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    directory = Path(args.dir) if args.dir else settings.raw_dir / f"{args.dataset}_json"
    if not directory.is_dir():
        print(f"no such directory: {directory}\nRun scripts/fetch_cricsheet.py first.")
        return 1

    settings.data_dir.joinpath("processed").mkdir(parents=True, exist_ok=True)
    if args.reset:
        Base.metadata.drop_all(engine)
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    print(f"schema at revision {upgrade()}")

    provider = providers.get(args.provider)
    with SessionLocal() as db:
        stats = provider.ingest(db, directory, dataset=args.dataset,
                                limit=args.limit, seasons=args.seasons)

    print(
        f"\nseen={stats.seen} ingested={stats.ingested} skipped={stats.skipped} "
        f"deliveries={stats.deliveries} warnings={len(stats.warnings)}"
    )
    for w in stats.warnings[:20]:
        print("  warn:", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
