"""Batting and bowling aggregations.

Every function here takes an already-filtered delivery frame, so the same code
produces career numbers, a season split, a powerplay split or a head-to-head.
The cricket rules themselves live in :mod:`app.analytics.constants`.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

import numpy as np
import pandas as pd

from app.analytics.constants import PHASE_ORDER
from app.analytics.store import Dataset


def div(num, den):
    """Divide, returning ``None`` rather than 0 when the denominator is empty.

    A batting average of "no dismissals" is not an average of zero, and the
    API must be able to say so. Missing information is never silently 0.
    """
    if den is None or den == 0 or (isinstance(den, float) and np.isnan(den)):
        return None
    val = float(num) / float(den)
    return None if np.isnan(val) else round(val, 2)


def _clean(value):
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def overs_string(legal_balls: int, balls_per_over: int = 6) -> str:
    return f"{legal_balls // balls_per_over}.{legal_balls % balls_per_over}"


# --------------------------------------------------------------------------
# Batting
# --------------------------------------------------------------------------
#: The exact columns ``batting_innings`` and ``bowling_spells`` return. They
#: are declared once so the empty-input path cannot drift from the populated
#: one - a player who never batted must yield an empty table of the right
#: shape, not a different table.
BATTING_INNINGS_COLUMNS = [
    "innings_id", "player_id", "runs", "balls", "fours", "sixes", "dots",
    "match_id", "season", "batting_team_id", "bowling_team_id", "venue_id",
    "is_chase", "out",
]

BOWLING_SPELLS_COLUMNS = [
    "innings_id", "player_id", "balls", "runs", "wickets", "match_id",
    "season", "bowling_team_id", "batting_team_id", "venue_id",
]


def batting_innings(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Per (innings, batter) totals - the basis for averages, 50s and 100s.

    A batter who came to the crease but never faced a ball (run out at the
    non-striker's end) still has an innings, so appearances as non-striker are
    unioned in with zero runs.
    """
    if deliveries.empty:
        # The empty frame must carry exactly the columns the populated path
        # produces: callers read the context columns (opposition, venue, chase)
        # unconditionally, and a narrower frame turns "this player never
        # batted" into a KeyError several layers away.
        return pd.DataFrame(columns=BATTING_INNINGS_COLUMNS)
    g = deliveries.groupby(["innings_id", "batter_id"], sort=False)
    card = g.agg(
        runs=("batter_runs", "sum"),
        balls=("is_ball_faced", "sum"),
        fours=("is_four", "sum"),
        sixes=("is_six", "sum"),
        dots=("is_batter_dot", "sum"),
        match_id=("match_id", "first"),
        season=("season", "first"),
        batting_team_id=("batting_team_id", "first"),
        bowling_team_id=("bowling_team_id", "first"),
        venue_id=("venue_id", "first"),
        is_chase=("is_chase", "first"),
    ).reset_index().rename(columns={"batter_id": "player_id"})

    # Crease appearances that produced no faced ball.
    ns = deliveries[["innings_id", "non_striker_id", "match_id", "season",
                     "batting_team_id", "bowling_team_id", "venue_id", "is_chase"]].rename(
        columns={"non_striker_id": "player_id"}
    ).drop_duplicates(["innings_id", "player_id"])
    known = set(zip(card["innings_id"], card["player_id"]))
    extra = ns[[k not in known for k in zip(ns["innings_id"], ns["player_id"])]].copy()
    if not extra.empty:
        for col in ("runs", "balls", "fours", "sixes", "dots"):
            extra[col] = 0
        card = pd.concat([card, extra[card.columns]], ignore_index=True)

    outs = deliveries.loc[deliveries["out_player_id"].notna(), ["innings_id", "out_player_id"]]
    out_pairs = set(zip(outs["innings_id"], outs["out_player_id"]))
    card["out"] = [p in out_pairs for p in zip(card["innings_id"], card["player_id"])]
    return card


def batting_summary(deliveries: pd.DataFrame, by: str = "batter_id") -> pd.DataFrame:
    """Aggregate batting statistics grouped by ``by`` (default: the batter)."""
    empty_cols = ["player_id", "innings", "runs", "balls", "fours", "sixes", "dots",
                  "outs", "not_outs", "average", "strike_rate", "boundary_pct",
                  "dot_pct", "highest_score", "fifties", "hundreds", "thirties"]
    if deliveries.empty:
        return pd.DataFrame(columns=empty_cols)

    card = batting_innings(deliveries)
    if by == "batter_id":
        key = card["player_id"]
    else:
        key = card[by]
    grouped = card.assign(_k=key).groupby("_k", sort=False)
    out = grouped.agg(
        innings=("innings_id", "nunique"),
        runs=("runs", "sum"),
        balls=("balls", "sum"),
        fours=("fours", "sum"),
        sixes=("sixes", "sum"),
        dots=("dots", "sum"),
        outs=("out", "sum"),
        highest_score=("runs", "max"),
        matches=("match_id", "nunique"),
    )
    out["fifties"] = grouped.apply(
        lambda g: int(((g["runs"] >= 50) & (g["runs"] < 100)).sum()), include_groups=False
    )
    out["hundreds"] = grouped.apply(lambda g: int((g["runs"] >= 100).sum()), include_groups=False)
    out["thirties"] = grouped.apply(
        lambda g: int(((g["runs"] >= 30) & (g["runs"] < 50)).sum()), include_groups=False
    )
    # Highest score should be marked not-out when the best knock was unbeaten.
    best = card.sort_values("runs", ascending=False).assign(_k=key).drop_duplicates("_k")
    out["highest_not_out"] = best.set_index("_k")["out"].map(lambda o: not bool(o))

    out["not_outs"] = out["innings"] - out["outs"]
    out["average"] = [div(r, o) for r, o in zip(out["runs"], out["outs"])]
    out["strike_rate"] = [div(r * 100, b) for r, b in zip(out["runs"], out["balls"])]
    out["boundary_pct"] = [
        div((f + s) * 100, b) for f, s, b in zip(out["fours"], out["sixes"], out["balls"])
    ]
    out["dot_pct"] = [div(d * 100, b) for d, b in zip(out["dots"], out["balls"])]
    out["boundary_runs"] = out["fours"] * 4 + out["sixes"] * 6
    out["boundary_run_pct"] = [
        div(br * 100, r) for br, r in zip(out["boundary_runs"], out["runs"])
    ]
    return out.reset_index().rename(columns={"_k": "player_id"})


