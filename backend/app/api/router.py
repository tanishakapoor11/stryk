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
from app.analytics import matchups as matchup_service
from app.analytics import names as name_service
from app.analytics import overview as overview_service
from app.analytics import players as player_service
from app.analytics import store
from app.analytics import teams as team_service
from app.analytics.constants import METRIC_DEFINITIONS, PHASE_DEFINITIONS, PHASE_ORDER, QUALIFICATION
from app.api.deps import filter_params
from app.analytics.store import Filters

router = APIRouter(prefix="/api")


def _ds():
    ds = store.get()
    if ds.is_empty:
        raise HTTPException(
            503,
            "No data has been ingested yet. Run scripts/fetch_cricsheet.py then scripts/ingest.py.",
        )
    return ds


# ---------------------------------------------------------------- meta
@router.get("/meta/seasons", tags=["meta"])
def seasons():
    ds = _ds()
    rows = ds.matches.groupby("season").agg(matches=("id", "nunique")).reset_index()
    return [{"season": int(r.season), "matches": int(r.matches)} for r in rows.itertuples()]


@router.get("/meta/teams", tags=["meta"])
def teams():
    return team_service.list_teams(_ds())


@router.get("/meta/venues", tags=["meta"])
def venues():
    ds = _ds()
    counts = ds.matches.groupby("venue_id").size()
    return [
        {"id": int(vid), "name": row["name"], "city": row["city"],
         "matches": int(counts.get(vid, 0))}
        for vid, row in ds.venues.iterrows()
    ]


@router.get("/meta/metrics", tags=["meta"])
def metric_definitions():
    """Formulas and qualification thresholds, served to the UI tooltips."""
    return {
        "metrics": METRIC_DEFINITIONS,
        "qualification": QUALIFICATION,
        "phases": {"order": PHASE_ORDER, "definitions": PHASE_DEFINITIONS},
        "data_availability": {
            "bowling_style_splits": player_service.BOWLING_STYLE_DATA_AVAILABLE,
            "overseas_status": team_service.OVERSEAS_DATA_AVAILABLE,
            "auction_prices": auction_service.load_prices(_ds()) is not None,
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
    ds = _ds()
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
    return out[: limit + 6]


# ---------------------------------------------------------------- overview
@router.get("/overview", tags=["overview"])
def overview(f: Filters = Depends(filter_params), limit: int = Query(10, ge=3, le=50)):
    ds = _ds()
    return {
        "summary": overview_service.summary(ds, f),
        "leaderboards": overview_service.leaderboards(ds, f, limit),
        "trends": overview_service.season_trends(ds, f),
        "distribution": overview_service.performance_distribution(ds, f),
        "insights": overview_service.insights(ds, f),
        "featured_innings": overview_service.featured_innings(ds, f),
        "filters": f.describe(),
    }


@router.get("/insights", tags=["overview"])
def insights(f: Filters = Depends(filter_params), count: int = Query(4, ge=1, le=10)):
    return overview_service.insights(_ds(), f, count)


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
):
    return player_service.directory(
        _ds(), f, search=q, role=role, sort=sort, order=order, limit=limit, offset=offset
    )


@router.get("/players/{player_id}", tags=["players"])
def player_profile(player_id: str, f: Filters = Depends(filter_params)):
    result = player_service.profile(_ds(), player_id, f)
    if result is None:
        raise HTTPException(404, f"No player with id {player_id!r}")
    return result


@router.get("/players/{player_id}/matchups", tags=["matchups"])
def player_matchups(
    player_id: str,
    as_role: str = Query("batter", pattern="^(batter|bowler)$"),
    f: Filters = Depends(filter_params),
    limit: int = Query(15, ge=1, le=60),
):
    ds = _ds()
    if player_id not in ds.players.index:
        raise HTTPException(404, f"No player with id {player_id!r}")
    return matchup_service.frequent_opponents(ds, player_id, as_role, f, limit)


@router.get("/compare", tags=["players"])
def compare(
    players: List[str] = Query(..., alias="player", min_length=1),
    f: Filters = Depends(filter_params),
):
    """Side-by-side profiles. The UI decides what is meaningful; the API never
    declares a winner."""
    ds = _ds()
    out = []
    for pid in players[:4]:
        profile = player_service.profile(ds, pid, f)
        if profile is None:
            raise HTTPException(404, f"No player with id {pid!r}")
        out.append(profile)
    return {"players": out, "filters": f.describe()}


# ---------------------------------------------------------------- matchups
@router.get("/matchup", tags=["matchups"])
def matchup(
    batter: str = Query(...),
    bowler: str = Query(...),
    f: Filters = Depends(filter_params),
):
    result = matchup_service.head_to_head(_ds(), batter, bowler, f)
    if result is None:
        raise HTTPException(404, "Unknown batter or bowler id")
    return result


# ---------------------------------------------------------------- teams
@router.get("/teams", tags=["teams"])
def team_index():
    return team_service.list_teams(_ds())


@router.get("/teams/{team_id}", tags=["teams"])
def team_profile(team_id: int, f: Filters = Depends(filter_params)):
    result = team_service.profile(_ds(), team_id, f)
    if result is None:
        raise HTTPException(404, f"No team with id {team_id}")
    return result


# ---------------------------------------------------------------- auction
@router.get("/auction/pool", tags=["auction"])
def auction_pool(
    f: Filters = Depends(filter_params),
    q: Optional[str] = Query(None, description="Name search"),
    role: Optional[str] = Query(None, description="Batter | Bowler | All-rounder"),
    sort: str = Query("batting_impact"),
    limit: int = Query(60, ge=1, le=200),
):
    """Candidate pool scored against the league rate for the same deliveries.

    The impact figures are analytical measures of on-field contribution. They
    are not valuations. Price data, when the response says it is available,
    comes from an operator-supplied file and never from a model.
    """
    result = auction_service.pool(_ds(), f, role=role, search=q, sort=sort, limit=limit)
    result["requirements"] = auction_service.squad_requirements()
    return result


# ---------------------------------------------------------------- admin
@router.post("/admin/reload", tags=["admin"])
def reload_dataset():
    """Re-read the fact table after an ingestion run."""
    ds = store.reload()
    return {"status": "reloaded", "deliveries": int(len(ds.deliveries)),
            "loaded_at": ds.loaded_at.isoformat() + "Z"}
