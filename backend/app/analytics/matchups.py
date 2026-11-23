"""Batter vs bowler head-to-head analysis.

Head-to-head samples in T20 are small. Every response carries its sample size
and an explicit reliability verdict so the UI can refuse to overstate a
12-ball record.
"""

from __future__ import annotations

from typing import List, Optional

import pandas as pd

from app.analytics import metrics, store
from app.analytics.constants import QUALIFICATION
from app.analytics.store import Dataset, Filters

RELIABLE = QUALIFICATION["matchup_balls_reliable"]
MINIMUM = QUALIFICATION["matchup_balls_minimum"]


def _verdict(balls: int) -> dict:
    if balls == 0:
        return {"level": "none", "message": "These two have never met in this sample."}
    if balls < MINIMUM:
        return {
            "level": "insufficient",
            "message": f"Only {balls} balls. Far too small a sample to read anything into.",
        }
    if balls < RELIABLE:
        return {
            "level": "indicative",
            "message": (
                f"{balls} balls. Indicative only - a single boundary or dismissal moves these "
                f"numbers substantially. {RELIABLE}+ balls is the threshold Stryk treats as readable."
            ),
        }
    return {
        "level": "readable",
        "message": f"{balls} balls faced - a large enough sample to compare against each player's baseline.",
    }


def head_to_head(ds: Dataset, batter_id: str, bowler_id: str, f: Filters) -> Optional[dict]:
    if batter_id not in ds.players.index or bowler_id not in ds.players.index:
        return None
    dv = store.apply(ds.deliveries, f, team_column="batting_team_id")
    sub = dv[(dv["batter_id"] == batter_id) & (dv["bowler_id"] == bowler_id)]

    balls = int(sub["is_ball_faced"].sum()) if not sub.empty else 0
    runs = int(sub["batter_runs"].sum()) if not sub.empty else 0
    outs = sub[sub["out_player_id"] == batter_id] if not sub.empty else sub
    bowler_outs = int(outs["out_credited_to_bowler"].sum()) if not outs.empty else 0
    dots = int(sub["is_batter_dot"].sum()) if not sub.empty else 0
    fours = int(sub["is_four"].sum()) if not sub.empty else 0
    sixes = int(sub["is_six"].sum()) if not sub.empty else 0

    # Each player's baseline over the same filter, for context.
    bat_base = metrics.batting_summary(dv[dv["batter_id"] == batter_id])
    bowl_base = metrics.bowling_summary(dv[dv["bowler_id"] == bowler_id])

    by_phase = []
    if not sub.empty:
        for phase, grp in sub.groupby("phase"):
            b = int(grp["is_ball_faced"].sum())
            by_phase.append({
                "phase": phase,
                "balls": b,
                "runs": int(grp["batter_runs"].sum()),
                "dismissals": int((grp["out_player_id"] == batter_id).sum()),
                "strike_rate": metrics.div(int(grp["batter_runs"].sum()) * 100, b),
                "dot_pct": metrics.div(int(grp["is_batter_dot"].sum()) * 100, b),
            })

    by_season = []
    if not sub.empty:
        for season, grp in sub.groupby("season"):
            b = int(grp["is_ball_faced"].sum())
            by_season.append({
                "season": int(season),
                "balls": b,
                "runs": int(grp["batter_runs"].sum()),
                "dismissals": int((grp["out_player_id"] == batter_id).sum()),
                "strike_rate": metrics.div(int(grp["batter_runs"].sum()) * 100, b),
            })

    dismissal_log = []
    if not outs.empty:
        for _, r in outs.iterrows():
            dismissal_log.append({
                "date": r["date"].date().isoformat() if pd.notna(r["date"]) else None,
                "season": int(r["season"]),
                "kind": r["out_kind"],
                "phase": r["phase"],
                "over": int(r["over"]) + 1,
                "credited_to_bowler": bool(r["out_credited_to_bowler"]),
            })

    return {
        "batter": {"id": batter_id, "name": ds.player_name(batter_id)},
        "bowler": {"id": bowler_id, "name": ds.player_name(bowler_id)},
        "filters": f.describe(),
        "sample": {"balls": balls, "innings": int(sub["innings_id"].nunique()) if not sub.empty else 0,
                   "matches": int(sub["match_id"].nunique()) if not sub.empty else 0},
        "reliability": _verdict(balls),
        "summary": {
            "balls": balls,
            "runs": runs,
            "dismissals": int(len(outs)),
            "bowler_dismissals": bowler_outs,
            "strike_rate": metrics.div(runs * 100, balls),
            "average": metrics.div(runs, len(outs)),
            "dot_pct": metrics.div(dots * 100, balls),
            "boundary_pct": metrics.div((fours + sixes) * 100, balls),
            "fours": fours,
            "sixes": sixes,
            "balls_per_dismissal": metrics.div(balls, len(outs)),
        },
        "baseline": {
            "batter": metrics.records(bat_base)[0] if not bat_base.empty else None,
            "bowler": metrics.records(bowl_base)[0] if not bowl_base.empty else None,
        },
        "by_phase": by_phase,
        "by_season": by_season,
        "dismissal_log": dismissal_log,
        "notes": {
            "dismissals": "Every dismissal of the batter off this bowler's deliveries, including run-outs.",
            "bowler_dismissals": "The subset credited to the bowler's figures.",
            "thresholds": {"minimum_balls": MINIMUM, "reliable_balls": RELIABLE},
        },
    }


def frequent_opponents(ds: Dataset, player_id: str, as_role: str = "batter",
                       f: Optional[Filters] = None, limit: int = 15) -> List[dict]:
    """The opponents a player has faced most - the entry point for match-ups."""
    f = f or Filters()
    dv = store.apply(ds.deliveries, f)
    if dv.empty:
        return []
    if as_role == "batter":
        sub, key, out_key = dv[dv["batter_id"] == player_id], "bowler_id", "out_player_id"
    else:
        sub, key, out_key = dv[dv["bowler_id"] == player_id], "batter_id", "out_player_id"
    if sub.empty:
        return []
    rows = []
    for opp, grp in sub.groupby(key):
        balls = int(grp["is_ball_faced"].sum())
        if balls < MINIMUM:
            continue
        runs = int(grp["batter_runs"].sum())
        target = player_id if as_role == "batter" else opp
        outs = int((grp[out_key] == target).sum())
        rows.append({
            "opponent_id": opp,
            "opponent_name": ds.player_name(opp),
            "balls": balls,
            "runs": runs,
            "dismissals": outs,
            "strike_rate": metrics.div(runs * 100, balls),
            "average": metrics.div(runs, outs),
            "reliability": _verdict(balls)["level"],
        })
    rows.sort(key=lambda r: -r["balls"])
    return rows[:limit]
