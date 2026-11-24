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
from app.catalog import HERE as CATALOG_DIR
from app.catalog import MatchContext, normalise_gender
from app.models import (
    DATA_LEVEL_BALL_BY_BALL,
    DataSource,
    Delivery,
    Dismissal,
    ExternalId,
    IngestionLog,
    Innings,
    Match,
    MatchOfficial,
    MatchPlayer,
    Player,
    Team,
    Venue,
)

log = logging.getLogger("stryk.ingest")

def _team_config() -> dict:
    """Renames and short names, from app/catalog/teams.json (data, not code)."""
    return json.loads((CATALOG_DIR / "teams.json").read_text(encoding="utf-8"))


_TEAMS = _team_config()
#: Back-compat view of the men's renames, used by tests and older callers.
TEAM_CANONICAL: Dict[str, str] = _TEAMS["renames"].get("MEN", {})
TEAM_SHORT: Dict[str, str] = _TEAMS["short_names"].get("MEN", {})

#: Cricsheet officials keys -> MatchOfficial.role
OFFICIAL_ROLES = {
    "umpires": "umpire",
    "tv_umpires": "tv_umpire",
    "reserve_umpires": "reserve_umpire",
    "match_referees": "match_referee",
}


def normalise_match_type(info: dict) -> str:
    """The format STRYK records, which is not always the source's label.

    Cricsheet files The Hundred as "T20" with 5-ball overs. It is a different
    format (100 balls, a 25-ball powerplay), and pooling it with T20 records
    would compare unlike things, so it is stored as "Hundred".
    """
    raw = info.get("match_type", "T20")
    if raw == "T20" and info.get("balls_per_over") == 5:
        return "Hundred"
    return raw


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
        #: Keyed by (name, gender): "India" men and "India" women are two teams.
        self.teams: Dict[tuple, int] = {
            (name, gender): tid
            for tid, name, gender in db.execute(select(Team.id, Team.name, Team.gender)).all()
        }
        self.venues: Dict[str, int] = {
            name: vid for vid, name in db.execute(select(Venue.id, Venue.name)).all()
        }
        self.players: set = {pid for (pid,) in db.execute(select(Player.id)).all()}

    def team(self, raw_name: str, gender: str = "MEN", national: bool = False) -> int:
        renames = _TEAMS["renames"].get(gender, {})
        name = renames.get(raw_name, raw_name)
        key = (name, gender)
        if key not in self.teams:
            aliases = sorted(k for k, v in renames.items() if v == name)
            row = Team(
                name=name,
                short_name=_TEAMS["short_names"].get(gender, {}).get(name),
                aliases=aliases,
                gender=gender,
                team_type="NATIONAL" if national else "OTHER",
                is_national_team=national,
            )
            self.db.add(row)
            self.db.flush()
            self.teams[key] = row.id
        return self.teams[key]

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


