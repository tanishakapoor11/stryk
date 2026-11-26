"""HTTP surface.

Responses are plain JSON documents assembled by the analytics layer. They are
deliberately not mirrored one-for-one into Pydantic models: the analytical
payloads are deep and change shape as metrics are added, and a second
hand-maintained copy of every nested table would rot. The contract the
frontend depends on is expressed once, in TypeScript, in frontend/types.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.analytics import auction as auction_service
from app.analytics import competitions as competition_service
from app.analytics import matchups as matchup_service
from app.analytics import names as name_service
from app.analytics import overview as overview_service
from app.analytics import players as player_service
from app.analytics import store
from app.analytics import teams as team_service
from app.analytics.constants import METRIC_DEFINITIONS, PHASE_DEFINITIONS, PHASE_ORDER, QUALIFICATION
from app.api.deps import filter_params, scope_params
from app.analytics.store import Filters, ScopeError

router = APIRouter(prefix="/api")


NO_DATA = "No data has been ingested yet. Run scripts/fetch_cricsheet.py then scripts/ingest.py."


def _base():
    """The whole database: for discovery, search and catalogue views."""
    ds = store.get()
    if ds.competitions.empty and ds.matches.empty:
        raise HTTPException(503, NO_DATA)
    return ds


def _ds(competition: Optional[List[str]] = None):
    """A dataset scoped to one competition set (default: the default competition).

    Every statistical endpoint goes through here, so no analysis can pool
    deliveries across competitions of different genders or formats.
    """
    base = store.get()
    if base.matches.empty:
        raise HTTPException(503, NO_DATA)
    try:
        return store.scoped(store.resolve_scope(base, competition), base)
    except ScopeError as exc:
        raise HTTPException(exc.status, str(exc)) from None


def _entity_scope(competition, *, player_id=None, team_id=None):
    """Explicit scope if given; otherwise the entity's busiest competition."""
    if competition:
        return competition, None
    options = competition_service.entity_competitions(store.get(), player_id=player_id, team_id=team_id)
    return ([options[0]["slug"]] if options else None), options


# ---------------------------------------------------------------- meta
@router.get("/meta/seasons", tags=["meta"])
def seasons(competition: Optional[List[str]] = Depends(scope_params)):
    ds = _ds(competition)
    rows = ds.matches.groupby("season").agg(matches=("id", "nunique")).reset_index()
    return [{"season": int(r.season), "matches": int(r.matches)} for r in rows.itertuples()]


@router.get("/meta/teams", tags=["meta"])
def teams(competition: Optional[List[str]] = Depends(scope_params)):
    return team_service.list_teams(_ds(competition))


@router.get("/meta/venues", tags=["meta"])
def venues(competition: Optional[List[str]] = Depends(scope_params)):
    ds = _ds(competition)
    counts = ds.matches.groupby("venue_id").size()
    return [
        {"id": int(vid), "name": row["name"], "city": row["city"],
         "matches": int(counts.get(vid, 0))}
        for vid, row in ds.venues.iterrows()
        if counts.get(vid, 0)
    ]


@router.get("/meta/metrics", tags=["meta"])
def metric_definitions(competition: Optional[List[str]] = Depends(scope_params)):
    """Formulas and qualification thresholds, served to the UI tooltips."""
    return {
        "metrics": METRIC_DEFINITIONS,
        "qualification": QUALIFICATION,
        "phases": {"order": PHASE_ORDER, "definitions": PHASE_DEFINITIONS},
        "data_availability": {
            "bowling_style_splits": player_service.BOWLING_STYLE_DATA_AVAILABLE,
            "overseas_status": team_service.OVERSEAS_DATA_AVAILABLE,
            "auction_prices": auction_service.load_prices(_ds(competition)) is not None,
        },
    }


