"""Attach ingested matches to competitions, seasons, stages and groups.

Shared by the importer (new matches) and the 0002 migration (backfilling a
database built before competitions existed), so both paths make identical
decisions.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from typing import Dict, Optional, Tuple

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app import catalog
from app.catalog import MatchContext, classify_stage
from app.models import (
    Competition,
    Country,
    Season,
    Team,
    TournamentGroup,
    TournamentStage,
)

log = logging.getLogger("stryk.linking")

#: Team type implied by the competition a club side plays in.
_TEAM_TYPE_FOR = {
    "FRANCHISE_LEAGUE": "FRANCHISE",
    "DOMESTIC": "DOMESTIC",
    "REGIONAL": "REGIONAL",
}


def season_identity(naming: str, season_label: Optional[str], first_date: dt.date) -> Tuple[str, int]:
    """(season name, start year) under a competition's naming rule.

    ``calendar_year`` uses the year the match was played: Cricsheet labels the
    2008 IPL "2007/08" and the 2020 UAE edition "2020/21", both wrong for IPL.
    ``source_label`` keeps the source's label, which is right for seasons that
    genuinely span two years (BBL "2023/24").
    """
    if naming == "calendar_year" or not season_label:
        return str(first_date.year), first_date.year
    label = str(season_label).strip()
    m = re.match(r"(\d{4})", label)
    return label, int(m.group(1)) if m else first_date.year


class Linker:
    def __init__(self, db: Session):
        self.db = db
        catalog.seed(db)
        self.catalogue = catalog.catalogue()["competitions"]
        self.competitions: Dict[str, Competition] = {
            c.slug: c for c in db.execute(select(Competition)).scalars()
        }
        self.seasons: Dict[Tuple[int, str], int] = {
            (s.competition_id, s.name): s.id for s in db.execute(select(Season)).scalars()
        }
        self.stages: Dict[Tuple[int, str], int] = {
            (s.season_id, s.name): s.id for s in db.execute(select(TournamentStage)).scalars()
        }
        self.groups: Dict[Tuple[int, str], int] = {
            (g.season_id, g.name): g.id for g in db.execute(select(TournamentGroup)).scalars()
        }

    def competition(self, ctx: MatchContext) -> Competition:
        entry = catalog.resolve(ctx, self.catalogue)
        if entry is not None:
            return self.competitions[entry["slug"]]
        # No catalogue entry claims this match. Show it, but invent nothing:
        # the competition carries only what the source said.
        slug = catalog.uncatalogued_slug(ctx)
        if slug not in self.competitions:
            row = Competition(
                slug=slug,
                name=ctx.event_name or "Unidentified competition",
                competition_type="OTHER",
                gender=ctx.gender,
                is_catalogued=False,
                formats=[ctx.match_type] if ctx.match_type else [],
                season_naming="source_label",
                match_rules=[],
            )
            self.db.add(row)
            self.db.flush()
            self.competitions[slug] = row
            log.info("created uncatalogued competition %s", slug)
        return self.competitions[slug]

    def link(
        self,
        ctx: MatchContext,
        season_label: Optional[str],
        first_date: dt.date,
        stage: Optional[str],
        group: Optional[str],
    ) -> dict:
        comp = self.competition(ctx)
        name, year = season_identity(comp.season_naming, season_label, first_date)
        key = (comp.id, name)
        if key not in self.seasons:
            row = Season(competition_id=comp.id, name=name, year=year,
                         points_system_id=comp.points_system_id, status="unknown")
            self.db.add(row)
            self.db.flush()
            self.seasons[key] = row.id
        season_id = self.seasons[key]

        stage_name, stage_type = classify_stage(stage, group)
        skey = (season_id, stage_name)
        if skey not in self.stages:
            row = TournamentStage(season_id=season_id, name=stage_name, stage_type=stage_type,
                                  sequence=0 if stage_type == "league" else 1)
            self.db.add(row)
            self.db.flush()
            self.stages[skey] = row.id
        group_id = None
        if group:
            gkey = (season_id, str(group))
            if gkey not in self.groups:
                row = TournamentGroup(season_id=season_id, stage_id=self.stages[skey], name=str(group))
                self.db.add(row)
                self.db.flush()
                self.groups[gkey] = row.id
            group_id = self.groups[gkey]
        return {
            "competition_id": comp.id,
            "season_id": season_id,
            "stage_id": self.stages[skey],
            "group_id": group_id,
            "_competition_type": comp.competition_type,
        }

    def classify_teams(self, team_ids, competition_type: str) -> None:
        """Give club sides a team type from the competition they play in.

        Only teams still marked OTHER are touched, so a national side or a team
        already classified is never overwritten.
        """
        team_type = _TEAM_TYPE_FOR.get(competition_type)
        if not team_type or not team_ids:
            return
        self.db.execute(
            update(Team)
            .where(Team.id.in_(list(team_ids)), Team.team_type == "OTHER")
            .values(team_type=team_type)
        )


def backfill_legacy(db: Session) -> int:
    """Link matches imported before competitions existed. Returns rows linked.

    Uses only what the old schema stored (event name, gender, format, stage,
    season label). The old schema did not keep Cricsheet's ``team_type`` or
    the source dataset, so a legacy match no catalogue event rule claims
    becomes an uncatalogued competition; re-importing it from its dataset
    assigns it properly.
    """
    from app.catalog import normalise_gender
    from app.ingestion.cricsheet import record_player_ids
    from app.models import DataSource, Match

    linker = Linker(db)
    source_id = db.execute(select(DataSource.id).where(DataSource.slug == "cricsheet")).scalar()
    rows = db.execute(
        select(Match.id, Match.event_name, Match.gender, Match.match_type, Match.season_label,
               Match.date, Match.stage, Match.result, Match.team1_id, Match.team2_id)
        .where(Match.competition_id.is_(None))
    ).all()
    for r in rows:
        gender = normalise_gender(r.gender)
        links = linker.link(
            MatchContext(r.event_name, gender, r.match_type, None),
            r.season_label, r.date, r.stage, None,
        )
        linker.classify_teams({r.team1_id, r.team2_id}, links.pop("_competition_type"))
        db.execute(
            update(Match).where(Match.id == r.id).values(
                **links,
                status="no_result" if r.result == "no result" else "completed",
                data_level=4,
                source_id=source_id,
                external_id=r.id,
            )
        )
        if gender == "WOMEN":
            db.execute(update(Team).where(Team.id.in_([r.team1_id, r.team2_id]))
                       .values(gender="WOMEN"))
    if rows:
        db.execute(text("""
            INSERT INTO external_id (entity_type, entity_id, source, external_id)
            SELECT 'match', m.id, 'cricsheet', m.id FROM match m
            WHERE NOT EXISTS (SELECT 1 FROM external_id e WHERE e.source = 'cricsheet'
                              AND e.entity_type = 'match' AND e.external_id = m.id)
        """))
        record_player_ids(db)
        refresh_derived(db)
    log.info("backfilled %d legacy match(es)", len(rows))
    return len(rows)


def link_countries(db: Session) -> int:
    """Attach every national team to its country, and give it the country's code.

    Cricsheet names a national side after the nation ("Sri Lanka", "Papua New
    Guinea"), so the join is on the name, with the alternative spellings a
    match file uses listed on the country as ``teams``. Nothing is guessed: a
    national team whose name no country claims keeps a null country and falls
    back to a plain badge, exactly as before.

    Idempotent, and the country code becomes the team's ``short_name`` only
    when it has none, so an explicitly configured abbreviation always wins.
    """
    by_name: Dict[str, Country] = {}
    for row in db.execute(select(Country)).scalars():
        by_name[row.name] = row
    for entry in catalog.catalogue()["countries"]:
        country = by_name.get(entry["name"])
        for alias in entry.get("teams", []):
            if country is not None:
                by_name[alias] = country

    linked = 0
    for team in db.execute(select(Team).where(Team.is_national_team.is_(True))).scalars():
        country = by_name.get(team.name)
        if country is None:
            continue
        team.country_id = country.id
        if not team.short_name:
            team.short_name = country.short_code
        linked += 1
    db.flush()
    return linked


def refresh_derived(db: Session, today: Optional[dt.date] = None) -> None:
    """Recompute season dates/format/status and team/player memberships.

    Pure derivations from match and squad rows, so they are rebuilt wholesale
    rather than maintained incrementally; at IPL scale this takes well under a
    second.
    """
    today = today or dt.date.today()
    link_countries(db)
    db.execute(text("""
        UPDATE season SET
          start_date = (SELECT MIN(m.date) FROM match m WHERE m.season_id = season.id),
          end_date   = (SELECT MAX(m.date) FROM match m WHERE m.season_id = season.id),
          format = CASE WHEN (SELECT COUNT(DISTINCT m.match_type) FROM match m
                              WHERE m.season_id = season.id) = 1
                        THEN (SELECT MIN(m.match_type) FROM match m WHERE m.season_id = season.id)
                        ELSE NULL END
    """))
    # Status: a season is completed when its final has been played. Calendar
    # seasons of international cricket complete with the year. Anything else
    # stays "unknown" - we hold completed matches only, so we cannot tell a
    # finished league from one whose remaining fixtures we simply lack.
    db.execute(text("""
        UPDATE season SET status = CASE
          WHEN EXISTS (SELECT 1 FROM match m JOIN tournament_stage s ON s.id = m.stage_id
                       WHERE m.season_id = season.id AND LOWER(s.name) = 'final')
            THEN 'completed'
          WHEN (SELECT c.competition_type FROM competition c WHERE c.id = season.competition_id)
                = 'INTERNATIONAL'
            THEN CASE WHEN season.year < :year THEN 'completed' ELSE 'in_progress' END
          ELSE 'unknown' END
    """), {"year": today.year})

    db.execute(text("DELETE FROM competition_team"))
    db.execute(text("""
        INSERT INTO competition_team (competition_id, season_id, team_id, group_id)
        SELECT competition_id, season_id, team_id, MAX(group_id) FROM (
          SELECT competition_id, season_id, team1_id AS team_id, group_id FROM match
            WHERE season_id IS NOT NULL
          UNION ALL
          SELECT competition_id, season_id, team2_id AS team_id, group_id FROM match
            WHERE season_id IS NOT NULL
        ) t GROUP BY competition_id, season_id, team_id
    """))
    db.execute(text("DELETE FROM player_team"))
    db.execute(text("""
        INSERT INTO player_team (player_id, team_id, competition_id, season_id, matches)
        SELECT mp.player_id, mp.team_id, m.competition_id, m.season_id, COUNT(DISTINCT m.id)
        FROM match_player mp JOIN match m ON m.id = mp.match_id
        WHERE m.season_id IS NOT NULL
        GROUP BY mp.player_id, mp.team_id, m.competition_id, m.season_id
    """))
