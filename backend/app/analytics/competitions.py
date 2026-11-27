"""Competition, season and coverage documents for the discovery pages.

Reads the unscoped dataset (every competition) for directory-level views and a
scoped one for anything statistical, so a season's leaders can never include
deliveries from another competition.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Dict, List, Optional

import pandas as pd

from app import catalog
from app.analytics import overview, standings, store
from app.analytics.store import Dataset, Filters

#: Coverage statuses, most to least data. Labels are what the UI shows.
COVERAGE_LABELS = {
    "ball_by_ball": "Full ball-by-ball",
    "detailed": "Detailed statistics",
    "scorecard": "Scorecards",
    "results": "Results only",
    "metadata": "Fixtures and metadata only",
    "mixed": "Mixed coverage",
    "not_ingested": "Available, not yet imported",
    "unavailable": "No data source",
}
_LEVEL_STATUS = {5: "ball_by_ball", 4: "ball_by_ball", 3: "detailed", 2: "scorecard", 1: "metadata"}

#: Where an uncatalogued competition sorts: behind every curated tier. Ingest
#: invents one of these for any match no catalogue rule claims - a single
#: bilateral tour, a regional qualifier - and there are more of them than there
#: are real competitions.
UNRANKED = 9


@lru_cache(maxsize=1)
def first_seasons() -> Dict[str, int]:
    """The year each competition began - not the year its data begins.

    Cricsheet publishes deliveries, and the earliest are from 2001, so a
    competition older than that is in STRYK only from where the ball-by-ball
    record starts. Comparing the two years is the only way to tell a complete
    record (every IPL season) from a partial one (Test cricket since 2001),
    and cumulative lists like most runs are honest only for the first.
    Competitions whose lineage is ambiguous carry no year and count as partial.
    """
    return {c["slug"]: int(c["first_season"]) for c in catalog.catalogue()["competitions"]
            if c.get("first_season")}


def coverage_is_complete(slug: str, first_match: Optional[str]) -> Optional[bool]:
    """Whether STRYK holds every season a competition has played.

    None where it cannot be told: an uncatalogued competition, or one whose
    first season is not established.
    """
    began = first_seasons().get(slug)
    if began is None or not first_match:
        return None
    return int(first_match[:4]) <= began


@lru_cache(maxsize=1)
def prominence() -> Dict[str, int]:
    """How prominent each competition is, 1 (headline) to 5 (niche).

    How much interest a competition holds is an editorial judgement, not
    something the ball-by-ball data can be asked: the County Championship plays
    more matches than the IPL. So it is curated in competitions.json beside the
    rest of the competition metadata, and every list here is ordered by it.
    """
    return {c["slug"]: int(c["prominence"]) for c in catalog.catalogue()["competitions"]
            if c.get("prominence")}


def rank(c: dict) -> int:
    """The sort rank of a card or any dict carrying a ``slug``."""
    return prominence().get(c["slug"], UNRANKED)


FIXTURES_UNAVAILABLE = (
    "Upcoming and live fixtures are not available: the only data source in use (Cricsheet) "
    "publishes completed matches."
)


def _none(v):
    """Null for missing values; numpy scalars become plain Python for JSON."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        return v
    return v.item() if hasattr(v, "item") and not isinstance(v, (str, bytes)) else v


def _country(ds: Dataset, country_id) -> Optional[dict]:
    countries = ds.registry.get("countries")
    if country_id is None or pd.isna(country_id) or countries is None or countries.empty:
        return None
    row = countries[countries["id"] == int(country_id)]
    if row.empty:
        return None
    r = row.iloc[0]
    return {"id": int(r["id"]), "code": r["short_code"], "name": r["name"],
            "flag": _none(r["flag"]), "cricket_board": _none(r["cricket_board"])}


