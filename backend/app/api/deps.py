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


def filter_params(
    season: Optional[List[int]] = Query(None, description="Season year, repeatable"),
    team: Optional[List[int]] = Query(None, description="Team id, repeatable"),
    opposition: Optional[List[int]] = Query(None),
    venue: Optional[List[int]] = Query(None),
    phase: Optional[List[str]] = Query(None, description=f"One of {PHASE_ORDER}"),
    innings: Optional[int] = Query(None, ge=1, le=4),
    chasing: Optional[bool] = Query(None, description="true = batting second"),
    date_from: Optional[dt.date] = Query(None),
    date_to: Optional[dt.date] = Query(None),
    include_super_over: bool = Query(False),
) -> Filters:
    bad = [p for p in (phase or []) if p not in PHASE_ORDER]
    if bad:
        from fastapi import HTTPException

        raise HTTPException(422, f"unknown phase(s) {bad}; expected any of {PHASE_ORDER}")
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
    )
