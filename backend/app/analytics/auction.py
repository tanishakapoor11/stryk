"""Auction intelligence.

Two things are deliberately kept apart here.

*Performance* comes from the ball-by-ball data and is a fact: how many runs a
batter scored above what the league scored off the same number of deliveries,
how many runs a bowler saved against the same yardstick.

*Price* does not exist in Cricsheet. There is no auction figure anywhere in a
match file, and guessing one from performance would turn an analytical opinion
into something that reads like a market fact. So Stryk loads prices from an
optional operator-supplied file and, when that file is absent, reports
`prices_available: false` and the UI disables every price-dependent feature
rather than inventing numbers.

To enable the price features, drop a CSV at data/raw/auction/prices.csv with
the columns:

    player_name,season,price_inr,team,source

`player_id` may be supplied instead of `player_name` when ids are known.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Dict, List, Optional

import pandas as pd

from app.analytics import metrics, names, store
from app.analytics.players import infer_roles
from app.analytics.store import Dataset, Filters
from app.core.config import settings

log = logging.getLogger("stryk.auction")

#: A pool entry needs enough deliveries for its rate statistics to mean
#: anything. These are deliberately lower than the leaderboard thresholds: an
#: auction pool is about finding players, not crowning them.
POOL_QUALIFICATION = {"min_balls_faced": 120, "min_balls_bowled": 120}

PRICE_COLUMNS = {"season", "price_inr"}

METHOD_NOTES = {
    "batting_runs_above_league": {
        "label": "Batting runs above league",
        "formula": "runs - (balls faced x league runs per ball, matched on phase)",
        "notes": (
            "How many more runs the batter scored than the league scored off the same "
            "deliveries in the same phases. Positive is above the league; it is a volume "
            "measure, so a part-time batter with a high strike rate can still score low."
        ),
    },
    "bowling_runs_saved": {
        "label": "Bowling runs saved",
        "formula": "(legal balls x league runs per ball, matched on phase) - runs conceded",
        "notes": (
            "Runs the bowler denied relative to the league rate over the same deliveries "
            "in the same phases. Wickets are reported separately and are not folded in: "
            "converting a wicket into runs requires an assumption Stryk does not make."
        ),
    },
    "per_match": {
        "label": "Per-match impact",
        "formula": "runs above league (or saved) / matches played",
        "notes": "Rate form of the same figure, so a four-season player is comparable to a ten-season one.",
    },
}


# ------------------------------------------------------------------ prices
@lru_cache(maxsize=1)
def _price_path():
    return settings.raw_dir / "auction" / "prices.csv"


def load_prices(ds: Dataset) -> Optional[pd.DataFrame]:
    """Read the optional operator-supplied auction price file.

    Returns None when no usable file is present. A malformed file is logged and
    treated as absent: a half-parsed price table is worse than none.
    """
    path = _price_path()
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001 - operator file, any failure is "absent"
        log.warning("auction price file at %s could not be read: %s", path, exc)
        return None

    missing = PRICE_COLUMNS - set(df.columns)
    if missing:
        log.warning("auction price file is missing column(s) %s; ignoring it", sorted(missing))
        return None

    if "player_id" not in df.columns:
        if "player_name" not in df.columns:
            log.warning("auction price file needs player_id or player_name; ignoring it")
            return None
        by_name = {str(v).strip().lower(): k for k, v in ds.players["name"].items()}
        by_name.update({str(v).strip().lower(): k
                        for k, v in ds.players["display_name"].items()})
        df["player_id"] = df["player_name"].astype(str).str.strip().str.lower().map(by_name)

    unmatched = int(df["player_id"].isna().sum())
    if unmatched:
        log.warning("%d auction price row(s) did not match a known player", unmatched)
    df = df.dropna(subset=["player_id"])
    df["season"] = pd.to_numeric(df["season"], errors="coerce").astype("Int64")
    df["price_inr"] = pd.to_numeric(df["price_inr"], errors="coerce")
    df = df.dropna(subset=["season", "price_inr"])
    return df if not df.empty else None


# ------------------------------------------------------------------ pool
def _league_rate_by_phase(dv: pd.DataFrame, kind: str) -> pd.Series:
    """League runs per ball, per phase, under the current filters.

    Phase-matched rather than global: a death-overs specialist should not be
    compared against a powerplay yardstick. The two yardsticks differ because
    the two sides of the ledger do - a batter is measured against runs off the
    bat, a bowler against the runs actually debited to bowlers.
    """
    if kind == "batting":
        sub = dv[dv["is_ball_faced"]]
        runs_col, ball_col = "batter_runs", "is_ball_faced"
    else:
        sub = dv[dv["is_legal"]]
        runs_col, ball_col = "bowler_runs", "is_legal"
    if sub.empty:
        return pd.Series(dtype=float)
    grouped = sub.groupby("phase").agg(runs=(runs_col, "sum"), balls=(ball_col, "sum"))
    return grouped["runs"] / grouped["balls"]


def _expected(dv: pd.DataFrame, group_col: str, ball_col: str, rates: pd.Series) -> pd.Series:
    """Runs the league would have scored off each player's deliveries."""
    sub = dv[dv[ball_col]]
    if sub.empty or rates.empty:
        return pd.Series(dtype=float)
    weighted = sub["phase"].map(rates).fillna(rates.mean())
    return weighted.groupby(sub[group_col]).sum()