def _source_datasets(ds: Dataset, rules: list) -> List[dict]:
    """The source datasets a competition is mapped to, with advertised counts."""
    sd = ds.registry.get("source_datasets")
    src = ds.registry.get("sources")
    out = []
    for rule in rules or []:
        if "dataset" not in rule or sd is None or sd.empty:
            continue
        hit = sd[sd["key"] == rule["dataset"]]
        if hit.empty:
            continue
        h = hit.iloc[0]
        source = src[src["id"] == h["source_id"]].iloc[0] if src is not None and not src.empty else None
        out.append({
            "source": source["name"] if source is not None else rule.get("provider"),
            "dataset": h["key"],
            "name": h["name"],
            "url": h["url"],
            "published_matches": _none(h["published_matches"]),
            # A dataset can hold both genders (The Hundred) and so more
            # matches than this one competition.
            "gender_filter": rule.get("gender"),
            "checked_on": str(source["checked_on"]) if source is not None else None,
        })
    return out


def coverage(ds: Dataset, comp_id: int) -> dict:
    comp = ds.competitions.loc[comp_id]
    m = ds.matches[ds.matches["competition_id"] == comp_id] if not ds.matches.empty else ds.matches
    sources = _source_datasets(ds, comp["match_rules"])
    if m.empty:
        if _none(comp.get("unavailable_reason")):
            status, detail = "unavailable", comp["unavailable_reason"]
        elif sources:
            status = "not_ingested"
            detail = ("Published by " + ", ".join(f"{s['source']} ({s['name']})" for s in sources)
                      + " but not imported into STRYK yet.")
        else:
            status, detail = "unavailable", "No data source is mapped to this competition."
        return {"status": status, "label": COVERAGE_LABELS[status], "detail": detail,
                "matches": 0, "seasons": 0, "data_levels": [], "sources": sources,
                "begins": first_seasons().get(comp["slug"]), "complete": None}
    levels = sorted({int(x) for x in m["data_level"].dropna()})
    status = _LEVEL_STATUS.get(levels[0], "metadata") if len(levels) == 1 else "mixed"
    first_match = m["date"].min().date().isoformat()
    return {
        "status": status,
        "label": COVERAGE_LABELS[status],
        "detail": None,
        "matches": int(len(m)),
        "seasons": int(m["season_id"].nunique()),
        "first_match": first_match,
        "last_match": m["date"].max().date().isoformat(),
        "data_levels": levels,
        "sources": sources,
        #: The competition's own first season, and whether STRYK holds all of
        #: it. A career total is only a career total when ``complete``.
        "begins": first_seasons().get(comp["slug"]),
        "complete": coverage_is_complete(comp["slug"], first_match),
    }


def scope_coverage(ds: Dataset) -> dict:
    """Whether the scope in view is a complete record of its competitions.

    Cumulative lists - most runs, most wickets - are a competition's real
    all-time order only when STRYK holds every season it has played. Where it
    does not, the top of the list is whoever played most recently rather than
    whoever scored most, and the interface drops the list instead of implying
    an order it cannot support. A scope of several competitions is complete
    only if every one of them is.
    """
    ids = list(ds.scope.competition_ids) if ds.scope else []
    covs = [coverage(ds, cid) for cid in ids]
    flags = [c["complete"] for c in covs]
    firsts = [int(c["first_match"][:4]) for c in covs if c.get("first_match")]
    begins = [c["begins"] for c in covs if c.get("begins")]
    return {
        # None - not false - where it cannot be told, so the interface can say
        # "unknown" rather than assert a competition is missing seasons.
        "complete": all(flags) if flags and None not in flags else None,
        "begins": min(begins) if begins else None,
        "indexed_from": min(firsts) if firsts else None,
        "indexed_to": max((int(c["last_match"][:4]) for c in covs if c.get("last_match")),
                          default=None),
    }


def _formats(ds: Dataset, comp_id: int, declared) -> List[str]:
    m = ds.matches[ds.matches["competition_id"] == comp_id] if not ds.matches.empty else ds.matches
    seen = {store.canonical_format(x) for x in m["match_type"]} if not m.empty else set()
    return sorted({store.canonical_format(x) for x in (declared or [])} | seen)


