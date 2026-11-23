"""Download freely licensed player photographs from Wikimedia Commons.

    python scripts/fetch_player_photos.py

Player photographs on the usual cricket sites are all rights reserved, so they
cannot be used here. Wikimedia Commons hosts freely licensed images of many
cricketers, and Wikidata links them to the same ESPNcricinfo ids that
scripts/fetch_player_names.py already joins on, so the photos can be matched
to players without guesswork.

Most Commons licences (CC-BY, CC-BY-SA) require credit, so this records the
author and licence for every image it keeps and the UI displays them. An image
whose attribution cannot be read is skipped rather than shown uncredited.

Output:
  frontend/public/players/<cricsheet_id>.jpg   320px-wide thumbnails
  frontend/public/players/credits.json         author + licence per player

Both are gitignored: they are fetched assets, like the Cricsheet data itself.
Players with no free image keep their generated monogram, which is why the UI
never depends on a photo existing.
"""
from __future__ import annotations

import csv
import io
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "frontend" / "public" / "players"
CREDITS = OUT_DIR / "credits.json"

REGISTER_URL = "https://cricsheet.org/register/people.csv"
WIKIDATA_URL = "https://query.wikidata.org/sparql"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
# P2697 is "ESPNcricinfo player ID"; P18 is "image".
SPARQL = """
SELECT ?cricinfo ?image WHERE {
  ?item wdt:P2697 ?cricinfo .
  ?item wdt:P18 ?image .
}
"""
USER_AGENT = "StrykCricketAnalytics/0.1 (cricket analytics project)"
THUMB_WIDTH = 320


MAX_RETRIES = 6


