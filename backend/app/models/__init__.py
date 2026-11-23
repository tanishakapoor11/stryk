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
* Competitions, seasons, stages and groups are first-class (see
  docs/global-platform.md). ``Match.season`` (an int year) is kept alongside
  ``Match.season_id`` because the analytics layer and existing URLs filter on
  it; ``Season`` is the authority for what a season *is* (BBL 2023/24 is one
  season across two calendar years).
* Every match records where it came from (``source_id``, ``external_id``) and
  how much of it we hold (``data_level``, 1-5). Nothing is inferred to fill a
  gap: a column a source does not supply stays null.
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

# --------------------------------------------------------------------- enums
# Stored as plain strings (portable across SQLite and PostgreSQL); the allowed
# values are listed here and validated by the catalogue loader and the API.
COMPETITION_TYPES = (
    "INTERNATIONAL", "ICC_TOURNAMENT", "DOMESTIC", "FRANCHISE_LEAGUE", "REGIONAL", "OTHER",
)
GENDERS = ("MEN", "WOMEN", "MIXED", "UNKNOWN")
TEAM_TYPES = ("NATIONAL", "FRANCHISE", "DOMESTIC", "REGIONAL", "OTHER")
MATCH_STATUSES = ("scheduled", "live", "completed", "no_result", "abandoned")
SEASON_STATUSES = ("upcoming", "in_progress", "completed", "unknown")
STAGE_TYPES = ("league", "group", "knockout")

#: Data availability levels (docs/global-platform.md section 4).
DATA_LEVEL_METADATA = 1
DATA_LEVEL_SCORECARD = 2
DATA_LEVEL_DETAILED = 3
DATA_LEVEL_BALL_BY_BALL = 4
DATA_LEVEL_ADVANCED = 5


class Country(Base):
    __tablename__ = "country"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: Stable catalogue key ("IND", "ENG", "WI").
    short_code: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    flag: Mapped[Optional[str]] = mapped_column(String(16))
    cricket_board: Mapped[Optional[str]] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PointsSystem(Base):
    """A competition's points allocation and tie-break order.

    ``rules`` holds the catalogue entry verbatim (points per result, tie
    resolution, tie-breaker sequence, qualifiers, cited sources) so the rules
    engine never needs a code change to support a new competition.
    """

    __tablename__ = "points_system"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    rules: Mapped[dict] = mapped_column(JSON, default=dict)


class DataSource(Base):
    """A data provider, with the licence terms that govern what we may show."""

    __tablename__ = "data_source"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    url: Mapped[Optional[str]] = mapped_column(String(200))
    licence: Mapped[Optional[str]] = mapped_column(String(160))
    attribution: Mapped[Optional[str]] = mapped_column(String(300))
    data_level: Mapped[int] = mapped_column(Integer, default=DATA_LEVEL_METADATA)
    update_frequency: Mapped[Optional[str]] = mapped_column(String(160))
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    checked_on: Mapped[Optional[dt.date]] = mapped_column(Date)


