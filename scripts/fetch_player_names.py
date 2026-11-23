"""Resolve Cricsheet scorecard names ("SS Iyer") to full names ("Shreyas Iyer").

    python scripts/fetch_player_names.py

Cricsheet identifies players by a scorecard name: initials plus surname. Nobody
searching for a player types "SS Iyer", so Stryk needs the full name as well.
Neither the match files nor Cricsheet's own people register carry one, but the
register does carry each player's ESPNcricinfo id, and Wikidata publishes full
names keyed on that same id. Joining the two gives a real, sourced full name
for ~97% of the players in the IPL dataset.

Two requests total, both to public bulk endpoints - no per-player scraping:

  1. https://cricsheet.org/register/people.csv   identifier -> cricinfo id
  2. Wikidata SPARQL (property P2697)            cricinfo id -> full name

Output: data/raw/people/full_names.csv (cricsheet_id, scorecard_name, full_name)

Players this cannot resolve keep their scorecard name and are listed at the end
of the run. They are searchable by that name; nothing is invented for them.
"""
from __future__ import annotations

import csv
import io
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "people" / "full_names.csv"

REGISTER_URL = "https://cricsheet.org/register/people.csv"
WIKIDATA_URL = "https://query.wikidata.org/sparql"
# P2697 is "ESPNcricinfo player ID". One query returns every cricketer that has
# one, which is far politer than 800 individual page fetches.
SPARQL = """
SELECT ?cricinfo ?name WHERE {
  ?item wdt:P2697 ?cricinfo .
  ?item rdfs:label ?name .
  FILTER(LANG(?name) = "en")
}
"""
SEARCH_URL = "https://www.wikidata.org/w/api.php"
# Aliases matter as much as labels: Wikidata labels Prabhsimran Singh as the
# shorter "Simran Singh" and keeps the fuller name only as an alias, so a
# search for what people actually type would miss him.
ALIAS_SPARQL = """
SELECT ?cricinfo ?alias WHERE {
  ?item wdt:P2697 ?cricinfo .
  ?item skos:altLabel ?alias .
  FILTER(LANG(?alias) = "en")
}
"""
MANUAL = ROOT / "data" / "raw" / "people" / "full_names_manual.csv"
# A generic client name: this identifies the software, not the person running it.
USER_AGENT = "StrykCricketAnalytics/0.1 (cricket analytics project)"