def _get(url: str, accept: str, timeout: int = 120, retries: int = MAX_RETRIES) -> bytes:
    """GET with backoff: Wikimedia rate-limits bursts with 429 + Retry-After."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed https hosts
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 503) or attempt == retries:
                raise
            try:
                wait = float(exc.headers.get("Retry-After", ""))
            except ValueError:
                wait = 0.0
            wait = min(max(wait, 2.0 * 2**attempt), 120.0)
            print(f"  rate limited ({exc.code}), retrying in {wait:.0f}s")
            time.sleep(wait)
    raise AssertionError("unreachable")


def players_with_cricinfo() -> dict[str, tuple[str, str]]:
    """Cricsheet id -> (display name, ESPNcricinfo id)."""
    sys.path.insert(0, str(ROOT / "backend"))
    from sqlalchemy import text

    from app.core.db import engine

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, COALESCE(full_name, name) FROM player")
        ).fetchall()
    names = {r[0]: r[1] for r in rows}

    print(f"fetching {REGISTER_URL}")
    text_csv = _get(REGISTER_URL, "text/csv").decode("utf-8")
    out: dict[str, tuple[str, str]] = {}
    for row in csv.DictReader(io.StringIO(text_csv)):
        key = (row.get("key_cricinfo") or "").strip()
        if key and row["identifier"] in names:
            out[row["identifier"]] = (names[row["identifier"]], key)
    print(f"  {len(out)} of {len(names)} players carry an ESPNcricinfo id")
    return out


def commons_images() -> dict[str, str]:
    """ESPNcricinfo id -> Commons file name."""
    print("querying Wikidata for freely licensed images")
    url = f"{WIKIDATA_URL}?{urllib.parse.urlencode({'query': SPARQL})}"
    data = _get(url, "text/csv", timeout=240).decode("utf-8")
    out: dict[str, str] = {}
    for row in csv.DictReader(io.StringIO(data)):
        cid, image = row["cricinfo"].strip(), row["image"].strip()
        if not cid or not image:
            continue
        # The IRI ends in the Commons file name, percent-encoded.
        filename = urllib.parse.unquote(image.rsplit("/", 1)[-1])
        out.setdefault(cid, filename)
    print(f"  {len(out)} images")
    return out


def attribution(filenames: list[str]) -> dict[str, dict]:
    """Author and licence for each Commons file, 50 at a time."""
    out: dict[str, dict] = {}
    for start in range(0, len(filenames), 50):
        chunk = filenames[start : start + 50]
        params = urllib.parse.urlencode({
            "action": "query", "format": "json", "prop": "imageinfo",
            "iiprop": "extmetadata", "titles": "|".join(f"File:{f}" for f in chunk),
        })
        try:
            payload = json.loads(_get(f"{COMMONS_API}?{params}", "application/json", timeout=60))
        except Exception as exc:  # noqa: BLE001 - a chunk failing just means no credit
            print(f"  attribution lookup failed for one chunk: {exc}")
            continue
        for page in (payload.get("query", {}).get("pages") or {}).values():
            info = (page.get("imageinfo") or [{}])[0].get("extmetadata") or {}
            title = str(page.get("title", "")).removeprefix("File:")
            author = _plain(info.get("Artist", {}).get("value", ""))
            licence = info.get("LicenseShortName", {}).get("value", "")
            if title and licence:
                out[title] = {"author": author or "Unknown", "licence": licence}
        time.sleep(0.4)
        print(f"  attribution {min(start + 50, len(filenames))}/{len(filenames)}")
    return out


def _plain(html: str) -> str:
    """Commons returns the author as HTML; keep the text, drop the markup."""
    import re

    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&amp;", "&").replace("&quot;", '"').replace("&#039;", "'")
    return " ".join(text.split())[:120]


def main() -> int:
    players = players_with_cricinfo()
    if not players:
        print("no players found - run scripts/ingest.py first")
        return 1
    images = commons_images()

    wanted = {pid: images[cid] for pid, (_, cid) in players.items() if cid in images}
    print(f"\n{len(wanted)} player(s) have a freely licensed image")
    if not wanted:
        return 0

    credits_by_file = attribution(sorted(set(wanted.values())))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    credits: dict[str, dict] = {}
    saved = skipped = failed = deferred = 0
    consecutive_failures = 0
    blocked = False
    for index, (pid, filename) in enumerate(sorted(wanted.items()), 1):
        credit = credits_by_file.get(filename)
        if not credit:
            # No readable licence means it cannot be displayed with credit.
            skipped += 1
            continue
        target = OUT_DIR / f"{pid}.jpg"
        if not target.exists():
            if blocked:
                # Keep walking the list so photos already on disk still get
                # their credits recorded; just stop asking for new ones.
                deferred += 1
                continue
            url = (
                "https://commons.wikimedia.org/wiki/Special:FilePath/"
                f"{urllib.parse.quote(filename)}?width={THUMB_WIDTH}"
            )
            try:
                # Few retries: once the thumbnail server blocks this client the
                # block lasts many minutes, so long backoff per photo only turns
                # a blocked run into an hours-long one.
                target.write_bytes(_get(url, "image/*", timeout=60, retries=1))
                consecutive_failures = 0
            except Exception as exc:  # noqa: BLE001
                print(f"  could not fetch {filename}: {exc}")
                failed += 1
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    blocked = True
                    print("  Wikimedia is blocking downloads; stopping here. "
                          "Re-run later - photos already saved are kept.")
                continue
            # Faster pacing (0.25s) trips Wikimedia's thumbnail rate limit after
            # ~50 images, and the block then outlasts every retry.
            time.sleep(1.0)
        credits[pid] = {
            "file": filename,
            "author": credit["author"],
            "licence": credit["licence"],
            "source": f"https://commons.wikimedia.org/wiki/File:{urllib.parse.quote(filename)}",
        }
        saved += 1
        if index % 25 == 0:
            # Written as we go, so an interrupted run still leaves usable
            # photos rather than a directory of images with no credits.
            CREDITS.write_text(json.dumps(credits, indent=1, sort_keys=True) + "\n")
            print(f"  {index}/{len(wanted)}")

    CREDITS.write_text(json.dumps(credits, indent=1, sort_keys=True) + "\n")
    print(f"\nsaved {saved} photo(s) to {OUT_DIR}")
    if skipped:
        print(f"{skipped} skipped: no readable licence, so they cannot be credited")
    if failed:
        print(f"{failed} failed to download")
    if deferred:
        print(f"{deferred} not attempted after Wikimedia started blocking - re-run "
              "this script in 15-30 minutes to fetch them")
    print("Players without a photo fall back to their generated monogram.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
