"""The competition catalogue: countries, competitions, points systems, sources.

The catalogue is data (the JSON files beside this module), not code: adding a
competition is a new JSON entry plus an ingest, never a new page or endpoint.
This module loads and validates it, writes it into the database, and resolves
which competition an ingested match belongs to.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    COMPETITION_TYPES,
    GENDERS,
    Competition,
    Country,
    DataSource,
    PointsSystem,
    SourceDataset,
)

HERE = Path(__file__).resolve().parent
TIE_BREAKERS = ("points", "wins", "net_run_rate", "wickets_per_ball")


class CatalogueError(ValueError):
    pass


def _load(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def catalogue() -> dict:
    """Load and validate every catalogue file. Raises CatalogueError on bad data."""
    return validate({
        "countries": _load("countries.json")["countries"],
        "competitions": _load("competitions.json")["competitions"],
        "points_systems": _load("points_systems.json")["points_systems"],
        "sources": _load("sources.json")["sources"],
    })


def validate(cat: dict) -> dict:
    countries, competitions = cat["countries"], cat["competitions"]
    points, sources = cat["points_systems"], cat["sources"]

    codes = {c["code"] for c in countries}
    point_slugs = {p["slug"] for p in points}
    dataset_keys = {(s["slug"], d["key"]) for s in sources for d in s["datasets"]}
    seen = set()
    for c in competitions:
        where = f"competition {c.get('slug')!r}"
        if c["slug"] in seen:
            raise CatalogueError(f"{where}: duplicate slug")
        seen.add(c["slug"])
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", c["slug"]):
            raise CatalogueError(f"{where}: slug must be lowercase-hyphenated")
        if c["type"] not in COMPETITION_TYPES:
            raise CatalogueError(f"{where}: unknown type {c['type']!r}")
        if c["gender"] not in GENDERS:
            raise CatalogueError(f"{where}: unknown gender {c['gender']!r}")
        if c.get("country") and c["country"] not in codes:
            raise CatalogueError(f"{where}: unknown country {c['country']!r}")
        if c.get("points_system") and c["points_system"] not in point_slugs:
            raise CatalogueError(f"{where}: unknown points system {c['points_system']!r}")
        if c["season_naming"] not in ("calendar_year", "source_label"):
            raise CatalogueError(f"{where}: bad season_naming")
        if "prominence" in c and c["prominence"] not in (1, 2, 3, 4, 5):
            raise CatalogueError(f"{where}: prominence must be 1-5, got {c['prominence']!r}")
        season = c.get("first_season")
        if season is not None and not (isinstance(season, int) and 1800 <= season <= 2100):
            raise CatalogueError(f"{where}: first_season must be a year, got {season!r}")
        for rule in c.get("match", []):
            if "dataset" in rule and (rule["provider"], rule["dataset"]) not in dataset_keys:
                raise CatalogueError(f"{where}: dataset {rule['dataset']!r} not in sources.json")
            if "event" in rule and rule.get("match_type") and c["formats"] \
                    and rule["match_type"] not in c["formats"]:
                raise CatalogueError(
                    f"{where}: event rule format {rule['match_type']!r} is not in formats"
                )
            if rule.get("gender") and rule["gender"] not in GENDERS:
                raise CatalogueError(f"{where}: bad rule gender")
        if not c.get("match") and not c.get("unavailable_reason"):
            raise CatalogueError(f"{where}: needs a match rule or an unavailable_reason")
    for p in points:
        bad = [t for t in p["tie_breakers"] if t not in TIE_BREAKERS]
        if bad:
            raise CatalogueError(f"points system {p['slug']!r}: unknown tie-breakers {bad}")
        if p["tie_resolution"] not in ("super_over", "shared"):
            raise CatalogueError(f"points system {p['slug']!r}: bad tie_resolution")
    return cat


# ------------------------------------------------------------------ seeding
def seed(db: Session) -> Dict[str, int]:
    """Upsert the catalogue into the database. Idempotent; returns slug -> id."""
    cat = catalogue()

    countries = {c.short_code: c for c in db.execute(select(Country)).scalars()}
    for c in cat["countries"]:
        row = countries.get(c["code"]) or Country(short_code=c["code"])
        row.name, row.flag, row.cricket_board = c["name"], c["flag"], c["cricket_board"]
        db.add(row)
        countries[c["code"]] = row

    systems = {p.slug: p for p in db.execute(select(PointsSystem)).scalars()}
    for p in cat["points_systems"]:
        row = systems.get(p["slug"]) or PointsSystem(slug=p["slug"])
        row.name, row.rules = p["name"], p
        db.add(row)
        systems[p["slug"]] = row

    sources = {s.slug: s for s in db.execute(select(DataSource)).scalars()}
    for s in cat["sources"]:
        row = sources.get(s["slug"]) or DataSource(slug=s["slug"])
        row.name, row.url, row.licence = s["name"], s["url"], s["licence"]
        row.attribution, row.data_level = s["attribution"], s["data_level"]
        row.update_frequency, row.limitations = s["update_frequency"], s["limitations"]
        row.checked_on = dt.date.fromisoformat(s["checked_on"])
        db.add(row)
        db.flush()
        sources[s["slug"]] = row
        existing = {d.key: d for d in db.execute(
            select(SourceDataset).where(SourceDataset.source_id == row.id)).scalars()}
        for d in s["datasets"]:
            ds = existing.get(d["key"]) or SourceDataset(source_id=row.id, key=d["key"])
            ds.name, ds.url = d["name"], d["url"]
            ds.published_matches, ds.withheld_matches = d["matches"], d["withheld"]
            db.add(ds)
    db.flush()

    comps = {c.slug: c for c in db.execute(select(Competition)).scalars()}
    for c in cat["competitions"]:
        row = comps.get(c["slug"]) or Competition(slug=c["slug"])
        row.name, row.short_name = c["name"], c["short_name"]
        row.competition_type, row.gender = c["type"], c["gender"]
        row.country_id = countries[c["country"]].id if c.get("country") else None
        row.governing_body, row.description = c.get("governing_body"), c.get("description")
        row.is_active, row.formats = c.get("is_active", True), c.get("formats", [])
        row.season_naming = c["season_naming"]
        row.points_system_id = systems[c["points_system"]].id if c.get("points_system") else None
        row.match_rules, row.is_catalogued = c.get("match", []), True
        row.unavailable_reason = c.get("unavailable_reason")
        db.add(row)
        comps[c["slug"]] = row
    db.flush()
    return {slug: row.id for slug, row in comps.items()}


# --------------------------------------------------------------- resolution
@dataclass(frozen=True)
class MatchContext:
    """What a source tells us about a match, before we know its competition."""

    event_name: Optional[str]
    gender: str  # MEN | WOMEN | MIXED | UNKNOWN
    match_type: Optional[str]
    team_type: Optional[str]  # "international" | "club" | None
    provider: str = "cricsheet"
    dataset: Optional[str] = None


def normalise_gender(raw: Optional[str]) -> str:
    return {"male": "MEN", "female": "WOMEN", "men": "MEN", "women": "WOMEN",
            "mixed": "MIXED"}.get((raw or "").strip().lower(), "UNKNOWN")


def _rule_matches(rule: dict, ctx: MatchContext, kind: str) -> bool:
    if rule.get("gender") and rule["gender"] != ctx.gender:
        return False
    if kind == "event":
        if "event" not in rule or rule["event"] != ctx.event_name:
            return False
        # One event name can cover more than one format: the men's Asia Cup is
        # "Asia Cup" whether it is played as ODIs or T20s, and the two are
        # separate competitions here because no analysis may pool formats.
        return rule.get("match_type") in (None, ctx.match_type)
    if kind == "dataset":
        return ("dataset" in rule and rule["dataset"] == ctx.dataset
                and rule.get("provider", "cricsheet") == ctx.provider)
    if kind == "international":
        return ("team_type" in rule and rule["team_type"] == ctx.team_type
                and rule.get("match_type") == ctx.match_type)
    return False


def resolve(ctx: MatchContext, competitions: List[dict]) -> Optional[dict]:
    """Pick the catalogue competition for a match, or None if none claims it.

    Order matters and goes from most to least specific: a verified event name,
    then the dataset the match was imported from, then the generic
    international rule (bilateral matches by gender and format).
    """
    for kind in ("event", "dataset", "international"):
        for comp in competitions:
            if any(_rule_matches(r, ctx, kind) for r in comp.get("match", [])):
                return comp
    return None


def uncatalogued_slug(ctx: MatchContext) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (ctx.event_name or "unknown-event").lower()).strip("-")
    suffix = {"MEN": "men", "WOMEN": "women"}.get(ctx.gender, "unknown")
    return f"{base or 'unknown-event'}-{suffix}"[:80]


# ------------------------------------------------------------------ stages
_KNOCKOUT = re.compile(
    r"\b(final|semi|quarter|qualifier|eliminator|play-?off|knockout|elimination|challenger)\b", re.I
)


def classify_stage(stage: Optional[str], group: Optional[str]) -> tuple[str, str]:
    """(stage name, stage type) for a match's ``event.stage`` / ``event.group``.

    A match with neither is in the league stage. Knockout is recognised by
    name; any other named stage ("Super 8") is treated as a group stage, which
    is what such rounds are, rather than assumed to be a knockout.
    """
    if stage:
        return stage, ("knockout" if _KNOCKOUT.search(stage) else "group")
    if group:
        return "Group stage", "group"
    return "League", "league"