def _seasons_of(ds: Dataset, comp_id: int) -> pd.DataFrame:
    s = ds.seasons
    if s.empty:
        return s
    s = s[s["competition_id"] == comp_id]
    counts = ds.matches.groupby("season_id").size() if not ds.matches.empty else pd.Series(dtype=int)
    return s.assign(matches=s.index.map(lambda i: int(counts.get(i, 0)))).sort_values("year", ascending=False)


def _season_doc(sid, row) -> dict:
    return {
        "id": int(sid), "name": row["name"], "year": int(row["year"]),
        "status": row["status"], "format": _none(row["format"]),
        "start_date": str(row["start_date"]) if _none(row["start_date"]) else None,
        "end_date": str(row["end_date"]) if _none(row["end_date"]) else None,
        "matches": int(row.get("matches", 0)),
    }


def card(ds: Dataset, comp_id: int) -> dict:
    c = ds.competitions.loc[comp_id]
    seasons = _seasons_of(ds, comp_id)
    latest = _season_doc(seasons.index[0], seasons.iloc[0]) if not seasons.empty else None
    return {
        "id": int(comp_id),
        "slug": c["slug"],
        "name": c["name"],
        "short_name": _none(c["short_name"]),
        "type": c["competition_type"],
        "gender": c["gender"],
        "country": _country(ds, c["country_id"]),
        "governing_body": _none(c["governing_body"]),
        "description": _none(c["description"]),
        "formats": _formats(ds, comp_id, c["formats"]),
        "is_active": bool(c["is_active"]),
        "is_catalogued": bool(c["is_catalogued"]),
        "has_points_system": _none(c["points_system_id"]) is not None,
        "latest_season": latest,
        "coverage": coverage(ds, comp_id),
    }