def _outcome(info: dict, team) -> dict:
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
        res["winner_id"] = team(out["winner"])
        by = out.get("by") or {}
        for key in ("runs", "wickets", "innings"):
            if key in by:
                res["result_type"] = key
                res["result_margin"] = by[key] if key != "innings" else None
    if "eliminator" in out:
        # Super over: the match is a tie decided by the eliminator.
        res["result"] = "tie"
        res["eliminator_id"] = team(out["eliminator"])
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
    match_type = normalise_match_type(info)
    event = info.get("event") or {}
    if isinstance(event, str):
        event = {"name": event}
    gender = normalise_gender(info.get("gender", "male"))
    national = info.get("team_type") == "international"

    def team(name: str) -> int:
        return reg.team(name, gender=gender, national=national)

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
        "team1_id": team(teams[0]),
        "team2_id": team(teams[1]),
        "toss_winner_id": team(info["toss"]["winner"]) if info.get("toss") else None,
        "toss_decision": (info.get("toss") or {}).get("decision"),
        "player_of_match_id": pid(info["player_of_match"][0]) if info.get("player_of_match") else None,
        "balls_per_over": info.get("balls_per_over", 6),
        "overs_limit": info.get("overs"),
        "source_file": path.name,
        "external_id": match_id,
        "data_level": DATA_LEVEL_BALL_BY_BALL,
        **_outcome(info, team),
    }
    outcome_result = match_row["result"]
    match_row["status"] = "no_result" if outcome_result == "no result" else "completed"

    squad_rows = []
    for team_name, names in (info.get("players") or {}).items():
        tid = team(team_name)
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
        batting_id = team(inn["team"])
        bowling_id = next(team(t) for t in teams if team(t) != batting_id)
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

    officials = []
    for key, role in OFFICIAL_ROLES.items():
        for name in (info.get("officials") or {}).get(key, []) or []:
            ident = people.get(name)
            if ident is None:
                stats.warn(f"{match_id}: official {name!r} missing from registry")
                continue
            officials.append({"match_id": match_id, "player_id": reg.player(ident, name), "role": role})

    context = MatchContext(
        event_name=event.get("name"),
        gender=gender,
        match_type=match_type,
        team_type=info.get("team_type"),
    )
    return {
        "match": match_row,
        "context": context,
        "season_label": str(info.get("season", season)),
        "stage": event.get("stage"),
        "group": event.get("group"),
        "officials": officials,
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
    dataset: Optional[str] = None,
) -> IngestStats:
    """Import every Cricsheet JSON file in ``directory``.

    Already-imported matches are skipped by id, so the importer is safe to
    re-run and to point at a directory containing additional seasons.

    ``dataset`` is the Cricsheet dataset key the directory came from ("ipl",
    "wpl", "t20s" ...). It lets the catalogue assign competitions whose source
    event names have not been verified; it defaults to the directory name with
    any "_json" suffix removed.
    """
    from app.ingestion.linking import Linker, refresh_derived

    dataset = dataset or directory.name.removesuffix("_json")
    stats = IngestStats()
    run = IngestionLog(source=str(directory), status="running", warnings=[])
    db.add(run)
    db.commit()

    linker = Linker(db)
    source_id = db.execute(select(DataSource.id).where(DataSource.slug == "cricsheet")).scalar()
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

        ctx = parsed["context"]
        links = linker.link(
            MatchContext(ctx.event_name, ctx.gender, ctx.match_type, ctx.team_type,
                         provider="cricsheet", dataset=dataset),
            parsed["season_label"],
            parsed["match"]["date"],
            parsed["stage"],
            parsed["group"],
        )
        linker.classify_teams(
            {parsed["match"]["team1_id"], parsed["match"]["team2_id"]},
            links.pop("_competition_type"),
        )
        parsed["match"].update(links, source_id=source_id, source_dataset=dataset)

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
        # Cricsheet occasionally lists one registry person in both squads of a
        # match (e.g. 1130677, KV Sharma for Vidarbha and Railways), which the
        # (match_id, player_id) unique constraint rejects. Keep the first row,
        # same as officials below.
        squad = list({(r["match_id"], r["player_id"]): r for r in parsed["squad"]}.values())
        if squad:
            db.execute(insert(MatchPlayer), squad)
        officials = list({(o["player_id"], o["role"]): o for o in parsed["officials"]}.values())
        if officials:
            db.execute(insert(MatchOfficial), officials)
        db.execute(insert(ExternalId), [{"entity_type": "match", "entity_id": parsed["match"]["id"],
                                         "source": "cricsheet", "external_id": parsed["match"]["id"]}])
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

    record_player_ids(db)
    refresh_derived(db)
    run.finished_at = dt.datetime.utcnow()
    run.matches_seen = stats.seen
    run.matches_ingested = stats.ingested
    run.matches_skipped = stats.skipped
    run.deliveries_ingested = stats.deliveries
    run.warnings = stats.warnings
    run.status = "completed"
    db.commit()
    return stats


def record_player_ids(db: Session) -> None:
    """Map every person to their Cricsheet registry id in ``external_id``.

    The Cricsheet id is also the STRYK player id, so this is the identity row
    future providers join against when they bring their own ids.
    """
    from sqlalchemy import text

    db.execute(text("""
        INSERT INTO external_id (entity_type, entity_id, source, external_id)
        SELECT 'player', p.id, 'cricsheet', p.id FROM player p
        WHERE NOT EXISTS (SELECT 1 FROM external_id e WHERE e.source = 'cricsheet'
                          AND e.entity_type = 'player' AND e.external_id = p.id)
    """))