@router.get("/search", tags=["meta"])
def global_search(q: str = Query(..., min_length=2), limit: int = Query(12, le=50)):
    """Ranked search over players and teams.

    Players match on either name form - "Shreyas", "Iyer", "Shreyas Iyer" and
    "SS Iyer" all find the same player - and are ordered by match quality then
    by appearances, so the player a reader almost certainly meant comes first.
    See app/analytics/names.py.
    """
    ds = _base()
    ql = name_service.normalise(q)
    out = [
        {
            "type": "player",
            "id": hit["id"],
            "name": hit["name"],
            "secondary": hit["scorecard_name"] if hit["scorecard_name"] != hit["name"] else None,
            "detail": f"{hit['appearances']} matches",
            "href": f"/players/{hit['id']}",
        }
        for hit in name_service.search(ds, q, limit=limit)
    ]
    for t in team_service.list_teams(ds):
        haystack = name_service.normalise(f"{t['name']} {t['short_name'] or ''} {' '.join(t['aliases'])}")
        if ql and ql in haystack:
            out.append({"type": "team", "id": t["id"], "name": t["name"],
                        "secondary": t["short_name"], "detail": f"{t['matches']} matches",
                        "href": f"/teams/{t['id']}"})
    for c in competition_service.directory(ds, q=q, limit=6)["items"]:
        out.append({"type": "competition", "id": c["slug"], "name": c["name"],
                    "secondary": c["short_name"], "detail": c["coverage"]["label"],
                    "href": f"/competitions/{c['slug']}"})
    seasons = [
        {"type": "season", "id": f"{s['slug']}/{competition_service.season_slug(s['season'])}",
         "name": f"{s['competition']} {s['season']}", "secondary": s["competition"],
         "detail": f"{s['matches']} matches",
         "href": f"/competitions/{s['slug']}/{competition_service.season_slug(s['season'])}"}
        for s in competition_service.search_seasons(ds, q, limit=6)
    ]
    # A query carrying a year names one edition, so that edition leads: a
    # reader who typed "asia cup 2023" wants the 2023 tournament, not the
    # competition's landing page or a player whose name happens to match.
    out = seasons + out if competition_service.names_a_year(q) else out + seasons

    # An exactly named competition leads whatever else matched. Player names
    # are searched by substring, so "ipl" otherwise returns three players
    # called Shipley, Chipli and Samantray before the Indian Premier League.
    def names_exactly(hit) -> bool:
        if hit["type"] not in ("competition", "season"):
            return False
        return ql in {name_service.normalise(str(hit["id"])),
                      name_service.normalise(hit["name"]),
                      name_service.normalise(hit["secondary"] or "")}

    exact = [h for h in out if names_exactly(h)]
    if exact:
        rest = [h for h in out if not names_exactly(h)]
        out = exact + rest
    return out[: limit + 12]


@router.get("/sitemap", tags=["meta"])
def sitemap():
    """Every indexable entity, for the frontend's sitemap.xml.

    One call rather than one per competition: this reads only the reference
    tables, which are in memory already, and never touches the ball table.

    Players are returned with their appearance count so the sitemap can leave
    out one-match entries - thousands of near-empty pages are worth less to a
    search engine than the few hundred people actually look for.
    """
    ds = _base()
    comps = ds.competitions
    seasons, competitions = [], []
    for cid, c in comps.iterrows():
        m = ds.matches[ds.matches["competition_id"] == cid] if not ds.matches.empty else ds.matches
        if m.empty:
            continue
        last = m["date"].max().date().isoformat()
        competitions.append({"slug": c["slug"], "last_match": last})
        rows = ds.seasons[ds.seasons["competition_id"] == cid] if not ds.seasons.empty else ds.seasons
        for sid, s in rows.iterrows():
            sm = m[m["season_id"] == sid]
            if sm.empty:
                continue
            seasons.append({"competition": c["slug"],
                            "season": competition_service.season_slug(str(s["name"])),
                            "last_match": sm["date"].max().date().isoformat()})
    played = (ds.squads.groupby("player_id")["match_id"].nunique()
              if not ds.squads.empty else None)
    players = ([{"id": pid, "matches": int(n)} for pid, n in played.items()]
               if played is not None else [])
    teams = [{"id": int(tid)} for tid in sorted(set(ds.matches["team1_id"]).union(
        ds.matches["team2_id"]))] if not ds.matches.empty else []
    return {"competitions": competitions, "seasons": seasons,
            "teams": teams, "players": players}


# ---------------------------------------------------------------- overview
@router.get("/overview", tags=["overview"])
def overview(
    f: Filters = Depends(filter_params),
    limit: int = Query(10, ge=3, le=50),
    competition: Optional[List[str]] = Depends(scope_params),
):
    ds = _ds(competition)
    return {
        "scope": ds.scope.describe(),
        "coverage": competition_service.scope_coverage(ds),
        "summary": overview_service.summary(ds, f),
        "leaderboards": overview_service.leaderboards(ds, f, limit),
        "trends": overview_service.season_trends(ds, f),
        "distribution": overview_service.performance_distribution(ds, f),
        "insights": overview_service.insights(ds, f),
        "featured_innings": overview_service.featured_innings(ds, f),
        "filters": f.describe(),
    }


@router.get("/insights", tags=["overview"])
def insights(
    f: Filters = Depends(filter_params),
    count: int = Query(4, ge=1, le=10),
    competition: Optional[List[str]] = Depends(scope_params),
):
    return overview_service.insights(_ds(competition), f, count)


