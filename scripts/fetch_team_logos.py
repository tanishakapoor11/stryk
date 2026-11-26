"""Download team logos that Wikimedia Commons hosts under a free licence.

    python scripts/fetch_team_logos.py
    python scripts/fetch_team_logos.py --competition ipl --competition bbl
    python scripts/fetch_team_logos.py --dry-run        # report, download nothing

Most cricket crests are NOT here. A club logo is usually non-free, which means
Commons will not host it: it lives on Wikipedia under a fair-use tag that does
not permit reuse. What Commons does hold is the subset simple enough to fall
below the threshold of originality - plain wordmarks and basic shapes - which
are in the public domain and genuinely free to copy. This script takes those
and leaves everything else alone, so the gap it cannot fill stays visible
rather than being filled with something that only looks right.

Only public-domain files are saved. A file under CC-BY or CC-BY-SA carries an
attribution obligation that nothing in the interface currently discharges, so
those are reported at the end for an operator to decide on, never downloaded.

Matching is deliberately strict. Commons' relevance search is useless here: a
search for "Sydney Sixers" returns a photograph of the Sydney to Hobart yacht
race, and "Kolkata Knight Riders" a picture of Sourav Ganguly. A candidate is
therefore only accepted when its own file name contains every significant word
of the team's name AND a word like "logo" or "crest". A wrong logo on a team
is worse than no logo, because nothing about it looks like an error.

Output:
  frontend/public/teams/<team-name-slug>.<ext>   the logo, read automatically
  frontend/public/teams/credits.json             licence + source per file

Anything not found is listed by scripts/team_logo_manifest.py, and a file
dropped in by hand at the same name is used the same way.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "frontend" / "public" / "teams"
CREDITS = OUT_DIR / "credits.json"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "StrykCricketAnalytics/0.1 (cricket analytics project)"
EXTENSIONS = ("svg", "png", "webp", "jpg", "jpeg")
LOGO_WORDS = ("logo", "crest", "emblem", "badge", "flag")
#: Words that carry no identity, so they are not required to appear in a file
#: name: "Surrey County Cricket Club" is filed on Commons as "Surrey CCC logo".
NOISE = {"cricket", "club", "county", "ccc", "team", "the", "and", "of", "xi"}
#: Only these need no credit line. See the module docstring.
FREE = ("public domain", "cc0", "pd-")
#: Another sport's club can share a cricket side's name exactly - the West
#: Indies Football Association is one search result away from the cricket
#: team - and its badge would be accepted on every other test.
OTHER_SPORTS = ("football", "soccer", "rugby", "hockey", "netball", "basketball",
                "athletic", "baseball", "fc", "afc", "united")
#: A superseded mark is still a real logo of the right team, so it is kept, but
#: it loses to a current one.
STALE = ("pre", "old", "former", "original", "historic", "obsolete")

sys.path.insert(0, str(ROOT / "backend"))


def slug(name: str) -> str:
    decomposed = unicodedata.normalize("NFD", name.lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", stripped))


def _get(params: dict, timeout: int = 60, retries: int = 5) -> dict:
    """GET the Commons API with backoff; it answers a burst with HTTP 429."""
    url = f"{COMMONS_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 503) or attempt == retries:
                raise
            try:
                wait = float(exc.headers.get("Retry-After", ""))
            except ValueError:
                wait = 0.0
            wait = min(max(wait, 2.0 * 2**attempt), 60.0)
            print(f"    rate limited ({exc.code}), waiting {wait:.0f}s")
            time.sleep(wait)
    raise AssertionError("unreachable")


def _download(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def significant(name: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", name.lower()) if w not in NOISE]


def accepts(title: str, team: str, national: bool) -> bool:
    """Does this file name actually name this team, and claim to be a logo?

    A national side is named after a country, and a country name plus the word
    "logo" matches a vast amount of Commons that has nothing to do with
    cricket: searching "India logo" returns Oil India Limited, "Sri Lanka"
    returns a resort chain called NUWA, and "England" returned a Rockstar
    energy drink mark. All three were downloaded by an earlier version of this
    filter and looked, on the page, exactly like a correct logo.

    So for any side whose name is not distinctive on its own - every national
    team, and a one-word club like Surrey - the file name must also say
    "cricket". A franchise name such as "Rajasthan Royals" carries no such
    risk and is accepted on its own.
    """
    body = title.lower()
    if not any(w in body for w in LOGO_WORDS):
        return False
    if any(re.search(rf"\b{w}\b", body) for w in OTHER_SPORTS):
        return False
    words = significant(team)
    if not words or not all(w in body for w in words):
        return False
    if (national or len(words) < 2) and "cricket" not in body:
        return False
    return True


def candidates(team: str, national: bool) -> list[dict]:
    term = f"{team} cricket logo" if national else f"{team} logo"
    search = _get({
        "action": "query", "format": "json", "list": "search", "srnamespace": 6,
        "srlimit": 12, "srsearch": term,
    })
    titles = [h["title"] for h in search.get("query", {}).get("search", [])
              if accepts(h["title"], team, national)]
    if not titles:
        return []
    info = _get({
        "action": "query", "format": "json", "prop": "imageinfo",
        "iiprop": "extmetadata|url|size", "titles": "|".join(titles[:10]),
    })
    out = []
    for page in (info.get("query", {}).get("pages") or {}).values():
        ii = (page.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata") or {}
        licence = (meta.get("LicenseShortName", {}) or {}).get("value") or ""
        # Strip the query string before reading the extension: Commons appends
        # ?utm_source=commons.wikimedia.org, whose last dot is in the hostname,
        # so splitting the whole URL yields "org" and every file is discarded.
        url = (ii.get("url") or "").split("?")[0]
        ext = url.rsplit(".", 1)[-1].lower() if "." in url else ""
        if not licence or ext not in EXTENSIONS:
            continue
        out.append({
            "title": str(page.get("title", "")).removeprefix("File:"),
            "licence": licence, "url": url, "ext": ext,
            "free": any(f in licence.lower() for f in FREE),
        })
    # A free licence first, because a credited one cannot be used at all yet;
    # then a current mark over a superseded one; then a vector over a bitmap;
    # then the shortest name, which is reliably the plain mark rather than a
    # dated variant of it.
    def stale(title: str) -> bool:
        low = title.lower()
        return bool(re.search(r"(19|20)\d{2}", low)) or any(w in low for w in STALE)

    out.sort(key=lambda c: (not c["free"], stale(c["title"]), c["ext"] != "svg",
                            len(c["title"])))
    return out


def teams(competitions: list[str]) -> list[tuple[str, bool]]:
    """(name, is_national) for every team worth looking a logo up for.

    A national side identified by its flag is skipped: the flag is how cricket
    actually labels a country - it is what ESPNcricinfo, Cricbuzz and Crex all
    show - and a board's corporate mark next to it in the same table makes the
    column read as two different things. The exception is a side with no flag,
    which is why West Indies and the composite XIs are still looked up.
    """
    import sqlalchemy
    from sqlalchemy import text

    from app.core.db import engine

    where, params = "", {}
    if competitions:
        where = """AND t.id IN (SELECT ct.team_id FROM competition_team ct
                                JOIN competition c ON c.id = ct.competition_id
                                WHERE c.slug IN :slugs)"""
        params["slugs"] = tuple(competitions)
    sql = text(f"""
        SELECT DISTINCT t.name, t.is_national_team, c.flag,
               (SELECT COUNT(*) FROM competition_team ct WHERE ct.team_id = t.id) AS n
        FROM team t LEFT JOIN country c ON c.id = t.country_id
        WHERE 1 = 1 {where} ORDER BY n DESC, t.name
    """)
    if competitions:
        sql = sql.bindparams(sqlalchemy.bindparam("slugs", expanding=True))
    with engine.connect() as conn:
        seen, out, skipped = set(), [], 0
        for name, national, flag, _ in conn.execute(sql, params):
            if name in seen:
                continue
            seen.add(name)
            if national and flag:
                skipped += 1
                continue
            out.append((name, bool(national)))
        if skipped:
            print(f"skipping {skipped} national side(s) already identified by a flag")
        return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--competition", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    roster = teams(args.competition)
    if not roster:
        print("no teams - run scripts/ingest.py first")
        return 1
    print(f"checking Commons for {len(roster)} team(s)\n")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        credits = json.loads(CREDITS.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - no credits file yet
        credits = {}

    have = {p.stem.lower() for p in OUT_DIR.iterdir()
            if p.suffix.lower().lstrip(".") in EXTENSIONS} if OUT_DIR.is_dir() else set()

    saved, needs_credit, missing = [], [], []
    for index, (name, national) in enumerate(roster, 1):
        key = slug(name)
        if key in have:
            continue
        try:
            found = candidates(name, national)
        except Exception as exc:  # noqa: BLE001 - one team failing is not fatal
            print(f"  {name}: lookup failed ({exc})")
            missing.append(name)
            continue
        free = [c for c in found if c["free"]]
        if not free:
            missing.append(name)
            if found:
                needs_credit.append((name, found[0]))
        else:
            pick = free[0]
            target = OUT_DIR / f"{key}.{pick['ext']}"
            print(f"  {name} -> {pick['title']}  [{pick['licence']}]")
            if not args.dry_run:
                try:
                    target.write_bytes(_download(pick["url"]))
                except Exception as exc:  # noqa: BLE001
                    print(f"    download failed: {exc}")
                    missing.append(name)
                    continue
                credits[key] = {
                    "team": name, "file": pick["title"], "licence": pick["licence"],
                    "source": "https://commons.wikimedia.org/wiki/File:"
                              + urllib.parse.quote(pick["title"].replace(" ", "_")),
                }
            saved.append(name)
        # Two API calls per team. Commons answers a faster cadence than this
        # with 429 and a Retry-After in the forties, so pacing is cheaper than
        # backing off: 1.5s per team beats 0.8s plus a 40s penalty.
        time.sleep(1.5)
        if index % 25 == 0:
            print(f"  ...{index}/{len(roster)}")
            if not args.dry_run:
                CREDITS.write_text(json.dumps(credits, indent=1, sort_keys=True) + "\n")

    if not args.dry_run:
        CREDITS.write_text(json.dumps(credits, indent=1, sort_keys=True) + "\n")

    print(f"\n{len(saved)} public-domain logo(s)"
          f"{' would be' if args.dry_run else ''} saved to {OUT_DIR}")
    if needs_credit:
        print(f"\n{len(needs_credit)} team(s) have a logo on Commons under a licence that "
              "requires credit.\nNothing in the interface shows a credit line for a team "
              "logo yet, so these are\nnot downloaded. Listed here to decide on:")
        for name, c in needs_credit[:40]:
            print(f"  {name:36s} {c['licence']:16s} {c['title']}")
    print(f"\n{len(missing)} team(s) have no free logo on Commons - almost all of them. "
          "Run\nscripts/team_logo_manifest.py --missing for the filenames to supply by hand.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
