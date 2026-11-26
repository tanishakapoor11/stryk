"""List the exact filename the interface looks for, for every team.

    python scripts/team_logo_manifest.py                  # every team
    python scripts/team_logo_manifest.py --competition ipl --competition bbl
    python scripts/team_logo_manifest.py --missing        # only ones with no file yet
    python scripts/team_logo_manifest.py --csv > teams.csv

Nothing is bundled with this project and nothing is downloaded: cricket board
and franchise marks are not on Wikimedia Commons, because they are not freely
licensed, so there is no source to fetch them from. Supplying them is an
operator decision.

What this does is remove the guesswork from supplying them. Drop a file at the
name printed here into frontend/public/teams/ and it is used automatically,
with no code change and no restart beyond the next request:

    frontend/public/teams/chennai-super-kings.svg
    frontend/public/teams/india.svg
    frontend/public/teams/sydney-sixers.png

svg, png, webp, jpg and jpeg are all read, and a vector file wins over a
bitmap of the same name. A team with no file falls back to its national flag,
and then to the generated badge, so the interface never depends on artwork
existing. Men's and women's sides of the same nation share one file.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGO_DIR = ROOT / "frontend" / "public" / "teams"
EXTENSIONS = ("svg", "png", "webp", "jpg", "jpeg")
sys.path.insert(0, str(ROOT / "backend"))


def slug(name: str) -> str:
    """Mirror of teamSlug() in frontend/lib/photos.ts. Must stay in step."""
    decomposed = unicodedata.normalize("NFD", name.lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", stripped))


def existing() -> dict[str, str]:
    """Slug -> the file already supplying that team's artwork."""
    out: dict[str, str] = {}
    if not LOGO_DIR.is_dir():
        return out
    for path in sorted(LOGO_DIR.iterdir()):
        if path.suffix.lower().lstrip(".") in EXTENSIONS:
            out.setdefault(path.stem.lower(), path.name)
    return out


def teams(competitions: list[str]) -> list[tuple]:
    from sqlalchemy import text

    from app.core.db import engine

    where, params = "", {}
    if competitions:
        where = """
          AND t.id IN (SELECT ct.team_id FROM competition_team ct
                       JOIN competition c ON c.id = ct.competition_id
                       WHERE c.slug IN :slugs)"""
        params["slugs"] = tuple(competitions)
    sql = text(f"""
        SELECT t.name, t.gender, t.is_national_team,
               (SELECT c.name FROM competition c
                  JOIN competition_team ct ON ct.competition_id = c.id
                 WHERE ct.team_id = t.id
                 GROUP BY c.id ORDER BY COUNT(*) DESC LIMIT 1) AS main_competition,
               (SELECT COUNT(*) FROM competition_team ct WHERE ct.team_id = t.id) AS seasons
        FROM team t
        WHERE 1 = 1 {where}
        ORDER BY t.is_national_team DESC, seasons DESC, t.name
    """)
    if competitions:
        sql = sql.bindparams(__import__("sqlalchemy").bindparam("slugs", expanding=True))
    with engine.connect() as conn:
        return conn.execute(sql, params).fetchall()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--competition", action="append", default=[],
                    help="competition slug, repeatable (ipl, bbl, the-hundred-mens, ...)")
    ap.add_argument("--missing", action="store_true", help="only teams with no file yet")
    ap.add_argument("--csv", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    have = existing()
    rows = []
    for name, gender, national, competition, _ in teams(args.competition):
        key = slug(name)
        file = have.get(key)
        if args.missing and file:
            continue
        rows.append({
            "team": name,
            "gender": gender,
            "kind": "national" if national else "club",
            "competition": competition or "",
            "filename": f"{key}.svg",
            "supplied": file or "",
        })

    if args.csv:
        w = csv.DictWriter(sys.stdout, fieldnames=list(rows[0]) if rows else
                           ["team", "gender", "kind", "competition", "filename", "supplied"])
        w.writeheader()
        w.writerows(rows)
        return 0

    if not rows:
        print("no teams matched" if args.competition else "no teams - run scripts/ingest.py first")
        return 0

    width = max(len(r["team"]) for r in rows)
    for r in rows:
        mark = "have" if r["supplied"] else "    "
        print(f"  {mark}  {r['team']:<{width}}  {r['filename']}")
    print(f"\n{len(rows)} team(s); {sum(1 for r in rows if r['supplied'])} already supplied")
    print(f"drop files into {LOGO_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
