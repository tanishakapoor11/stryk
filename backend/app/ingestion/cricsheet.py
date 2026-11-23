"""Cricsheet JSON -> normalised relational store.

The parser is deliberately strict: anything it cannot interpret is recorded as
a warning on the ingestion log rather than silently coerced to zero. Matches
are keyed by their Cricsheet id so re-running the importer is idempotent and
new seasons can be added incrementally.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.analytics.constants import (
    BOWLER_CREDITED_DISMISSALS,
    BOWLER_DEBITED_EXTRAS,
    NOT_OUT_RETIREMENTS,
    phase_for_over,
)
from app.models import (
    Delivery,
    Dismissal,
    IngestionLog,
    Innings,
    Match,
    MatchPlayer,
    Player,
    Team,
    Venue,
)

log = logging.getLogger("stryk.ingest")

#: Franchise renames. Deliveries are stored against the current franchise so a
#: team page is continuous across a rebrand. Deccan Chargers is intentionally
#: NOT merged into Sunrisers Hyderabad: the franchise was terminated in 2012
#: and SRH was sold as a new entity, so merging them would invent history.
TEAM_CANONICAL = {
    "Delhi Daredevils": "Delhi Capitals",
    "Kings XI Punjab": "Punjab Kings",
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",
    "Rising Pune Supergiants": "Rising Pune Supergiant",
}

TEAM_SHORT = {
    "Mumbai Indians": "MI",
    "Chennai Super Kings": "CSK",
    "Kolkata Knight Riders": "KKR",
    "Rajasthan Royals": "RR",
    "Royal Challengers Bengaluru": "RCB",
    "Sunrisers Hyderabad": "SRH",
    "Punjab Kings": "PBKS",
    "Delhi Capitals": "DC",
    "Gujarat Titans": "GT",
    "Lucknow Super Giants": "LSG",
    "Deccan Chargers": "DCH",
    "Pune Warriors": "PWI",
    "Gujarat Lions": "GL",
    "Rising Pune Supergiant": "RPS",
    "Kochi Tuskers Kerala": "KTK",
}


class IngestionError(Exception):
    pass


@dataclass
class IngestStats:
    seen: int = 0
    ingested: int = 0
    skipped: int = 0
    deliveries: int = 0
    warnings: List[str] = field(default_factory=list)

    def warn(self, msg: str) -> None:
        log.warning(msg)
        if len(self.warnings) < 500:
            self.warnings.append(msg)


class _Registry:
    """Lazily creates and caches Team / Venue / Player rows."""

    def __init__(self, db: Session):
        self.db = db
        self.teams: Dict[str, int] = {
            name: tid for tid, name in db.execute(select(Team.id, Team.name)).all()
        }
        self.venues: Dict[str, int] = {
            name: vid for vid, name in db.execute(select(Venue.id, Venue.name)).all()
        }
        self.players: set = {pid for (pid,) in db.execute(select(Player.id)).all()}

    def team(self, raw_name: str) -> int:
        name = TEAM_CANONICAL.get(raw_name, raw_name)
        if name not in self.teams:
            aliases = sorted(k for k, v in TEAM_CANONICAL.items() if v == name)
            row = Team(name=name, short_name=TEAM_SHORT.get(name), aliases=aliases)
            self.db.add(row)
            self.db.flush()
            self.teams[name] = row.id
        return self.teams[name]

    def venue(self, name: Optional[str], city: Optional[str]) -> Optional[int]:
        if not name:
            return None
        if name not in self.venues:
            row = Venue(name=name, city=city)
            self.db.add(row)
            self.db.flush()
            self.venues[name] = row.id
        return self.venues[name]

    def player(self, pid: str, name: str) -> str:
        if pid not in self.players:
            self.db.add(Player(id=pid, name=name))
            self.players.add(pid)
        return pid


def _season_year(info: dict, stats: IngestStats, match_id: str) -> int:
    """Normalise the season to the calendar year the matches were played in.

    Cricsheet labels the 2008 IPL "2007/08" and the 2020 (UAE) edition
    "2020/21"; taking the year off the first date avoids both the off-by-one
    and the collision with the genuine 2021 season.
    """
    dates = info.get("dates") or []
    if not dates:
        raise IngestionError(f"{match_id}: match has no dates")
    year = dt.date.fromisoformat(dates[0]).year
    label = str(info.get("season", year))
    if label.isdigit() and int(label) != year:
        stats.warn(f"{match_id}: season label {label} but first date is {dates[0]}")
    return year


def _outcome(info: dict, reg: _Registry) -> dict:
    out = info.get("outcome") or {}
    res: dict = {
        "winner_id": None,
        "result": "normal",
        "result_margin": None,
        "result_type": None,
        "method": out.get("method"),
        "eliminator_id": None,
    }
    if "winner" in out:
        res["winner_id"] = reg.team(out["winner"])
        by = out.get("by") or {}
        for key in ("runs", "wickets", "innings"):
            if key in by:
                res["result_type"] = key
                res["result_margin"] = by[key] if key != "innings" else None
    if "eliminator" in out:
        # Super over: the match is a tie decided by the eliminator.
        res["result"] = "tie"
        res["eliminator_id"] = reg.team(out["eliminator"])
        res["winner_id"] = res["eliminator_id"]
    if "result" in out:
        res["result"] = out["result"]
    return res


def parse_match(path: Path, reg: _Registry, stats: IngestStats) -> dict:
    """Parse one Cricsheet file into row dicts. Pure: performs no writes."""
    raw = json.loads(path.read_text())
    info = raw["info"]
    match_id = path.stem
    people: Dict[str, str] = info.get("registry", {}).get("people", {})
    if not people:
        raise IngestionError(f"{match_id}: no people registry; cannot assign stable player ids")

    def pid(name: str) -> str:
        ident = people.get(name)
        if ident is None:
            raise IngestionError(f"{match_id}: player {name!r} missing from registry")
        return reg.player(ident, name)

    season = _season_year(info, stats, match_id)
    match_type = info.get("match_type", "T20")
    event = info.get("event") or {}
    if isinstance(event, str):
        event = {"name": event}
    teams = info["teams"]
    if len(teams) != 2:
        raise IngestionError(f"{match_id}: expected 2 teams, found {len(teams)}")

    match_row = {
        "id": match_id,
        "match_type": match_type,
        "event_name": event.get("name"),
        "match_number": event.get("match_number"),
        "stage": event.get("stage") or event.get("group"),
        "gender": info.get("gender", "male"),
        "season": season,
        "season_label": str(info.get("season", season)),
        "date": dt.date.fromisoformat(info["dates"][0]),
        "venue_id": reg.venue(info.get("venue"), info.get("city")),
        "team1_id": reg.team(teams[0]),
        "team2_id": reg.team(teams[1]),
        "toss_winner_id": reg.team(info["toss"]["winner"]) if info.get("toss") else None,
        "toss_decision": (info.get("toss") or {}).get("decision"),
        "player_of_match_id": pid(info["player_of_match"][0]) if info.get("player_of_match") else None,
        "balls_per_over": info.get("balls_per_over", 6),
        "overs_limit": info.get("overs"),
        "source_file": path.name,
        **_outcome(info, reg),
    }

    squad_rows = []
    for team_name, names in (info.get("players") or {}).items():
        tid = reg.team(team_name)
        for name in names:
            squad_rows.append(
                {"match_id": match_id, "player_id": pid(name), "team_id": tid, "season": season}
            )
    if not squad_rows:
        stats.warn(f"{match_id}: no squad lists in source file")

    innings_rows: List[dict] = []
    delivery_rows: List[dict] = []
    dismissal_rows: List[dict] = []

    for idx, inn in enumerate(raw.get("innings", []), start=1):
        batting_id = reg.team(inn["team"])
        bowling_id = next(reg.team(t) for t in teams if reg.team(t) != batting_id)
        target = inn.get("target") or {}
        is_super = bool(inn.get("super_over"))
        innings_rows.append(
            {
                "match_id": match_id,
                "innings_number": idx,
                "batting_team_id": batting_id,
                "bowling_team_id": bowling_id,
                "is_super_over": is_super,
                "target_runs": target.get("runs"),
                "target_overs": target.get("overs"),
                "is_chase": bool(target),
            }
        )
        inn_index = len(innings_rows) - 1

        for over_block in inn.get("overs", []):
            over_no = over_block["over"]
            phase = phase_for_over(over_no, match_type)
            for ball_no, ball in enumerate(over_block.get("deliveries", []), start=1):
                runs = ball["runs"]
                extras = ball.get("extras") or {}
                batter_runs = int(runs.get("batter", 0))
                extra_runs = int(runs.get("extras", 0))
                total_runs = int(runs.get("total", batter_runs + extra_runs))
                if total_runs != batter_runs + extra_runs:
                    stats.warn(
                        f"{match_id} {over_no}.{ball_no}: runs total {total_runs} != "
                        f"batter {batter_runs} + extras {extra_runs}"
                    )
                if extras and sum(extras.values()) != extra_runs:
                    stats.warn(
                        f"{match_id} {over_no}.{ball_no}: extras breakdown "
                        f"{extras} != reported {extra_runs}"
                    )
                wides = int(extras.get("wides", 0))
                noballs = int(extras.get("noballs", 0))
                is_legal = wides == 0 and noballs == 0
                bowler_runs = batter_runs + sum(int(extras.get(k, 0)) for k in BOWLER_DEBITED_EXTRAS)
                wickets = ball.get("wickets") or []
                bowler_id = pid(ball["bowler"])

                delivery_rows.append(
                    {
                        "_innings_index": inn_index,
                        "match_id": match_id,
                        "season": season,
                        "innings_number": idx,
                        "is_super_over": is_super,
                        "is_chase": bool(target),
                        "batting_team_id": batting_id,
                        "bowling_team_id": bowling_id,
                        "venue_id": match_row["venue_id"],
                        "over": over_no,
                        "ball_in_over": ball_no,
                        "phase": phase,
                        "batter_id": pid(ball["batter"]),
                        "bowler_id": bowler_id,
                        "non_striker_id": pid(ball["non_striker"]),
                        "batter_runs": batter_runs,
                        "extra_runs": extra_runs,
                        "total_runs": total_runs,
                        "wides": wides,
                        "noballs": noballs,
                        "byes": int(extras.get("byes", 0)),
                        "legbyes": int(extras.get("legbyes", 0)),
                        "penalty": int(extras.get("penalty", 0)),
                        "is_legal": is_legal,
                        "is_ball_faced": wides == 0,
                        "bowler_runs": bowler_runs,
                        "is_wicket": bool(wickets),
                        "is_bowler_wicket": any(
                            w["kind"] in BOWLER_CREDITED_DISMISSALS for w in wickets
                        ),
                    }
                )
                delivery_index = len(delivery_rows) - 1
                for w in wickets:
                    kind = w["kind"]
                    if kind in NOT_OUT_RETIREMENTS:
                        # Retired hurt: the batter is not out, no dismissal.
                        continue
                    dismissal_rows.append(
                        {
                            "_delivery_index": delivery_index,
                            "_innings_index": inn_index,
                            "match_id": match_id,
                            "season": season,
                            "player_out_id": pid(w["player_out"]),
                            "kind": kind,
                            "bowler_id": bowler_id,
                            "credited_to_bowler": kind in BOWLER_CREDITED_DISMISSALS,
                            "fielder_ids": [
                                pid(f["name"])
                                for f in (w.get("fielders") or [])
                                if f.get("name")
                            ],
                            "phase": phase,
                        }
                    )

    if not delivery_rows:
        stats.warn(f"{match_id}: no deliveries (abandoned match?)")

    return {
        "match": match_row,
        "squad": squad_rows,
        "innings": innings_rows,
        "deliveries": delivery_rows,
        "dismissals": dismissal_rows,
    }


def ingest_directory(
    db: Session,
    directory: Path,
    limit: Optional[int] = None,
    seasons: Optional[Iterable[int]] = None,
) -> IngestStats:
    """Import every Cricsheet JSON file in ``directory``.

    Already-imported matches are skipped by id, so the importer is safe to
    re-run and to point at a directory containing additional seasons.
    """
    stats = IngestStats()
    run = IngestionLog(source=str(directory), status="running", warnings=[])
    db.add(run)
    db.commit()

    existing = {mid for (mid,) in db.execute(select(Match.id)).all()}
    reg = _Registry(db)
    season_filter = set(seasons) if seasons else None

    next_innings_id = (db.execute(select(func.max(Innings.id))).scalar() or 0) + 1
    next_delivery_id = (db.execute(select(func.max(Delivery.id))).scalar() or 0) + 1

    files = sorted(p for p in directory.glob("*.json"))
    for path in files:
        if limit is not None and stats.ingested >= limit:
            break
        stats.seen += 1
        if path.stem in existing:
            stats.skipped += 1
            continue
        try:
            parsed = parse_match(path, reg, stats)
        except (IngestionError, KeyError, ValueError) as exc:
            stats.warn(f"{path.name}: skipped - {exc}")
            stats.skipped += 1
            continue

        if season_filter and parsed["match"]["season"] not in season_filter:
            stats.skipped += 1
            continue

        innings_ids = []
        for row in parsed["innings"]:
            row["id"] = next_innings_id
            innings_ids.append(next_innings_id)
            next_innings_id += 1
        delivery_ids = []
        for row in parsed["deliveries"]:
            row["id"] = next_delivery_id
            row["innings_id"] = innings_ids[row.pop("_innings_index")]
            delivery_ids.append(next_delivery_id)
            next_delivery_id += 1
        for row in parsed["dismissals"]:
            row["delivery_id"] = delivery_ids[row.pop("_delivery_index")]
            row["innings_id"] = innings_ids[row.pop("_innings_index")]

        db.flush()  # materialise any newly seen Player rows before FK inserts
        db.execute(insert(Match), [parsed["match"]])
        if parsed["squad"]:
            db.execute(insert(MatchPlayer), parsed["squad"])
        if parsed["innings"]:
            db.execute(insert(Innings), parsed["innings"])
        if parsed["deliveries"]:
            db.execute(insert(Delivery), parsed["deliveries"])
        if parsed["dismissals"]:
            db.execute(insert(Dismissal), parsed["dismissals"])
        db.commit()

        stats.ingested += 1
        stats.deliveries += len(parsed["deliveries"])
        if stats.ingested % 100 == 0:
            log.info("ingested %s matches (%s deliveries)", stats.ingested, stats.deliveries)

    run.finished_at = dt.datetime.utcnow()
    run.matches_seen = stats.seen
    run.matches_ingested = stats.ingested
    run.matches_skipped = stats.skipped
    run.deliveries_ingested = stats.deliveries
    run.warnings = stats.warnings
    run.status = "completed"
    db.commit()
    return stats