def directory(
    ds: Dataset,
    q: Optional[str] = None,
    types: Optional[List[str]] = None,
    gender: Optional[str] = None,
    country: Optional[str] = None,
    fmt: Optional[str] = None,
    season_status: Optional[str] = None,
    coverage_status: Optional[List[str]] = None,
    season_year: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    comps = ds.competitions
    if comps.empty:
        return {"total": 0, "items": [], "facets": {}}
    cards = [card(ds, int(cid)) for cid in comps.index]

    def keep(c: dict) -> bool:
        if q:
            hay = " ".join(filter(None, [c["name"], c["short_name"], c["slug"],
                                         (c["country"] or {}).get("name"), c["governing_body"]])).lower()
            if q.lower() not in hay:
                return False
        if types and c["type"] not in types:
            return False
        if gender and c["gender"] != gender:
            return False
        if country and (c["country"] or {}).get("code") != country:
            return False
        if fmt and fmt not in c["formats"]:
            return False
        if season_status and (c["latest_season"] or {}).get("status") != season_status:
            return False
        if coverage_status and c["coverage"]["status"] not in coverage_status:
            return False
        if season_year is not None:
            years = set(ds.seasons[ds.seasons["competition_id"] == c["id"]]["year"]) if not ds.seasons.empty else set()
            if season_year not in years:
                return False
        return True

    coverage_rank = {"ball_by_ball": 0, "detailed": 1, "scorecard": 2, "mixed": 3, "results": 4,
                     "metadata": 5, "not_ingested": 6, "unavailable": 7}
    kept = sorted(filter(keep, cards),
                  key=lambda c: (coverage_rank[c["coverage"]["status"]], rank(c),
                                 not c["is_active"], -c["coverage"]["matches"], c["name"]))

    def facet(key_fn) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for c in cards:
            for k in key_fn(c):
                if k:
                    out[k] = out.get(k, 0) + 1
        return dict(sorted(out.items()))

    return {
        "total": len(kept),
        "items": kept[offset: offset + limit],
        "limit": limit,
        "offset": offset,
        "facets": {
            "type": facet(lambda c: [c["type"]]),
            "gender": facet(lambda c: [c["gender"]]),
            "country": facet(lambda c: [(c["country"] or {}).get("code")]),
            "format": facet(lambda c: c["formats"]),
            "coverage": facet(lambda c: [c["coverage"]["status"]]),
        },
    }


def find(ds: Dataset, key: str) -> Optional[int]:
    comps = ds.competitions
    if comps.empty:
        return None
    hit = comps.index[comps["slug"] == key.lower()]
    if len(hit):
        return int(hit[0])
    if key.isdigit() and int(key) in comps.index:
        return int(key)
    return None


def find_season(ds: Dataset, comp_id: int, key: str) -> Optional[int]:
    s = ds.seasons
    if s.empty:
        return None
    s = s[s["competition_id"] == comp_id]
    # Season names can contain "/" ("2023/24"); URLs use "-" instead.
    for candidate in (key, key.replace("-", "/")):
        hit = s.index[s["name"] == candidate]
        if len(hit):
            return int(hit[0])
    if key.isdigit() and int(key) in s.index:
        return int(key)
    return None


#: A year anywhere in a search box: "asia cup 2023", "2016 world t20".
_YEAR = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")


def names_a_year(q: str) -> bool:
    """Whether a search query picks out one edition, as "asia cup 2023" does."""
    return bool(_YEAR.search(q))


def search_seasons(ds: Dataset, q: str, limit: int = 6) -> List[dict]:
    """Seasons matching a query that names a competition, usually with a year.

    "Asia Cup 2023" is a question about one tournament, and without this it
    finds nothing at all: no competition is named "Asia Cup 2023", so the
    competition search fails on the year and the reader is told there are no
    results for an edition STRYK holds in full. The year picks the edition and
    the remaining words pick the competition; a year on its own lists that
    season of every competition, most prominent first.

    Seasons with no matches are dropped - a result that opens an empty page is
    worse than one fewer result.
    """
    comps, seasons = ds.competitions, ds.seasons
    if comps.empty or seasons.empty:
        return []
    years = {int(y) for y in _YEAR.findall(q)}
    text = re.sub(r"\s+", " ", _YEAR.sub(" ", q)).strip().lower()
    if text:
        hay = (comps["name"].fillna("") + " " + comps["short_name"].fillna("")
               + " " + comps["slug"].fillna("")).str.lower()
        ids = set(comps.index[hay.str.contains(re.escape(text), regex=True)])
    elif years:
        ids = set(comps.index)
    else:
        return []
    rows = seasons[seasons["competition_id"].isin(ids)]
    if years:
        rows = rows[rows["year"].isin(years)]
    if rows.empty:
        return []
    played = ds.matches.groupby("season_id").size() if not ds.matches.empty else None
    out = []
    for sid, r in rows.iterrows():
        cid = int(r["competition_id"])
        n = int(played.get(sid, 0)) if played is not None else 0
        if not n:
            continue
        out.append({"competition_id": cid, "slug": comps.at[cid, "slug"],
                    "competition": comps.at[cid, "name"], "season": str(r["name"]),
                    "year": int(r["year"]), "matches": n})
    out.sort(key=lambda x: (rank(x), -x["year"]))
    return out[:limit]


def season_slug(name: str) -> str:
    return name.replace("/", "-")


# ------------------------------------------------------------------ results
def result_text(row: pd.Series, teams: pd.DataFrame) -> str:
    def name(tid):
        tid = _none(tid)
        if tid is None:
            return None
        tid = int(tid)
        return teams.at[tid, "short_name"] or teams.at[tid, "name"] if tid in teams.index else str(tid)

    result = row.get("result")
    winner = name(row.get("winner_id"))
    method = f" ({row['method']})" if _none(row.get("method")) else ""
    if result == "no result":
        return "No result"
    if result == "draw":
        return "Match drawn"
    if result == "tie":
        return f"Match tied; {winner} won the super over" if winner else "Match tied"
    if not winner:
        return "Result not recorded"
    kind, margin = _none(row.get("result_type")), _none(row.get("result_margin"))
    if kind == "innings":
        return f"{winner} won by an innings{method}"
    if kind in ("runs", "wickets") and margin is not None:
        margin = int(margin)
        unit = kind[:-1] if margin == 1 else kind
        return f"{winner} won by {margin} {unit}{method}"
    return f"{winner} won{method}"


def match_rows(ds: Dataset, matches: pd.DataFrame, limit: Optional[int] = None) -> List[dict]:
    if matches.empty:
        return []
    m = matches.sort_values(["date", "match_number"], ascending=[False, False])
    if limit:
        m = m.head(limit)
    teams, venues, stages = ds.teams, ds.venues, ds.stages

    def team(tid):
        tid = int(tid)
        if tid not in teams.index:
            return {"id": tid, "name": str(tid), "short_name": None}
        return {"id": tid, "name": teams.at[tid, "name"], "short_name": _none(teams.at[tid, "short_name"])}

    out = []
    for _, r in m.iterrows():
        vid = _none(r.get("venue_id"))
        sid = _none(r.get("stage_id"))
        out.append({
            "id": r["id"],
            "date": r["date"].date().isoformat(),
            "match_number": int(r["match_number"]) if _none(r.get("match_number")) is not None else None,
            "stage": stages.at[int(sid), "name"] if sid is not None and int(sid) in stages.index else None,
            "stage_type": stages.at[int(sid), "stage_type"] if sid is not None and int(sid) in stages.index else None,
            "format": r["match_type"],
            "team1": team(r["team1_id"]),
            "team2": team(r["team2_id"]),
            "winner_id": int(r["winner_id"]) if _none(r.get("winner_id")) is not None else None,
            "result": result_text(r, teams),
            "status": r.get("status"),
            "venue": ({"name": venues.at[int(vid), "name"], "city": _none(venues.at[int(vid), "city"])}
                      if vid is not None and int(vid) in venues.index else None),
            "data_level": int(r["data_level"]) if _none(r.get("data_level")) is not None else None,
        })
    return out


# ------------------------------------------------------------- documents
def _rules(ds: Dataset, points_system_id) -> Optional[dict]:
    ps = ds.registry.get("points_systems")
    if _none(points_system_id) is None or ps is None or ps.empty:
        return None
    hit = ps[ps["id"] == int(points_system_id)]
    return dict(hit.iloc[0]["rules"]) if not hit.empty else None


def _leaders(ds: Dataset, season_ids: Optional[List[int]], limit: int = 5) -> Optional[dict]:
    if ds.deliveries.empty:
        return None
    return overview.leaderboards(ds, Filters(season_ids=season_ids), limit)


def competition(base: Dataset, comp_id: int) -> dict:
    doc = card(base, comp_id)
    seasons = _seasons_of(base, comp_id)
    doc["seasons"] = [_season_doc(i, r) for i, r in seasons.iterrows()]
    rules = _rules(base, base.competitions.at[comp_id, "points_system_id"])
    doc["points_system"] = ({k: rules.get(k) for k in ("slug", "name", "points", "tie_breakers",
                                                        "tie_resolution", "qualifiers", "sources",
                                                        "verified_on", "notes")}
                            if rules else None)
    doc["unavailable_reason"] = _none(base.competitions.at[comp_id, "unavailable_reason"])
    doc["fixtures"] = {"available": False, "reason": FIXTURES_UNAVAILABLE}
    if seasons.empty:
        doc.update(current_season=None, teams=[], recent_results=[], leaders=None)
        return doc

    ds = store.scoped(store.resolve_scope(base, [doc["slug"]]), base)
    latest_id = int(seasons.index[0])
    doc["current_season"] = doc["seasons"][0]
    doc["teams"] = _season_teams(ds, latest_id)
    doc["recent_results"] = match_rows(ds, ds.matches, limit=8)
    doc["leaders"] = _leaders(ds, [latest_id])
    doc["scope"] = ds.scope.describe() if ds.scope else None
    return doc


def _season_teams(ds: Dataset, season_id: int) -> List[dict]:
    m = ds.matches[ds.matches["season_id"] == season_id]
    if m.empty:
        return []
    ids = sorted(set(m["team1_id"]).union(m["team2_id"]))
    out = []
    for tid in ids:
        played = m[(m["team1_id"] == tid) | (m["team2_id"] == tid)]
        out.append({
            "id": int(tid),
            "name": ds.teams.at[tid, "name"],
            "short_name": _none(ds.teams.at[tid, "short_name"]),
            "played": int(len(played)),
            "won": int((played["winner_id"] == tid).sum()),
        })
    return sorted(out, key=lambda t: t["name"])


def season(base: Dataset, comp_id: int, season_id: int) -> dict:
    ds = store.scoped(store.resolve_scope(base, [base.competitions.at[comp_id, "slug"]]), base)
    row = ds.seasons.loc[season_id]
    m = ds.matches[ds.matches["season_id"] == season_id]
    counts = m.groupby("stage_id").size()
    stg = ds.stages[ds.stages["season_id"] == season_id]
    # Order stages by when they were played: Qualifier 1, Eliminator, Qualifier 2, Final.
    first_played = m.groupby("stage_id")["date"].min()
    stg = stg.assign(_first=stg.index.map(first_played)).sort_values(["sequence", "_first", "name"])
    rules = _rules(ds, _none(row["points_system_id"]) or ds.competitions.at[comp_id, "points_system_id"])
    doc = {
        "competition": card(base, comp_id),
        "season": _season_doc(season_id, row.to_dict() | {"matches": int(len(m))}),
        "stages": [{"id": int(i), "name": s["name"], "type": s["stage_type"],
                    "matches": int(counts.get(i, 0))} for i, s in stg.iterrows()],
        "teams": _season_teams(ds, season_id),
        "standings": standings.compute(ds, season_id, rules),
        "knockouts": match_rows(ds, m[m["stage_id"].isin(stg.index[stg["stage_type"] == "knockout"])]),
        "leaders": _leaders(ds, [season_id]),
        "fixtures": {"available": False, "reason": FIXTURES_UNAVAILABLE},
        "coverage": _season_coverage(m),
        "scope": ds.scope.describe() if ds.scope else None,
    }
    return doc


def _season_coverage(m: pd.DataFrame) -> dict:
    if m.empty:
        return {"status": "unavailable", "label": COVERAGE_LABELS["unavailable"], "matches": 0}
    levels = sorted({int(x) for x in m["data_level"].dropna()})
    status = _LEVEL_STATUS.get(levels[0], "metadata") if len(levels) == 1 else "mixed"
    return {"status": status, "label": COVERAGE_LABELS[status], "matches": int(len(m)),
            "data_levels": levels}


def results(base: Dataset, comp_id: int, season_id: int, limit: int, offset: int) -> dict:
    m = base.matches[(base.matches["competition_id"] == comp_id) & (base.matches["season_id"] == season_id)]
    rows = match_rows(base, m)
    return {"total": len(rows), "items": rows[offset: offset + limit], "limit": limit, "offset": offset}


def statistics(base: Dataset, comp_id: int, season_id: int, limit: int) -> dict:
    ds = store.scoped(store.resolve_scope(base, [base.competitions.at[comp_id, "slug"]]), base)
    if ds.deliveries.empty:
        return {"available": False, "reason": "No ball-by-ball data for this season."}
    f = Filters(season_ids=[season_id])
    return {"available": True, "leaderboards": overview.leaderboards(ds, f, limit),
            "summary": overview.summary(ds, f)}


def countries(base: Dataset) -> List[dict]:
    c = base.registry.get("countries")
    if c is None or c.empty:
        return []
    comps = base.competitions
    counts = comps.groupby("country_id").size() if not comps.empty else pd.Series(dtype=int)
    return [
        {"id": int(r["id"]), "code": r["short_code"], "name": r["name"], "flag": _none(r["flag"]),
         "cricket_board": _none(r["cricket_board"]), "competitions": int(counts.get(r["id"], 0))}
        for _, r in c.sort_values("name").iterrows()
    ]


def sources(base: Dataset) -> List[dict]:
    src, sd = base.registry.get("sources"), base.registry.get("source_datasets")
    if src is None or src.empty:
        return []
    out = []
    for _, s in src.iterrows():
        datasets = sd[sd["source_id"] == s["id"]] if sd is not None and not sd.empty else sd
        out.append({
            "slug": s["slug"], "name": s["name"], "url": s["url"], "licence": s["licence"],
            "attribution": s["attribution"], "data_level": int(s["data_level"]),
            "update_frequency": s["update_frequency"], "limitations": s["limitations"],
            "checked_on": str(s["checked_on"]) if _none(s["checked_on"]) else None,
            "datasets": [{"key": d["key"], "name": d["name"], "url": d["url"],
                          "published_matches": _none(d["published_matches"]),
                          "withheld_matches": _none(d["withheld_matches"])}
                         for _, d in datasets.iterrows()] if datasets is not None else [],
        })
    return out


def entity_competitions(base: Dataset, *, player_id: Optional[str] = None,
                        team_id: Optional[int] = None) -> List[dict]:
    """Competitions a player or team appears in, busiest first.

    Lets a profile offer a competition switcher instead of silently pooling
    records across competitions, formats or genders.
    """
    m = base.matches
    if m.empty:
        return []
    if player_id is not None:
        ids = base.squads.loc[base.squads["player_id"] == player_id, "match_id"]
        m = m[m["id"].isin(ids)]
    elif team_id is not None:
        m = m[(m["team1_id"] == team_id) | (m["team2_id"] == team_id)]
    if m.empty:
        return []
    g = m.groupby("competition_id").agg(matches=("id", "nunique"), first=("date", "min"),
                                         last=("date", "max"), format=("match_type", "first"))
    comps = base.competitions
    out = [{
        "id": int(cid), "slug": comps.at[cid, "slug"], "name": comps.at[cid, "name"],
        "short_name": _none(comps.at[cid, "short_name"]), "gender": comps.at[cid, "gender"],
        "type": comps.at[cid, "competition_type"], "format": r["format"],
        "matches": int(r["matches"]), "first_match": r["first"].date().isoformat(),
        "last_match": r["last"].date().isoformat(),
    } for cid, r in g.iterrows()]
    return sorted(out, key=lambda x: -x["matches"])


def shared_competitions(base: Dataset, player_ids: List[str]) -> List[dict]:
    """Competitions every one of these players has a record in, busiest first.

    A comparison needs common ground: two players are only comparable inside a
    competition they have both played. ``matches`` on each option is the
    SMALLEST of the players' match counts there, because a side-by-side is
    only as deep as the thinnest record in it — quoting the larger number
    would advertise a sample the comparison does not have.

    An empty list means these players share no competition. That is an
    answer, not a failure: nothing honest can be put side by side.
    """
    if not player_ids:
        return []
    per = [{c["slug"]: c for c in entity_competitions(base, player_id=pid)} for pid in player_ids]
    common = set(per[0]).intersection(*(set(d) for d in per[1:]))
    out = [dict(per[0][slug], matches=min(d[slug]["matches"] for d in per)) for slug in common]
    return sorted(out, key=lambda x: -x["matches"])


def global_summary(base: Dataset, recent: int = 10) -> dict:
    """Totals across every competition, for the home page.

    Counts are taken from the data (matches, squads), never from registry
    tables, and they never add statistics across competitions: they say how
    much cricket STRYK holds, not anyone's combined record.
    """
    comps = base.competitions
    m = base.matches
    if comps.empty:
        return {"competitions": {"catalogued": 0, "with_data": 0}, "matches": 0}
    with_data = sorted(set(m["competition_id"].dropna().astype(int))) if not m.empty else []
    cards = [card(base, cid) for cid in with_data]
    # Most prominent first, then whichever played most recently (stable sort).
    cards.sort(key=lambda c: c["coverage"].get("last_match") or "", reverse=True)
    cards.sort(key=rank)

    by_type: Dict[str, dict] = {}
    for cid, c in comps.iterrows():
        t = by_type.setdefault(c["competition_type"], {"catalogued": 0, "with_data": 0})
        t["catalogued"] += 1
        t["with_data"] += int(cid in with_data)
    women_ids = set(comps.index[comps["gender"] == "WOMEN"])
    gender_of = m["competition_id"].map(comps["gender"]) if not m.empty else m

    latest = m.sort_values("date", ascending=False).head(recent) if not m.empty else m
    results = match_rows(base, latest)
    for row, cid in zip(results, latest.sort_values(["date", "match_number"], ascending=[False, False])["competition_id"]):
        row["competition"] = {"slug": comps.at[int(cid), "slug"], "name": comps.at[int(cid), "name"],
                              "short_name": _none(comps.at[int(cid), "short_name"])}
    return {
        "competitions": {
            "catalogued": int(len(comps)),
            "with_data": len(with_data),
            "women_with_data": len([c for c in with_data if c in women_ids]),
            "women_catalogued": len(women_ids),
            "by_type": by_type,
        },
        "matches": int(len(m)),
        "matches_by_gender": {g: int(n) for g, n in gender_of.value_counts().items()} if not m.empty else {},
        "deliveries": int(store.ball_totals()["balls"].sum()),
        "players": int(base.squads["player_id"].nunique()) if not base.squads.empty else 0,
        "teams": int(len(set(m["team1_id"]).union(m["team2_id"]))) if not m.empty else 0,
        "formats": sorted(set(m["match_type"])) if not m.empty else [],
        "first_match": m["date"].min().date().isoformat() if not m.empty else None,
        "last_match": m["date"].max().date().isoformat() if not m.empty else None,
        "with_data": cards,
        "latest_results": results,
        "suggestions": _suggestions(base, cards),
    }


#: Names to start a search from, in scorecard form as the data stores them.
#:
#: Deliberately a hand-written list rather than a computed one. The old version
#: took each competition's leading run-scorer, which is a statistic, not an
#: answer to "who will someone type first" - it surfaced the top scorer of a
#: qualifying tournament ahead of players an order of magnitude better known.
#: There is no search log to rank by, so the honest thing is to admit this is
#: an editorial choice and keep it in one obvious place.
#:
#: Weighted towards the audience STRYK is built for, and holding two women's
#: players because the rest of the page treats both games as one record.
#: Reorder freely; a name that no longer resolves is skipped, not fatal.
SUGGESTED_PLAYERS = (
    "Virat Kohli",
    "Rohit Sharma",
    "MS Dhoni",
    "Smriti Mandhana",
    "Jasprit Bumrah",
    "Harmanpreet Kaur",
)


def _suggestions(base: Dataset, cards: List[dict], count: int = 6) -> List[dict]:
    """Well-known players to start a search from.

    Resolves :data:`SUGGESTED_PLAYERS` against both the scorecard name and the
    display name, because a famous player is usually filed under neither
    spelling you would guess: Rohit Sharma is "RG Sharma" on the scorecard,
    while two far less-played cricketers are literally named "Rohit Sharma".

    A name can therefore match several players, and the one meant is the one
    who has played most. Appearances rank them rather than runs, so that a
    bowler is not beaten by a namesake who merely batted more.
    """
    players = base.players
    if players.empty:
        return []
    squads = base.squads
    caps = (squads.groupby("player_id").size()
            if squads is not None and not squads.empty else None)

    out: List[dict] = []
    for wanted in SUGGESTED_PLAYERS:
        hits = players.index[
            (players["name"] == wanted) | (players["display_name"] == wanted)
        ].tolist()
        if not hits:
            continue
        if len(hits) > 1 and caps is not None:
            hits.sort(key=lambda pid: -int(caps.get(pid, 0)))
        pid = hits[0]
        out.append({"id": pid, "name": base.player_name(pid) or pid, "competition": None})
        if len(out) >= count:
            break
    return out
