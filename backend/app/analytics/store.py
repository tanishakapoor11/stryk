"""In-memory fact table + filter vocabulary for the analytics layer.

Every analytic in Stryk is a pandas aggregation over one denormalised ball
table that is read from the database once and cached. At IPL scale (~300k
deliveries, ~60 MB) this is far cheaper to maintain - and faster - than a
bespoke SQL query per metric, and it keeps the statistical rules in one place.

ponytail: in-memory fact table; move to materialised SQL aggregates if the
dataset grows past a few million deliveries or the API runs multi-process.
"""

from __future__ import annotations

import datetime as dt
import logging
import threading
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import pandas as pd
from sqlalchemy import select

from app.core.db import engine
from app.models import (
    Delivery,
    Dismissal,
    Match,
    MatchPlayer,
    Player,
    Team,
    Venue,
)

log = logging.getLogger("stryk.store")
_lock = threading.Lock()
_cache: Optional["Dataset"] = None


@dataclass
class Dataset:
    deliveries: pd.DataFrame
    positions: pd.DataFrame
    matches: pd.DataFrame
    players: pd.DataFrame
    teams: pd.DataFrame
    squads: pd.DataFrame
    venues: pd.DataFrame
    loaded_at: dt.datetime

    @property
    def is_empty(self) -> bool:
        return self.deliveries.empty

    def player_name(self, pid: str) -> Optional[str]:
        """The name to show a reader: full where known, scorecard otherwise."""
        for column in ("display_name", "name"):
            try:
                value = self.players.at[pid, column]
            except KeyError:
                continue
            if isinstance(value, str) and value:
                return value
        return None

    def scorecard_name(self, pid: str) -> Optional[str]:
        """The Cricsheet form ("SS Iyer"), kept for provenance and for search."""
        try:
            return str(self.players.at[pid, "name"])
        except KeyError:
            return None

    def names(self, ids: Sequence[str]) -> List[str]:
        return [self.player_name(i) or i for i in ids]


def enrich(deliveries: pd.DataFrame, dismissals: pd.DataFrame) -> pd.DataFrame:
    """Attach dismissal context and the derived scoring flags to the ball table.

    Shared by the loader and the test-suite so that unit tests exercise the
    same derivation the API uses.
    """
    if deliveries.empty:
        return deliveries
    deliveries = deliveries.copy()
    for col in ("is_legal", "is_ball_faced", "is_wicket", "is_bowler_wicket",
                "is_super_over", "is_chase"):
        if col in deliveries:
            deliveries[col] = deliveries[col].astype(bool)
    if dismissals is not None and not dismissals.empty:
        dis = dismissals.drop_duplicates("delivery_id").set_index("delivery_id")
        deliveries = deliveries.join(
            dis[["player_out_id", "kind", "credited_to_bowler"]].rename(
                columns={
                    "player_out_id": "out_player_id",
                    "kind": "out_kind",
                    "credited_to_bowler": "out_credited_to_bowler",
                }
            ),
            on="id",
        )
    for col in ("out_player_id", "out_kind"):
        if col not in deliveries:
            deliveries[col] = None
    if "out_credited_to_bowler" not in deliveries:
        deliveries["out_credited_to_bowler"] = False
    deliveries["out_credited_to_bowler"] = (
        deliveries["out_credited_to_bowler"].notna()
        & deliveries["out_credited_to_bowler"].eq(True)
    )
    deliveries["is_four"] = deliveries["batter_runs"] == 4
    deliveries["is_six"] = deliveries["batter_runs"] == 6
    # A batter's dot: no run off the bat. Byes/leg-byes are still dots for the
    # batter but not for the bowler, hence two separate flags.
    deliveries["is_batter_dot"] = (deliveries["batter_runs"] == 0) & deliveries["is_ball_faced"]
    deliveries["is_bowler_dot"] = (deliveries["total_runs"] == 0) & deliveries["is_legal"]
    return deliveries


def _read(stmt) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(stmt, conn)


def prepare_players(players: pd.DataFrame) -> pd.DataFrame:
    """Index the player registry and derive its display and search columns.

    Cricsheet names players the way a scorecard does - "SS Iyer" - which is not
    what anyone types into a search box. ``full_name`` is resolved separately by
    scripts/fetch_player_names.py from Cricsheet's ESPNcricinfo ids joined
    against Wikidata; it is null wherever no source could supply one, and is
    never guessed from the initials.

    * ``display_name`` is what the interface shows: the full name when known,
      the scorecard name otherwise.
    * ``search_blob`` is both names lowercased into one string, so a query
      matches whichever form the user happens to know.
    """
    if players.empty:
        return players
    players = players.set_index("id")
    if "full_name" not in players.columns:
        players["full_name"] = None
    full = players["full_name"].fillna("")
    players["display_name"] = full.where(full.str.len() > 0, players["name"])
    # Aliases join the blob so a player is findable by any name they go by.
    # Wikidata labels Prabhsimran Singh as "Simran Singh" and keeps the fuller
    # name only as an alias, which is exactly the case this covers.
    alias_text = (
        players["aliases"].fillna("").str.replace("|", " ", regex=False).str.lower()
        if "aliases" in players.columns
        else ""
    )
    players["search_blob"] = (
        players["display_name"].str.lower() + " " + players["name"].str.lower() + " " + alias_text
    ).str.strip()
    return players