def _get(url: str, accept: str, timeout: int = 300, tries: int = 4) -> str:
    """GET with backoff.

    The Wikidata query service rate-limits aggressively during its own
    outages - as little as one request a minute - so a bulk query has to be
    patient rather than abandon the whole run.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503) and attempt < tries - 1:
                wait = 70 * (attempt + 1)
                print(f"  rate limited ({exc.code}); waiting {wait}s")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("unreachable")


def fetch_register() -> dict[str, str]:
    """Cricsheet identifier -> ESPNcricinfo id."""
    print(f"fetching {REGISTER_URL}")
    text = _get(REGISTER_URL, "text/csv")
    out: dict[str, str] = {}
    for row in csv.DictReader(io.StringIO(text)):
        key = (row.get("key_cricinfo") or "").strip()
        if key:
            out[row["identifier"]] = key
    print(f"  {len(out)} players with an ESPNcricinfo id")
    return out


def fetch_aliases() -> dict[str, list[str]]:
    """ESPNcricinfo id -> alternative names recorded on Wikidata."""
    url = f"{WIKIDATA_URL}?{urllib.parse.urlencode({'query': ALIAS_SPARQL})}"
    print("querying Wikidata for alternative names")
    text = _get(url, "text/csv")
    out: dict[str, list[str]] = {}
    for row in csv.DictReader(io.StringIO(text)):
        cid, alias = row["cricinfo"].strip(), row["alias"].strip()
        if cid and alias and not _is_qid(alias):
            out.setdefault(cid, []).append(alias)
    print(f"  {sum(len(v) for v in out.values())} alias(es) for {len(out)} players")
    return out


def best_display(label: str, aliases: list[str]) -> str:
    """Promote only an alias that spells out the *start* of the first name.

    Cricsheet writes Prabhsimran Singh as "P Simran Singh" and Wikidata labels
    him "Simran Singh", so the alias "Prabhsimran Singh" is the same name
    written out properly: same number of words, identical surname, and the
    label's first word is the tail of the alias's.

    Nothing else is promoted. Plain substring containment was tried first and
    was far too eager - a full legal name ("Separamadu Lasith Malinga"), a
    disambiguation artefact ("Cricketer Ravindra Jadeja") and a misspelling
    ("Nicolas Poorann") all contain or resemble the label, and none of them is
    the name anybody uses. Every alias is indexed for search regardless, so
    being passed over here costs nothing.
    """
    label_words = label.split()
    if len(label_words) < 2:
        return label
    for alias in aliases:
        alias_words = alias.split()
        if len(alias_words) != len(label_words):
            continue
        if [w.lower() for w in alias_words[1:]] != [w.lower() for w in label_words[1:]]:
            continue
        first_label, first_alias = label_words[0].lower(), alias_words[0].lower()
        if first_alias != first_label and first_alias.endswith(first_label):
            return alias
    return label


def _is_qid(label: str) -> bool:
    """An item with no English label comes back as its bare Q-number."""
    return len(label) > 1 and label[0] == "Q" and label[1:].isdigit()


def is_initials_form(name: str) -> bool:
    """True for a scorecard-style name: "SS Iyer", "V Kohli", "MS Dhoni".

    Used to reject a "full name" that is no more searchable than what we
    already have - some Wikidata items are themselves labelled with initials.
    """
    head = name.split(" ")[0] if " " in name else ""
    return bool(head) and 1 <= len(head) <= 3 and head.isupper() and head.isalpha()


def search_one(scorecard: str) -> str:
    """Resolve a single player through Wikidata's search API.

    The bulk query misses players whose item lacks an English rdfs:label or a
    P2697 statement. Searching the scorecard name often still finds them,
    because that form is usually recorded as an alias - "SR Tendulkar" matches
    the item labelled "Sachin Tendulkar". Returns "" when nothing usable comes
    back; a name is never constructed from the initials.
    """
    import json

    params = urllib.parse.urlencode({
        "action": "wbsearchentities", "format": "json", "language": "en",
        "type": "item", "limit": "5", "search": scorecard,
    })
    # Wikidata rate-limits bursts with HTTP 429. Without a retry the name is
    # silently dropped, which looked like missing data rather than throttling.
    payload = None
    for attempt in range(4):
        try:
            payload = json.loads(_get(f"{SEARCH_URL}?{params}", "application/json", timeout=30))
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            return ""
        except Exception:  # noqa: BLE001 - a lookup failure is just an unresolved name
            return ""
    if payload is None:
        return ""
    for hit in payload.get("search", []):
        label = (hit.get("label") or "").strip()
        description = (hit.get("description") or "").lower()
        if "cricket" not in description:
            continue
        if label and not _is_qid(label) and not is_initials_form(label):
            return label
    return ""


def load_manual() -> dict[str, str]:
    """Operator-maintained overrides: cricsheet_id,full_name.

    The escape hatch for players no public source resolves. Nothing is written
    here automatically.
    """
    if not MANUAL.exists():
        return {}
    with MANUAL.open(newline="", encoding="utf-8") as f:
        rows = {r["cricsheet_id"]: r["full_name"].strip() for r in csv.DictReader(f)}
    print(f"  {len(rows)} manual override(s) from {MANUAL.name}")
    return rows


def fetch_wikidata() -> dict[str, str]:
    """ESPNcricinfo id -> full name."""
    url = f"{WIKIDATA_URL}?{urllib.parse.urlencode({'query': SPARQL})}"
    print("querying Wikidata for full names (this takes ~45s)")
    text = _get(url, "text/csv")
    out: dict[str, str] = {}
    for row in csv.DictReader(io.StringIO(text)):
        cid, label = row["cricinfo"].strip(), row["name"].strip()
        if cid and label and not _is_qid(label) and not is_initials_form(label):
            out.setdefault(cid, label)
    print(f"  {len(out)} names")
    return out


def _engine():
    sys.path.insert(0, str(ROOT / "backend"))
    from app.core.db import engine  # noqa: E402

    return engine


def ensure_column() -> None:
    """Add player.full_name to a database that predates it.

    Run before anything reads the table: the ORM model declares the column, so
    an older database would otherwise fail on the first select.
    """
    from sqlalchemy import text

    with _engine().begin() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(player)"))}
        if "full_name" not in cols:
            print("adding player.full_name column")
            conn.execute(text("ALTER TABLE player ADD COLUMN full_name VARCHAR(120)"))
        if "aliases" not in cols:
            print("adding player.aliases column")
            conn.execute(text("ALTER TABLE player ADD COLUMN aliases VARCHAR(500)"))


def scorecard_names() -> dict[str, str]:
    """Cricsheet identifier -> scorecard name, read from the ingested database."""
    from sqlalchemy import text

    with _engine().connect() as conn:
        return {r[0]: r[1] for r in conn.execute(text("SELECT id, name FROM player"))}


def apply_to_database(rows: list[dict]) -> int:
    """Write the resolved names onto the player table."""
    from sqlalchemy import text

    with _engine().begin() as conn:
        for row in rows:
            conn.execute(
                text("UPDATE player SET full_name = :full, aliases = :aliases WHERE id = :pid"),
                {"full": row["full_name"], "aliases": row.get("aliases") or None,
                 "pid": row["cricsheet_id"]},
            )
    return len(rows)


def main() -> int:
    ensure_column()
    players = scorecard_names()
    if not players:
        print("no players in the database - run scripts/ingest.py first")
        return 1
    print(f"{len(players)} players in the database")

    register = fetch_register()
    names = fetch_wikidata()
    aliases = fetch_aliases()

    manual = load_manual()

    rows, needs_search = [], []
    for pid, scorecard in sorted(players.items(), key=lambda kv: kv[1]):
        known = aliases.get(register.get(pid, ""), [])
        full = manual.get(pid) or names.get(register.get(pid, ""), "")
        if full and not manual.get(pid):
            full = best_display(full, known)
        if full:
            rows.append({"cricsheet_id": pid, "scorecard_name": scorecard,
                         "full_name": full, "aliases": "|".join(known)})
        elif is_initials_form(scorecard):
            # Already-full names ("Priyansh Arya") need no resolution at all.
            needs_search.append((pid, scorecard, known))
        else:
            rows.append({"cricsheet_id": pid, "scorecard_name": scorecard,
                         "full_name": scorecard, "aliases": "|".join(known)})

    if needs_search:
        print(f"resolving {len(needs_search)} remaining name(s) via the Wikidata search API")
    unresolved = []
    for index, (pid, scorecard, known) in enumerate(needs_search):
        if index:
            time.sleep(1.0)
        full = search_one(scorecard)
        if full:
            rows.append({"cricsheet_id": pid, "scorecard_name": scorecard,
                         "full_name": best_display(full, known), "aliases": "|".join(known)})
        else:
            unresolved.append(scorecard)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["cricsheet_id", "scorecard_name", "full_name", "aliases"]
        )
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: r["scorecard_name"]))

    pct = 100 * len(rows) / len(players)
    print(f"\nwrote {len(rows)} full names to {OUT} ({pct:.1f}% coverage)")

    applied = apply_to_database(rows)
    print(f"updated {applied} player row(s) in the database")

    if unresolved:
        print(f"\n{len(unresolved)} player(s) keep their scorecard name "
              f"(searchable by surname; add them to {MANUAL.name} to override):")
        for name in unresolved[:30]:
            print(f"  {name}")
        if len(unresolved) > 30:
            print(f"  ... and {len(unresolved) - 30} more")
    print("\nRestart the API (or POST /api/admin/reload) to pick the names up.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