# --------------------------------------------------------------------------
# Bowling
# --------------------------------------------------------------------------
def bowling_spells(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Per (innings, bowler) figures - the basis for best figures and hauls."""
    if deliveries.empty:
        return pd.DataFrame(columns=BOWLING_SPELLS_COLUMNS)
    g = deliveries.groupby(["innings_id", "bowler_id"], sort=False)
    return g.agg(
        balls=("is_legal", "sum"),
        runs=("bowler_runs", "sum"),
        wickets=("out_credited_to_bowler", "sum"),
        match_id=("match_id", "first"),
        season=("season", "first"),
        bowling_team_id=("bowling_team_id", "first"),
        batting_team_id=("batting_team_id", "first"),
        venue_id=("venue_id", "first"),
    ).reset_index().rename(columns={"bowler_id": "player_id"})


def bowling_summary(deliveries: pd.DataFrame, by: str = "bowler_id") -> pd.DataFrame:
    cols = ["player_id", "innings", "balls", "overs", "runs", "wickets", "average",
            "economy", "strike_rate", "dot_pct", "four_wicket_hauls", "five_wicket_hauls"]
    if deliveries.empty:
        return pd.DataFrame(columns=cols)

    key_col = "bowler_id" if by == "bowler_id" else by
    g = deliveries.groupby(key_col, sort=False)
    out = g.agg(
        balls=("is_legal", "sum"),
        runs=("bowler_runs", "sum"),
        wickets=("out_credited_to_bowler", "sum"),
        dots=("is_bowler_dot", "sum"),
        fours_conceded=("is_four", "sum"),
        sixes_conceded=("is_six", "sum"),
        wides=("wides", "sum"),
        noballs=("noballs", "sum"),
        innings=("innings_id", "nunique"),
        matches=("match_id", "nunique"),
    )
    spells = bowling_spells(deliveries)
    if by == "bowler_id":
        per_match = spells.groupby(["match_id", "player_id"], sort=False).agg(
            wickets=("wickets", "sum"), runs=("runs", "sum")
        ).reset_index()
        hauls4 = per_match[per_match["wickets"] >= 4].groupby("player_id").size()
        hauls5 = per_match[per_match["wickets"] >= 5].groupby("player_id").size()
        out["four_wicket_hauls"] = hauls4.reindex(out.index).fillna(0).astype(int)
        out["five_wicket_hauls"] = hauls5.reindex(out.index).fillna(0).astype(int)
        best = per_match.sort_values(["wickets", "runs"], ascending=[False, True])
        best = best.drop_duplicates("player_id").set_index("player_id")
        out["best_wickets"] = best["wickets"].reindex(out.index)
        out["best_runs"] = best["runs"].reindex(out.index)
    else:
        out["four_wicket_hauls"] = 0
        out["five_wicket_hauls"] = 0

    out["overs"] = [overs_string(int(b)) for b in out["balls"]]
    out["economy"] = [div(r * 6, b) for r, b in zip(out["runs"], out["balls"])]
    out["average"] = [div(r, w) for r, w in zip(out["runs"], out["wickets"])]
    out["strike_rate"] = [div(b, w) for b, w in zip(out["balls"], out["wickets"])]
    out["dot_pct"] = [div(d * 100, b) for d, b in zip(out["dots"], out["balls"])]
    out["boundary_pct"] = [
        div((f + s) * 100, b)
        for f, s, b in zip(out["fours_conceded"], out["sixes_conceded"], out["balls"])
    ]
    return out.reset_index().rename(columns={key_col: "player_id"})


# --------------------------------------------------------------------------
# Serialisation helpers
# --------------------------------------------------------------------------
def records(df: pd.DataFrame, ds: Optional[Dataset] = None,
            name_col: str = "player_id") -> List[dict]:
    """DataFrame -> JSON-safe list of dicts, with NaN turned into null."""
    if df.empty:
        return []
    out = df.replace({np.nan: None}).to_dict("records")
    for row in out:
        for k, v in list(row.items()):
            row[k] = _clean(v)
        if ds is not None and name_col in row and isinstance(row[name_col], str):
            row.setdefault("player_name", ds.player_name(row[name_col]))
    return out


def phase_split(deliveries: pd.DataFrame, kind: str = "batting") -> List[dict]:
    """Powerplay / middle / death breakdown for a single player's deliveries."""
    fn = batting_summary if kind == "batting" else bowling_summary
    rows = []
    for phase in PHASE_ORDER:
        sub = deliveries[deliveries["phase"] == phase]
        summary = fn(sub)
        base = {"phase": phase}
        if summary.empty:
            rows.append({**base, "balls": 0, "runs": 0})
        else:
            rec = records(summary)[0]
            rec.pop("player_id", None)
            rows.append({**base, **rec})
    return rows
