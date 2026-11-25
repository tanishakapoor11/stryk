"""Re-file matches that the catalogue now identifies by event name.

    python scripts/relink.py [--dry-run]

Ingest skips matches it has already imported, so adding an event rule to
competitions.json does not move the matches that rule now claims: they stay
in whichever competition first took them, which for an international event is
the bilateral bucket its format falls in. The Asia Cup sat inside Men's ODIs
and Men's T20Is that way, and the men's T20 World Cup was missing its 2007-12
editions because Cricsheet calls them "ICC World Twenty20".

This re-resolves every match that carries an event name and moves the ones a
catalogue event rule claims, creating their seasons and stages as it goes.
Only event rules can match here - the source dataset a match came from is not
kept on the row - so a match no rule names is left exactly where it is.

Safe to run repeatedly: a match already in the right competition is skipped.
Re-run POST /api/admin/reload afterwards, or restart the API.
"""
from __future__ import annotations

import argparse
import collections
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select, text, update  # noqa: E402

from app import catalog  # noqa: E402
from app.catalog import MatchContext, normalise_gender  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.ingestion.linking import Linker, refresh_derived  # noqa: E402
from app.models import Competition, Match  # noqa: E402

log = logging.getLogger("stryk.relink")


def plan(db, linker=None):
    """(linker, moves) - the matches a catalogue event rule now claims elsewhere.

    Separated from applying them so the decision can be tested, and so
    --dry-run reports exactly what a real run would do.
    """
    linker = linker or Linker(db)
    slug_of = {c.id: c.slug for c in db.execute(select(Competition)).scalars()}
    moves = []
    rows = db.execute(
        select(Match.id, Match.event_name, Match.gender, Match.match_type,
               Match.season_label, Match.date, Match.stage, Match.competition_id)
    ).all()
    for r in rows:
        if not r.event_name:
            continue
        ctx = MatchContext(r.event_name, normalise_gender(r.gender), r.match_type, None)
        # Only event rules can fire: the dataset a match came from is not kept
        # on the row, so a match no rule names by event is left where it is.
        entry = catalog.resolve(ctx, linker.catalogue)
        if entry is None or linker.competitions[entry["slug"]].id == r.competition_id:
            continue
        moves.append((r, ctx, slug_of.get(r.competition_id, "?"), entry["slug"]))
    return linker, moves


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="report the moves, change nothing")
    args = ap.parse_args()
    logging.basicConfig(level="INFO", format="%(levelname)s %(name)s: %(message)s")

    with SessionLocal() as db:
        linker, moves = plan(db)
        counts: collections.Counter = collections.Counter()
        for r, ctx, src, dst in moves:
            counts[(src, dst)] += 1
            if args.dry_run:
                continue
            links = linker.link(ctx, r.season_label, r.date, r.stage, None)
            links.pop("_competition_type", None)
            db.execute(update(Match).where(Match.id == r.id).values(**links))

        total = len(moves)
        for (src, dst), n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"  {n:>5}  {src} -> {dst}")
        print(f"{total} match(es) re-filed" + (" (dry run)" if args.dry_run else ""))

        if args.dry_run or not total:
            return 0

        # Seasons, stages and the team/player season rows are all derived from
        # which competition a match belongs to, so they are rebuilt wholesale.
        refresh_derived(db)
        # A competition invented by ingest for an event the catalogue now owns
        # has nothing left in it.
        empty = db.execute(text("""
            DELETE FROM competition WHERE is_catalogued = 0
              AND NOT EXISTS (SELECT 1 FROM match m WHERE m.competition_id = competition.id)
            RETURNING slug
        """)).scalars().all()
        db.execute(text("""
            DELETE FROM season WHERE NOT EXISTS
              (SELECT 1 FROM match m WHERE m.season_id = season.id)
        """))
        db.commit()
        if empty:
            print(f"removed {len(empty)} now-empty uncatalogued competition(s)")
    print("done - run POST /api/admin/reload or restart the API")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
