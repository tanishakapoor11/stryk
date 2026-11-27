"""Shared query-parameter parsing.

Filters are expressed as URL query parameters so that any analysis in Stryk is
a shareable link - the frontend mirrors the same names in its own routes.
"""

from __future__ import annotations

import datetime as dt
from typing import List, Optional

from fastapi import Query

from app.analytics.constants import PHASE_ORDER
from app.analytics.store import Filters


def scope_params(
    competition: Optional[List[str]] = Query(
        None,
        description=(
            "Competition slug or id, repeatable. Defaults to the configured default "
            "competition. Competitions of different genders or formats cannot be combined."
        ),
    ),
) -> Optional[List[str]]:
    return competition or None


def filter_params(
    season: Optional[List[int]] = Query(None, description="Season year, repeatable"),
    season_id: Optional[List[int]] = Query(None, description="Season id, repeatable"),
    team: Optional[List[int]] = Query(None, description="Team id, repeatable"),
    opposition: Optional[List[int]] = Query(None),
    venue: Optional[List[int]] = Query(None),
    phase: Optional[List[str]] = Query(None, description=f"One of {PHASE_ORDER}"),
    innings: Optional[int] = Query(None, ge=1, le=4),
    chasing: Optional[bool] = Query(None, description="true = batting second"),
    date_from: Optional[dt.date] = Query(None),
    date_to: Optional[dt.date] = Query(None),
    include_super_over: bool = Query(False),
    over_from: Optional[int] = Query(
        None, ge=1, le=100, description="First over of an inclusive range, counting from 1"),
    over_to: Optional[int] = Query(
        None, ge=1, le=100, description="Last over of an inclusive range, counting from 1"),
    target_from: Optional[int] = Query(
        None, ge=1, description="Runs required to win, at least. 180 = a 180+ chase"),
    target_to: Optional[int] = Query(
        None, ge=1, description="Runs required to win, at most"),
    result: Optional[str] = Query(
        None, description="'won' or 'lost', from the filtered side's point of view. "
                          "A tie or an abandoned match is neither."),
) -> Filters:
    from fastapi import HTTPException

    bad = [p for p in (phase or []) if p not in PHASE_ORDER]
    if bad:
        raise HTTPException(422, f"unknown phase(s) {bad}; expected any of {PHASE_ORDER}")
    if over_from is not None and over_to is not None and over_from > over_to:
        raise HTTPException(422, f"over_from ({over_from}) is after over_to ({over_to})")
    if target_from is not None and target_to is not None and target_from > target_to:
        raise HTTPException(422, f"target_from ({target_from}) is above target_to ({target_to})")
    if result is not None and result not in ("won", "lost"):
        raise HTTPException(422, f"unknown result {result!r}; expected 'won' or 'lost'")
    return Filters(
        seasons=season,
        team_ids=team,
        opposition_ids=opposition,
        venue_ids=venue,
        phases=phase,
        innings_number=innings,
        chasing=chasing,
        date_from=date_from,
        date_to=date_to,
        include_super_over=include_super_over,
        season_ids=season_id,
        over_from=over_from,
        over_to=over_to,
        target_from=target_from,
        target_to=target_to,
        result=result,
    )