def load() -> Dataset:
    """Read the whole fact table into memory and pre-join the dismissals."""
    deliveries = _read(select(Delivery))
    dismissals = _read(select(Dismissal))
    matches = _read(select(Match))
    players = _read(select(Player))
    teams = _read(select(Team))
    squads = _read(select(MatchPlayer))
    venues = _read(select(Venue))

    if not matches.empty:
        matches["date"] = pd.to_datetime(matches["date"])

    deliveries = enrich(deliveries, dismissals)
    if not deliveries.empty:
        md = matches.set_index("id")
        deliveries["date"] = deliveries["match_id"].map(md["date"])
        deliveries["match_type"] = deliveries["match_id"].map(md["match_type"])

    ds = Dataset(
        deliveries=deliveries,
        positions=batting_positions(deliveries),
        matches=matches,
        players=prepare_players(players),
        teams=teams.set_index("id") if not teams.empty else teams,
        squads=squads,
        venues=venues.set_index("id") if not venues.empty else venues,
        loaded_at=dt.datetime.utcnow(),
    )
    log.info("loaded %s deliveries / %s matches", len(deliveries), len(matches))
    return ds


def batting_positions(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Derive each batter's position in the order from arrival at the crease.

    Cricsheet does not publish a batting order; it is reconstructed from the
    sequence in which players first appear, with the opener on strike at 1 and
    the non-striker at 2.
    """
    if deliveries.empty:
        return pd.DataFrame(columns=["innings_id", "player_id", "position"])
    cols = ["innings_id", "id"]
    striker = deliveries[cols + ["batter_id"]].rename(columns={"batter_id": "player_id"})
    striker["_rank"] = 0
    nonstriker = deliveries[cols + ["non_striker_id"]].rename(columns={"non_striker_id": "player_id"})
    nonstriker["_rank"] = 1
    long = pd.concat([striker, nonstriker]).sort_values(["id", "_rank"])
    first = long.drop_duplicates(["innings_id", "player_id"]).sort_values(["innings_id", "id", "_rank"])
    first["position"] = first.groupby("innings_id").cumcount() + 1
    return first[["innings_id", "player_id", "position"]].reset_index(drop=True)


def get() -> Dataset:
    global _cache
    if _cache is None:
        with _lock:
            if _cache is None:
                _cache = load()
    return _cache


def reload() -> Dataset:
    global _cache
    with _lock:
        _cache = load()
    return _cache


@dataclass
class Filters:
    """The shared filter vocabulary used by every endpoint.

    ``include_super_over`` defaults to False: super-over deliveries are a
    separate contest and are excluded from career and season statistics, which
    is how official IPL records treat them.
    """

    seasons: Optional[List[int]] = None
    team_ids: Optional[List[int]] = None
    opposition_ids: Optional[List[int]] = None
    venue_ids: Optional[List[int]] = None
    phases: Optional[List[str]] = None
    innings_number: Optional[int] = None
    chasing: Optional[bool] = None
    date_from: Optional[dt.date] = None
    date_to: Optional[dt.date] = None
    include_super_over: bool = False
    match_types: Optional[List[str]] = None
    applied: dict = field(default_factory=dict)

    def describe(self) -> dict:
        return {
            k: v
            for k, v in {
                "seasons": self.seasons,
                "teams": self.team_ids,
                "opposition": self.opposition_ids,
                "venues": self.venue_ids,
                "phases": self.phases,
                "innings": self.innings_number,
                "chasing": self.chasing,
                "date_from": self.date_from.isoformat() if self.date_from else None,
                "date_to": self.date_to.isoformat() if self.date_to else None,
                "include_super_over": self.include_super_over,
                "match_types": self.match_types,
            }.items()
            if v not in (None, [], False) or k == "include_super_over"
        }


def apply(df: pd.DataFrame, f: Filters, team_column: str = "batting_team_id") -> pd.DataFrame:
    """Filter the delivery frame. ``team_column`` selects which side the
    ``team_ids`` filter applies to (batting side for batting views, bowling
    side for bowling views)."""
    if df.empty:
        return df
    mask = pd.Series(True, index=df.index)
    if not f.include_super_over:
        mask &= ~df["is_super_over"]
    if f.seasons:
        mask &= df["season"].isin(f.seasons)
    if f.match_types:
        mask &= df["match_type"].isin(f.match_types)
    if f.team_ids:
        mask &= df[team_column].isin(f.team_ids)
    if f.opposition_ids:
        other = "bowling_team_id" if team_column == "batting_team_id" else "batting_team_id"
        mask &= df[other].isin(f.opposition_ids)
    if f.venue_ids:
        mask &= df["venue_id"].isin(f.venue_ids)
    if f.phases:
        mask &= df["phase"].isin(f.phases)
    if f.innings_number is not None:
        mask &= df["innings_number"] == f.innings_number
    if f.chasing is not None:
        mask &= df["is_chase"] == f.chasing
    if f.date_from is not None:
        mask &= df["date"] >= pd.Timestamp(f.date_from)
    if f.date_to is not None:
        mask &= df["date"] <= pd.Timestamp(f.date_to)
    return df[mask]