def pool(
    ds: Dataset,
    f: Filters,
    role: Optional[str] = None,
    search: Optional[str] = None,
    sort: str = "batting_impact",
    limit: int = 60,
) -> dict:
    """The candidate pool: every player with a readable sample, scored against
    the league rate for the same deliveries."""
    bat_dv = store.apply(ds.deliveries, f, team_column="batting_team_id")
    bowl_dv = store.apply(ds.deliveries, f, team_column="bowling_team_id")

    bat = metrics.batting_summary(bat_dv).set_index("player_id")
    bowl = metrics.bowling_summary(bowl_dv).set_index("player_id")
    bat_rates = _league_rate_by_phase(bat_dv, "batting")
    bowl_rates = _league_rate_by_phase(bowl_dv, "bowling")

    expected_bat = _expected(bat_dv, "batter_id", "is_ball_faced", bat_rates)
    expected_conceded = _expected(bowl_dv, "bowler_id", "is_legal", bowl_rates)

    roles = infer_roles(ds)
    ids = sorted(set(bat.index) | set(bowl.index))
    df = pd.DataFrame(index=pd.Index(ids, name="player_id"))
    df["name"] = ds.players["display_name"].reindex(df.index)
    df["scorecard_name"] = ds.players["name"].reindex(df.index)
    df["role"] = roles["role"].reindex(df.index)

    df["balls_faced"] = bat["balls"].reindex(df.index).fillna(0)
    df["runs"] = bat["runs"].reindex(df.index).fillna(0)
    df["strike_rate"] = bat["strike_rate"].reindex(df.index)
    df["batting_average"] = bat["average"].reindex(df.index)
    df["balls_bowled"] = bowl["balls"].reindex(df.index).fillna(0)
    df["wickets"] = bowl["wickets"].reindex(df.index).fillna(0)
    df["economy"] = bowl["economy"].reindex(df.index)
    df["overs"] = bowl["overs"].reindex(df.index)

    df["batting_impact"] = (df["runs"] - expected_bat.reindex(df.index).fillna(0)).round(1)
    df["bowling_impact"] = (
        expected_conceded.reindex(df.index).fillna(0) - bowl["runs"].reindex(df.index).fillna(0)
    ).round(1)

    sq = ds.squads
    if f.seasons:
        sq = sq[sq["season"].isin(f.seasons)]
    matches = sq.groupby("player_id")["match_id"].nunique().reindex(df.index).fillna(0)
    df["matches"] = matches.astype(int)
    df["seasons"] = sq.groupby("player_id")["season"].nunique().reindex(df.index).fillna(0).astype(int)
    last_team = sq.sort_values("season").groupby("player_id")["team_id"].last()
    df["team_id"] = last_team.reindex(df.index)
    df["team_name"] = df["team_id"].map(ds.teams["name"])
    df["last_season"] = sq.groupby("player_id")["season"].max().reindex(df.index)

    safe_matches = df["matches"].clip(lower=1)
    df["batting_impact_per_match"] = (df["batting_impact"] / safe_matches).round(2)
    df["bowling_impact_per_match"] = (df["bowling_impact"] / safe_matches).round(2)
    # A player with no matches under these filters has no per-match rate.
    df.loc[df["matches"] == 0, ["batting_impact_per_match", "bowling_impact_per_match"]] = None

    # Keep only players whose sample supports a rate statistic in at least one
    # discipline; everyone else is noise in an auction pool.
    qualified = (df["balls_faced"] >= POOL_QUALIFICATION["min_balls_faced"]) | (
        df["balls_bowled"] >= POOL_QUALIFICATION["min_balls_bowled"]
    )
    df = df[qualified]

    if role:
        df = df[df["role"] == role]
    if search:
        hits = names.matching_ids(ds, search)
        df = df[df.index.isin(hits or [])]

    sort_col = {
        "batting_impact": "batting_impact",
        "bowling_impact": "bowling_impact",
        "batting_impact_per_match": "batting_impact_per_match",
        "bowling_impact_per_match": "bowling_impact_per_match",
        "runs": "runs",
        "wickets": "wickets",
        "strike_rate": "strike_rate",
        "economy": "economy",
        "matches": "matches",
        "name": "name",
    }.get(sort, "batting_impact")
    ascending = sort_col in {"economy", "name"}
    df = df.sort_values(sort_col, ascending=ascending, na_position="last")

    total = len(df)
    rows = metrics.records(df.head(limit).reset_index(), ds)

    prices = load_prices(ds)
    if prices is not None:
        latest = prices.sort_values("season").groupby("player_id").last()
        for row in rows:
            hit = latest.loc[row["player_id"]] if row["player_id"] in latest.index else None
            row["price_inr"] = None if hit is None else float(hit["price_inr"])
            row["price_season"] = None if hit is None else int(hit["season"])

    return {
        "total": total,
        "returned": len(rows),
        "sort": sort,
        "rows": rows,
        "filters": f.describe(),
        "qualification": POOL_QUALIFICATION,
        "method": METHOD_NOTES,
        "prices_available": prices is not None,
        "price_note": (
            "Auction prices are loaded from an operator-supplied file at "
            "data/raw/auction/prices.csv. Cricsheet ball-by-ball data contains no "
            "price information, and Stryk will not estimate one: the impact figures "
            "on this page are analytical measures of on-field contribution, not "
            "valuations and not market prices."
        ),
        "price_file": str(_price_path()),
    }


def squad_requirements() -> List[Dict[str, object]]:
    """Default role slots for the squad builder.

    These mirror the shape of a usable T20 XI rather than any league's formal
    rules, and the UI lets the user change every number.
    """
    return [
        {"role": "Batter", "minimum": 5, "note": "Top order and middle order."},
        {"role": "Bowler", "minimum": 5, "note": "Enough to bowl twenty overs without a part-timer."},
        {"role": "All-rounder", "minimum": 2, "note": "Cover for a short bowling innings or a collapse."},
    ]
