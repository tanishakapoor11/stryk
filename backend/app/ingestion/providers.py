"""Provider abstraction.

A provider turns one external source into STRYK rows. Everything above this
layer - linking to competitions, coverage, analytics - is provider-neutral, so
adding a source (a licensed scorecard feed at data level 2, say) is a new
``Provider`` subclass, not a change to the schema or the API.

Each provider declares the highest data level it can supply. The importer
stamps every match with the level actually ingested, so a competition can be
listed from a level-1 fixture feed long before any ball-by-ball data exists.
"""

from __future__ import annotations

import abc
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app import catalog
from app.models import DATA_LEVEL_BALL_BY_BALL


class Provider(abc.ABC):
    #: Matches DataSource.slug and the catalogue's sources.json.
    slug: str
    #: Highest level this provider can supply (see app.models DATA_LEVEL_*).
    data_level: int

    def source(self) -> dict:
        for s in catalog.catalogue()["sources"]:
            if s["slug"] == self.slug:
                return s
        raise KeyError(f"provider {self.slug!r} has no entry in catalog/sources.json")

    def datasets(self) -> List[dict]:
        """Datasets this provider publishes, as recorded in the source registry."""
        return self.source()["datasets"]

    @abc.abstractmethod
    def ingest(self, db: Session, location: Path, dataset: Optional[str] = None, **options):
        """Import from a local copy of one dataset; must be idempotent."""


class CricsheetProvider(Provider):
    slug = "cricsheet"
    data_level = DATA_LEVEL_BALL_BY_BALL

    def ingest(self, db: Session, location: Path, dataset: Optional[str] = None, **options):
        from app.ingestion.cricsheet import ingest_directory

        return ingest_directory(db, location, dataset=dataset, **options)


PROVIDERS: Dict[str, Provider] = {p.slug: p for p in (CricsheetProvider(),)}


def get(slug: str) -> Provider:
    try:
        return PROVIDERS[slug]
    except KeyError:
        raise KeyError(f"unknown provider {slug!r}; known: {sorted(PROVIDERS)}") from None
