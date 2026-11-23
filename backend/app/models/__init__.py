"""Normalised schema for ball-by-ball cricket data.

Design notes
------------
* The schema is format-agnostic: ``Match.match_type`` ("T20", "ODI", "Test")
  and ``Match.event_name`` carry the competition, so adding internationals is
  an ingestion + phase-config change, not a migration of the core tables.
* ``Delivery`` is a fact table. A handful of columns are deliberately
  denormalised onto it (season, teams, innings number, super-over flag, phase,
  and the derived scoring booleans) so that every analytical query is a single
  scan with no joins. The derivations are applied exactly once, at ingest, in
  :mod:`app.ingestion.cricsheet` - which is also the only place the scoring
  rules live.
* There is no ``Season`` table: a season is a single scalar (the calendar year
  the matches were played in) and a lookup table would add a join to every
  query for no information. ``Match.season`` is the normalised year and
  ``Match.season_label`` keeps Cricsheet's original label ("2007/08").
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Team(Base):
    __tablename__ = "team"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    short_name: Mapped[Optional[str]] = mapped_column(String(10))
    #: Historical names that map onto this franchise (e.g. "Delhi Daredevils").
    aliases: Mapped[list] = mapped_column(JSON, default=list)


class Venue(Base):
    __tablename__ = "venue"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    city: Mapped[Optional[str]] = mapped_column(String(80))


class Player(Base):
    __tablename__ = "player"

    #: Cricsheet people-registry identifier - stable across matches and formats.
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    #: Cricsheet's scorecard name: initials plus surname, e.g. "SS Iyer".
    name: Mapped[str] = mapped_column(String(120), index=True)
    #: The name a person would actually type, e.g. "Shreyas Iyer". Resolved by
    #: scripts/fetch_player_names.py and null where no source could supply one;
    #: it is never guessed from the initials.
    full_name: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    #: Alternative names from Wikidata, pipe separated. Indexed for search so a
    #: player is findable by any name they are known by, not just the one shown.
    aliases: Mapped[Optional[str]] = mapped_column(String(500))
    #: Populated from the optional Cricsheet "people" register when available.
    batting_style: Mapped[Optional[str]] = mapped_column(String(32))
    bowling_style: Mapped[Optional[str]] = mapped_column(String(48))


class Match(Base):
    __tablename__ = "match"

    #: Cricsheet match id (the JSON filename stem).
    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    match_type: Mapped[str] = mapped_column(String(16), index=True)
    event_name: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    match_number: Mapped[Optional[int]] = mapped_column(Integer)
    stage: Mapped[Optional[str]] = mapped_column(String(48))
    gender: Mapped[str] = mapped_column(String(16), default="male")
    season: Mapped[int] = mapped_column(Integer, index=True)
    season_label: Mapped[str] = mapped_column(String(16))
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    venue_id: Mapped[Optional[int]] = mapped_column(ForeignKey("venue.id"))
    team1_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    team2_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    toss_winner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("team.id"))
    toss_decision: Mapped[Optional[str]] = mapped_column(String(8))
    winner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("team.id"), index=True)
    #: "normal" | "tie" | "no result" | "abandoned"
    result: Mapped[str] = mapped_column(String(16), default="normal")
    result_margin: Mapped[Optional[int]] = mapped_column(Integer)
    #: "runs" | "wickets" | None
    result_type: Mapped[Optional[str]] = mapped_column(String(16))
    #: "D/L", "VJD" ... when the result was decided by a rain method.
    method: Mapped[Optional[str]] = mapped_column(String(16))
    eliminator_id: Mapped[Optional[int]] = mapped_column(ForeignKey("team.id"))
    player_of_match_id: Mapped[Optional[str]] = mapped_column(ForeignKey("player.id"))
    balls_per_over: Mapped[int] = mapped_column(Integer, default=6)
    overs_limit: Mapped[Optional[int]] = mapped_column(Integer)
    source_file: Mapped[str] = mapped_column(String(64))
    ingested_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    venue: Mapped[Optional[Venue]] = relationship()


class MatchPlayer(Base):
    """Squad sheet: who was named in the XI for each match."""

    __tablename__ = "match_player"
    __table_args__ = (UniqueConstraint("match_id", "player_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("match.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("player.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    season: Mapped[int] = mapped_column(Integer, index=True)


class Innings(Base):
    __tablename__ = "innings"
    __table_args__ = (UniqueConstraint("match_id", "innings_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("match.id", ondelete="CASCADE"), index=True)
    innings_number: Mapped[int] = mapped_column(Integer)
    batting_team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    bowling_team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    is_super_over: Mapped[bool] = mapped_column(Boolean, default=False)
    #: Set on the chasing innings only.
    target_runs: Mapped[Optional[int]] = mapped_column(Integer)
    target_overs: Mapped[Optional[float]] = mapped_column(Float)
    #: True when this innings was batting second (chasing a target).
    is_chase: Mapped[bool] = mapped_column(Boolean, default=False)


class Delivery(Base):
    """One delivery. See module docstring for the denormalisation rationale."""

    __tablename__ = "delivery"
    __table_args__ = (
        Index("ix_delivery_batter_season", "batter_id", "season"),
        Index("ix_delivery_bowler_season", "bowler_id", "season"),
        Index("ix_delivery_matchup", "batter_id", "bowler_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    innings_id: Mapped[int] = mapped_column(ForeignKey("innings.id", ondelete="CASCADE"), index=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("match.id", ondelete="CASCADE"), index=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    innings_number: Mapped[int] = mapped_column(Integer)
    is_super_over: Mapped[bool] = mapped_column(Boolean, default=False)
    is_chase: Mapped[bool] = mapped_column(Boolean, default=False)
    batting_team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    bowling_team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    venue_id: Mapped[Optional[int]] = mapped_column(ForeignKey("venue.id"))

    #: 0-based over number, as published by Cricsheet.
    over: Mapped[int] = mapped_column(Integer)
    #: 1-based position within the over, counting extras.
    ball_in_over: Mapped[int] = mapped_column(Integer)
    #: "powerplay" | "middle" | "death" - see app.analytics.constants.
    phase: Mapped[str] = mapped_column(String(12), index=True)

    batter_id: Mapped[str] = mapped_column(ForeignKey("player.id"), index=True)
    bowler_id: Mapped[str] = mapped_column(ForeignKey("player.id"), index=True)
    non_striker_id: Mapped[str] = mapped_column(ForeignKey("player.id"))

    batter_runs: Mapped[int] = mapped_column(Integer, default=0)
    extra_runs: Mapped[int] = mapped_column(Integer, default=0)
    total_runs: Mapped[int] = mapped_column(Integer, default=0)
    wides: Mapped[int] = mapped_column(Integer, default=0)
    noballs: Mapped[int] = mapped_column(Integer, default=0)
    byes: Mapped[int] = mapped_column(Integer, default=0)
    legbyes: Mapped[int] = mapped_column(Integer, default=0)
    penalty: Mapped[int] = mapped_column(Integer, default=0)

    #: Counts towards the over (neither a wide nor a no-ball).
    is_legal: Mapped[bool] = mapped_column(Boolean, default=True)
    #: Counts towards the batter's balls faced (everything except wides).
    is_ball_faced: Mapped[bool] = mapped_column(Boolean, default=True)
    #: Runs debited to the bowler: batter runs + wides + no-balls.
    bowler_runs: Mapped[int] = mapped_column(Integer, default=0)
    is_wicket: Mapped[bool] = mapped_column(Boolean, default=False)
    #: Wicket credited to the bowler (excludes run-outs, retirements, ...).
    is_bowler_wicket: Mapped[bool] = mapped_column(Boolean, default=False)


class Dismissal(Base):
    __tablename__ = "dismissal"

    id: Mapped[int] = mapped_column(primary_key=True)
    delivery_id: Mapped[int] = mapped_column(ForeignKey("delivery.id", ondelete="CASCADE"), index=True)
    innings_id: Mapped[int] = mapped_column(ForeignKey("innings.id", ondelete="CASCADE"), index=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("match.id", ondelete="CASCADE"), index=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    player_out_id: Mapped[str] = mapped_column(ForeignKey("player.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    #: The bowler on strike; only credited when ``credited_to_bowler`` is true.
    bowler_id: Mapped[str] = mapped_column(ForeignKey("player.id"), index=True)
    credited_to_bowler: Mapped[bool] = mapped_column(Boolean, default=False)
    #: Fielder player ids (catcher / run-out fielders). Rare multi-fielder
    #: dismissals are kept as a list rather than spawning a join table.
    fielder_ids: Mapped[list] = mapped_column(JSON, default=list)
    phase: Mapped[str] = mapped_column(String(12))


class IngestionLog(Base):
    """One row per ingestion run - the audit trail asked for by the pipeline."""

    __tablename__ = "ingestion_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String(160))
    matches_seen: Mapped[int] = mapped_column(Integer, default=0)
    matches_ingested: Mapped[int] = mapped_column(Integer, default=0)
    matches_skipped: Mapped[int] = mapped_column(Integer, default=0)
    deliveries_ingested: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="running")
    warnings: Mapped[list] = mapped_column(JSON, default=list)


__all__ = [
    "Base",
    "Team",
    "Venue",
    "Player",
    "Match",
    "MatchPlayer",
    "Innings",
    "Delivery",
    "Dismissal",
    "IngestionLog",
]