class SourceDataset(Base):
    """One downloadable dataset published by a source, as seen on ``checked_on``."""

    __tablename__ = "source_dataset"
    __table_args__ = (UniqueConstraint("source_id", "key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_source.id"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(160))
    url: Mapped[Optional[str]] = mapped_column(String(300))
    #: Match count the source advertised when the registry was last checked.
    published_matches: Mapped[Optional[int]] = mapped_column(Integer)
    withheld_matches: Mapped[Optional[int]] = mapped_column(Integer)


class Competition(Base):
    __tablename__ = "competition"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    short_name: Mapped[Optional[str]] = mapped_column(String(40))
    competition_type: Mapped[str] = mapped_column(String(24), index=True)
    gender: Mapped[str] = mapped_column(String(8), index=True)
    #: Null for international and ICC competitions.
    country_id: Mapped[Optional[int]] = mapped_column(ForeignKey("country.id"), index=True)
    governing_body: Mapped[Optional[str]] = mapped_column(String(120))
    description: Mapped[Optional[str]] = mapped_column(String(600))
    logo: Mapped[Optional[str]] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    #: Formats this competition is played in, as the catalogue declares them.
    formats: Mapped[list] = mapped_column(JSON, default=list)
    #: "calendar_year" or "source_label" - how a match's season is named.
    season_naming: Mapped[str] = mapped_column(String(16), default="source_label")
    points_system_id: Mapped[Optional[int]] = mapped_column(ForeignKey("points_system.id"))
    #: False for a competition created on the fly from an unrecognised event.
    is_catalogued: Mapped[bool] = mapped_column(Boolean, default=True)
    #: Matching rules and source pointers from the catalogue.
    match_rules: Mapped[list] = mapped_column(JSON, default=list)
    #: Why no source covers this competition, when none does.
    unavailable_reason: Mapped[Optional[str]] = mapped_column(String(300))

    country: Mapped[Optional[Country]] = relationship()
    points_system: Mapped[Optional[PointsSystem]] = relationship()


class Season(Base):
    __tablename__ = "season"
    __table_args__ = (UniqueConstraint("competition_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competition.id", ondelete="CASCADE"), index=True
    )
    #: "2024", "2023/24" - unique within the competition, used in URLs.
    name: Mapped[str] = mapped_column(String(24))
    #: The year the season started.
    year: Mapped[int] = mapped_column(Integer, index=True)
    start_date: Mapped[Optional[dt.date]] = mapped_column(Date)
    end_date: Mapped[Optional[dt.date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="unknown")
    #: Dominant match format, e.g. "T20". Null when the season mixes formats.
    format: Mapped[Optional[str]] = mapped_column(String(16))
    points_system_id: Mapped[Optional[int]] = mapped_column(ForeignKey("points_system.id"))


class TournamentStage(Base):
    __tablename__ = "tournament_stage"
    __table_args__ = (UniqueConstraint("season_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("season.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(48))
    #: "league" | "group" | "knockout"
    stage_type: Mapped[str] = mapped_column(String(12))
    #: Position in the season, league first.
    sequence: Mapped[int] = mapped_column(Integer, default=0)


class TournamentGroup(Base):
    __tablename__ = "tournament_group"
    __table_args__ = (UniqueConstraint("season_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("season.id", ondelete="CASCADE"), index=True)
    stage_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tournament_stage.id"))
    name: Mapped[str] = mapped_column(String(48))


class ExternalId(Base):
    """Maps a STRYK entity to its identifier in an external source."""

    __tablename__ = "external_id"
    __table_args__ = (
        UniqueConstraint("source", "entity_type", "external_id"),
        Index("ix_external_id_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    #: "player" | "team" | "match" | "competition" | "venue"
    entity_type: Mapped[str] = mapped_column(String(16))
    entity_id: Mapped[str] = mapped_column(String(32))
    #: Source slug: "cricsheet", "cricinfo", ...
    source: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(64))


class Team(Base):
    __tablename__ = "team"
    __table_args__ = (UniqueConstraint("name", "gender", name="uq_team_name_gender"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    #: Not unique on its own: "India" men and "India" women are different teams.
    name: Mapped[str] = mapped_column(String(80), index=True)
    short_name: Mapped[Optional[str]] = mapped_column(String(10))
    #: Historical names that map onto this franchise (e.g. "Delhi Daredevils").
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    gender: Mapped[str] = mapped_column(String(8), default="MEN", index=True)
    team_type: Mapped[str] = mapped_column(String(12), default="OTHER")
    country_id: Mapped[Optional[int]] = mapped_column(ForeignKey("country.id"))
    is_national_team: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    logo: Mapped[Optional[str]] = mapped_column(String(200))


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
    #: No Phase 1 source supplies these; they stay null rather than guessed.
    date_of_birth: Mapped[Optional[dt.date]] = mapped_column(Date)
    country_id: Mapped[Optional[int]] = mapped_column(ForeignKey("country.id"))
    playing_role: Mapped[Optional[str]] = mapped_column(String(24))
    image: Mapped[Optional[str]] = mapped_column(String(200))
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean)


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

    competition_id: Mapped[Optional[int]] = mapped_column(ForeignKey("competition.id"), index=True)
    season_id: Mapped[Optional[int]] = mapped_column(ForeignKey("season.id"), index=True)
    stage_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tournament_stage.id"))
    group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tournament_group.id"))
    #: See MATCH_STATUSES.
    status: Mapped[str] = mapped_column(String(16), default="completed")
    #: 1 metadata ... 4 ball-by-ball, 5 advanced. What we hold, not what exists.
    data_level: Mapped[int] = mapped_column(Integer, default=DATA_LEVEL_BALL_BY_BALL)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("data_source.id"))
    #: The match's id in that source.
    external_id: Mapped[Optional[str]] = mapped_column(String(64))
    #: Source dataset the match was imported from ("ipl", "t20s", ...).
    source_dataset: Mapped[Optional[str]] = mapped_column(String(64))

    venue: Mapped[Optional[Venue]] = relationship()


class MatchOfficial(Base):
    __tablename__ = "match_official"
    __table_args__ = (UniqueConstraint("match_id", "player_id", "role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("match.id", ondelete="CASCADE"), index=True)
    #: Officials share the Cricsheet people registry with players.
    player_id: Mapped[str] = mapped_column(ForeignKey("player.id"), index=True)
    #: "umpire" | "tv_umpire" | "reserve_umpire" | "match_referee"
    role: Mapped[str] = mapped_column(String(16))


class CompetitionTeam(Base):
    """A team taking part in one season of a competition."""

    __tablename__ = "competition_team"
    __table_args__ = (UniqueConstraint("season_id", "team_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competition.id"), index=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("season.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tournament_group.id"))


class PlayerTeam(Base):
    """A player representing a team in a season - derived from playing XIs.

    A player can represent different teams across competitions and seasons;
    the player row itself is never duplicated.
    """

    __tablename__ = "player_team"
    __table_args__ = (UniqueConstraint("player_id", "team_id", "season_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("player.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competition.id"), index=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("season.id", ondelete="CASCADE"), index=True)
    matches: Mapped[int] = mapped_column(Integer, default=0)


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
    "Country",
    "PointsSystem",
    "DataSource",
    "SourceDataset",
    "Competition",
    "Season",
    "TournamentStage",
    "TournamentGroup",
    "ExternalId",
    "MatchOfficial",
    "CompetitionTeam",
    "PlayerTeam",
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