# ---------------------------------------------------------------- players
@router.get("/players", tags=["players"])
def list_players(
    f: Filters = Depends(filter_params),
    q: Optional[str] = Query(None, description="Name search"),
    role: Optional[str] = Query(None, description="Batter | Bowler | All-rounder"),
    sort: str = Query("runs"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    competition: Optional[List[str]] = Depends(scope_params),
):
    ds = _ds(competition)
    result = player_service.directory(
        ds, f, search=q, role=role, sort=sort, order=order, limit=limit, offset=offset
    )
    result["scope"] = ds.scope.describe()
    return result


@router.get("/players/{player_id}", tags=["players"])
def player_profile(
    player_id: str,
    f: Filters = Depends(filter_params),
    competition: Optional[List[str]] = Depends(scope_params),
):
    """A player's record within one competition scope.

    Without ``competition`` the scope is the competition the player has played
    most in, and ``competitions`` lists every other one so the UI can switch.
    Records are never pooled across competitions of different gender or format.
    """
    scope, options = _entity_scope(competition, player_id=player_id)
    ds = _ds(scope)
    result = player_service.profile(ds, player_id, f)
    if result is None:
        raise HTTPException(404, f"No player with id {player_id!r}")
    result["scope"] = ds.scope.describe()
    result["competitions"] = options if options is not None else competition_service.entity_competitions(
        store.get(), player_id=player_id)
    return result


@router.get("/players/{player_id}/matchups", tags=["matchups"])
def player_matchups(
    player_id: str,
    as_role: str = Query("batter", pattern="^(batter|bowler)$"),
    f: Filters = Depends(filter_params),
    limit: int = Query(15, ge=1, le=60),
    competition: Optional[List[str]] = Depends(scope_params),
):
    ds = _ds(_entity_scope(competition, player_id=player_id)[0])
    if player_id not in ds.players.index:
        raise HTTPException(404, f"No player with id {player_id!r}")
    return matchup_service.frequent_opponents(ds, player_id, as_role, f, limit)


@router.get("/compare", tags=["players"])
def compare(
    players: List[str] = Query(..., alias="player", min_length=1),
    f: Filters = Depends(filter_params),
    competition: Optional[List[str]] = Depends(scope_params),
):
    """Side-by-side profiles on an identical sample. The UI decides what is
    meaningful; the API never declares a winner.

    Without an explicit ``competition`` the scope is the busiest competition
    every selected player has played in, not the site-wide default: comparing
    an IPL record against a blank IPL record because one of the two has never
    played there is not a comparison. ``competitions`` lists the rest of the
    common ground so the UI can switch, and is empty when there is none.
    """
    ids = players[:4]
    options = competition_service.shared_competitions(store.get(), ids)
    scope = competition or ([options[0]["slug"]] if options else None)
    ds = _ds(scope)
    out = []
    for pid in ids:
        profile = player_service.profile(ds, pid, f)
        if profile is None:
            # Reachable only by a hand-written competition= in the URL: the
            # switcher never offers a competition one of them has not played.
            if pid in store.get().players.index:
                raise HTTPException(422, f"{pid!r} has no record in this competition")
            raise HTTPException(404, f"No player with id {pid!r}")
        out.append(profile)
    return {"players": out, "filters": f.describe(), "scope": ds.scope.describe(),
            "competitions": options}


# ---------------------------------------------------------------- matchups
@router.get("/matchup", tags=["matchups"])
def matchup(
    batter: str = Query(...),
    bowler: str = Query(...),
    f: Filters = Depends(filter_params),
    competition: Optional[List[str]] = Depends(scope_params),
):
    result = matchup_service.head_to_head(_ds(competition), batter, bowler, f)
    if result is None:
        raise HTTPException(404, "Unknown batter or bowler id")
    return result


# ---------------------------------------------------------------- teams
@router.get("/teams", tags=["teams"])
def team_index(competition: Optional[List[str]] = Depends(scope_params)):
    return team_service.list_teams(_ds(competition))


@router.get("/teams/{team_id}", tags=["teams"])
def team_profile(
    team_id: int,
    f: Filters = Depends(filter_params),
    competition: Optional[List[str]] = Depends(scope_params),
):
    scope, options = _entity_scope(competition, team_id=team_id)
    ds = _ds(scope)
    result = team_service.profile(ds, team_id, f)
    if result is None:
        raise HTTPException(404, f"No team with id {team_id}")
    result["scope"] = ds.scope.describe()
    result["competitions"] = options if options is not None else competition_service.entity_competitions(
        store.get(), team_id=team_id)
    return result


# ---------------------------------------------------------------- auction
@router.get("/auction/pool", tags=["auction"])
def auction_pool(
    f: Filters = Depends(filter_params),
    q: Optional[str] = Query(None, description="Name search"),
    role: Optional[str] = Query(None, description="Batter | Bowler | All-rounder"),
    sort: str = Query("batting_impact"),
    limit: int = Query(60, ge=1, le=200),
    competition: Optional[List[str]] = Depends(scope_params),
):
    """Candidate pool scored against the league rate for the same deliveries.

    The impact figures are analytical measures of on-field contribution. They
    are not valuations. Price data, when the response says it is available,
    comes from an operator-supplied file and never from a model.
    """
    result = auction_service.pool(_ds(competition), f, role=role, search=q, sort=sort, limit=limit)
    result["requirements"] = auction_service.squad_requirements()
    return result


# ---------------------------------------------------------- competitions
def _competition_id(key: str) -> int:
    cid = competition_service.find(_base(), key)
    if cid is None:
        raise HTTPException(404, f"No competition {key!r}")
    return cid


def _season_id(cid: int, key: str) -> int:
    sid = competition_service.find_season(_base(), cid, key)
    if sid is None:
        raise HTTPException(404, f"No season {key!r} in this competition")
    return sid


@router.get("/summary", tags=["competitions"])
def global_summary(recent: int = Query(10, ge=1, le=50)):
    """How much cricket STRYK holds, across every competition (home page)."""
    return competition_service.global_summary(_base(), recent)


@router.get("/countries", tags=["competitions"])
def countries():
    return competition_service.countries(_base())


@router.get("/sources", tags=["competitions"])
def sources():
    """The source coverage registry: licences, update frequency, datasets."""
    return competition_service.sources(_base())


@router.get("/competitions", tags=["competitions"])
def competitions(
    q: Optional[str] = Query(None, description="Name, country or governing body"),
    type: Optional[List[str]] = Query(None, description="INTERNATIONAL, ICC_TOURNAMENT, DOMESTIC, FRANCHISE_LEAGUE, REGIONAL, OTHER"),
    gender: Optional[str] = Query(None, pattern="^(MEN|WOMEN|MIXED|UNKNOWN)$"),
    country: Optional[str] = Query(None, description="Country code, e.g. IND"),
    format: Optional[str] = Query(None, description="T20, ODI, Test, ..."),
    season_status: Optional[str] = Query(None, pattern="^(upcoming|in_progress|completed|unknown)$"),
    coverage: Optional[List[str]] = Query(None, description="Coverage status, e.g. ball_by_ball"),
    season: Optional[int] = Query(None, description="Has a season starting in this year"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return competition_service.directory(
        _base(), q=q, types=type, gender=gender, country=country, fmt=format,
        season_status=season_status, coverage_status=coverage, season_year=season,
        limit=limit, offset=offset,
    )


@router.get("/competitions/{key}", tags=["competitions"])
def competition_detail(key: str):
    return competition_service.competition(_base(), _competition_id(key))


@router.get("/competitions/{key}/seasons", tags=["competitions"])
def competition_seasons(key: str):
    return competition_service.competition(_base(), _competition_id(key))["seasons"]


@router.get("/competitions/{key}/seasons/{season}", tags=["competitions"])
def season_detail(key: str, season: str):
    cid = _competition_id(key)
    return competition_service.season(_base(), cid, _season_id(cid, season))


@router.get("/competitions/{key}/seasons/{season}/standings", tags=["competitions"])
def season_standings(key: str, season: str):
    cid = _competition_id(key)
    return competition_service.season(_base(), cid, _season_id(cid, season))["standings"]


@router.get("/competitions/{key}/seasons/{season}/fixtures", tags=["competitions"])
def season_fixtures(key: str, season: str):
    cid = _competition_id(key)
    _season_id(cid, season)
    return {"available": False, "reason": competition_service.FIXTURES_UNAVAILABLE, "items": []}


@router.get("/competitions/{key}/seasons/{season}/results", tags=["competitions"])
def season_results(
    key: str, season: str,
    limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
):
    cid = _competition_id(key)
    return competition_service.results(_base(), cid, _season_id(cid, season), limit, offset)


@router.get("/competitions/{key}/seasons/{season}/statistics", tags=["competitions"])
def season_statistics(key: str, season: str, limit: int = Query(10, ge=3, le=50)):
    cid = _competition_id(key)
    return competition_service.statistics(_base(), cid, _season_id(cid, season), limit)


# ---------------------------------------------------------------- admin
@router.post("/admin/reload", tags=["admin"])
def reload_dataset():
    """Re-read the fact table after an ingestion run."""
    ds = store.reload()
    return {"status": "reloaded", "matches": int(len(ds.matches)),
            "deliveries": int(store.ball_totals()["balls"].sum()),
            "loaded_at": ds.loaded_at.isoformat() + "Z"}
