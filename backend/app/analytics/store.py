"""In-memory fact table + filter vocabulary for the analytics layer.

Every analytic in Stryk is a pandas aggregation over one denormalised ball
table, which is far cheaper to maintain - and faster - than a bespoke SQL
query per metric, and keeps the statistical rules in one place.

The ball table is read **per competition scope**, not whole. The database
holds every competition (~12M deliveries); a single analysis never spans more
than one competition set, and reading all of it at startup cost minutes and
gigabytes before the API served its first request. :func:`load` therefore
reads only the reference tables, and :func:`scoped` reads that scope's
deliveries on first use and caches them.

ponytail: in-memory per-scope fact table; move to materialised SQL aggregates
if one competition grows past a few million deliveries or the API runs
multi-process.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence

import pandas as pd
from sqlalchemy import case, func, select

from app.core.config import settings
from app.core.db import engine
from app.models import (
    Competition,
    Country,
    DataSource,
    PointsSystem,
    SourceDataset,
    Delivery,
    Dismissal,
    Innings,
    Match,
    MatchPlayer,
    Player,
    Season,
    Team,
    TournamentStage,
    Venue,
)

log = logging.getLogger("stryk.store")
_lock = threading.Lock()
_totals_lock = threading.Lock()
_cache: Optional["Dataset"] = None
_totals: Optional["pd.DataFrame"] = None
_scoped: "dict[tuple, Dataset]" = {}
#: One lock per scope, so concurrent requests for the same cold scope wait for
#: one read instead of each running their own. A page asks for its scope from
#: several endpoints at once, and reading a competition's deliveries is seconds
#: of random I/O over a multi-gigabyte table.
_scope_locks: "dict[tuple, threading.Lock]" = {}
# The scope cache is bounded by rows, not by entries, because competitions
# differ by an order of magnitude: the IPL is ~300k deliveries (~140 MB) and
# the County Championship ~2.5M (~1.2 GB). Counting entries would either hold
# four County-sized scopes - five gigabytes, and the machine starts swapping,
# which is far slower than re-reading - or evict ten cheap ones needlessly.
# Least recently used goes first: a reader moving around one competition must
# not lose it because they glanced at another.
_SCOPE_ROW_BUDGET = 5_000_000


#: Cricsheet splits twenty-over internationals by the status of the teams -
#: "T20" where a full member is involved, "IT20" between associate members -
#: but they are one format played under one set of rules, and the ICC has
#: recognised both as T20Is since 2019. Pooling them is sound; keeping them
#: apart would split the Asian Games in half and refuse the result as a scope
#: spanning two formats.
FORMAT_ALIASES = {"IT20": "T20"}


def canonical_format(match_type) -> Optional[str]:
    """The format a match is played under, whatever the source calls it."""
    if match_type is None:
        return None
    return FORMAT_ALIASES.get(str(match_type), str(match_type))


class ScopeError(ValueError):
    """A requested scope would mix records that must never be pooled."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Scope:
    """Which competitions an analysis covers.

    Always a single gender and a single match format: a career record that
    pooled men's and women's cricket, or T20 and Test cricket, would be
    meaningless, so a scope that would do so is refused rather than computed.
    """

    competition_ids: tuple
    slugs: tuple
    names: tuple
    gender: Optional[str]
    match_type: Optional[str]

    def describe(self) -> dict:
        return {"competitions": list(self.slugs), "gender": self.gender,
                "format": self.match_type}


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
    competitions: pd.DataFrame = field(default_factory=pd.DataFrame)
    seasons: pd.DataFrame = field(default_factory=pd.DataFrame)
    stages: pd.DataFrame = field(default_factory=pd.DataFrame)
    innings: pd.DataFrame = field(default_factory=pd.DataFrame)
    #: Small reference tables: countries, points_systems, sources, source_datasets.
    registry: dict = field(default_factory=dict)
    #: None for the unscoped (whole-database) dataset.
    scope: Optional[Scope] = None

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
    """Read the reference tables. Deliveries are read per scope by :func:`scoped`."""
    matches = _read(select(Match))
    players = _read(select(Player))
    teams = _read(select(Team))
    squads = _read(select(MatchPlayer))
    venues = _read(select(Venue))
    competitions = _read(select(Competition))
    seasons = _read(select(Season))
    stages = _read(select(TournamentStage))
    innings = _read(select(Innings))
    registry = {
        "countries": _read(select(Country)),
        "points_systems": _read(select(PointsSystem)),
        "sources": _read(select(DataSource)),
        "source_datasets": _read(select(SourceDataset)),
    }

    if not matches.empty:
        matches["date"] = pd.to_datetime(matches["date"])

    # No competitions: an empty ball table of the right shape, through the same
    # path a real scope takes, so every caller sees the same columns.
    deliveries = load_deliveries([], matches)

    ds = Dataset(
        deliveries=deliveries,
        positions=batting_positions(deliveries),
        matches=matches,
        players=prepare_players(players),
        teams=teams.set_index("id") if not teams.empty else teams,
        squads=squads,
        venues=venues.set_index("id") if not venues.empty else venues,
        loaded_at=dt.datetime.utcnow(),
        competitions=competitions.set_index("id") if not competitions.empty else competitions,
        seasons=seasons.set_index("id") if not seasons.empty else seasons,
        stages=stages.set_index("id") if not stages.empty else stages,
        innings=innings,
        registry=registry,
    )
    log.info("loaded %s matches; deliveries are read per competition", len(matches))
    return ds


#: Disk kept for cached scope frames, oldest evicted first. Roughly the size
#: of the database itself, and only competitions someone opened are stored.
_SCOPE_DISK_BUDGET = 4_000_000_000


#: Bumped whenever the delivery frame gains or loses a column. Cached pickles
#: are keyed by it, so an old cache is ignored rather than served without the
#: column its reader expects.
_FRAME_VERSION = 3


def _scope_cache_path(competition_ids: Sequence[int]) -> Path:
    name = "-".join(str(int(i)) for i in competition_ids)
    if len(name) > 80:  # a scope of many competitions: name it by its digest
        name = hashlib.sha1(name.encode()).hexdigest()[:20]
    return (Path(str(engine.url.database or "")).parent / "scopes"
            / f"{name}-v{_FRAME_VERSION}.pkl")


def _evict_scope_files(keep: Path) -> None:
    """Hold the disk cache to its budget, least recently written first."""
    files = sorted((f for f in keep.parent.glob("*.pkl")), key=lambda f: f.stat().st_mtime)
    total = sum(f.stat().st_size for f in files)
    for f in files:
        if total <= _SCOPE_DISK_BUDGET:
            return
        if f == keep:
            continue
        total -= f.stat().st_size
        f.unlink(missing_ok=True)


def load_deliveries(competition_ids: Sequence[int], matches: pd.DataFrame) -> pd.DataFrame:
    """The enriched ball table for one set of competitions.

    Scoping happens in SQL rather than by filtering a whole-database frame, so
    opening the IPL reads the IPL's ~300k deliveries and not all ~12M.

    The result is also kept on disk. Reading a competition out of the database
    means an index lookup per match and millions of rows built one at a time -
    7s for men's ODIs, 13s for the County Championship - while reading the
    same frame back from a pickle takes 0.3s. The ball table never changes
    except by ingestion, so the copy is good until the database is written to.
    """
    cache = _scope_cache_path(competition_ids) if competition_ids else None
    if cache is not None:
        try:
            if cache.exists() and cache.stat().st_mtime >= _db_mtime():
                return pd.read_pickle(cache)
        except Exception as exc:  # a truncated or half-written cache is not fatal
            log.warning("ignoring unreadable scope cache %s: %s", cache, exc)

    scope_matches = select(Match.id).where(Match.competition_id.in_(list(competition_ids)))
    deliveries = _read(select(Delivery).where(Delivery.match_id.in_(scope_matches)))
    dismissals = _read(select(Dismissal).where(Dismissal.match_id.in_(scope_matches)))
    deliveries = enrich(deliveries, dismissals)
    md = matches.set_index("id") if not matches.empty else None
    for col in ("date", "match_type", "competition_id", "season_id"):
        deliveries[col] = deliveries["match_id"].map(md[col]) if md is not None else None
    deliveries["date"] = pd.to_datetime(deliveries["date"])
    # The runs required to win, attached to each ball of the chase so that
    # "in a 180+ chase" is one filter and not a join the caller has to do.
    # Null for a first innings, which has no target - and a null never
    # satisfies a >= or <= comparison, so those balls drop out by themselves.
    targets = _read(select(Innings.id, Innings.target_runs))
    deliveries["target_runs"] = (
        deliveries["innings_id"].map(targets.set_index("id")["target_runs"])
        if not targets.empty else pd.NA
    )
    # The winning side, attached to each ball so "in a winning cause" is a
    # filter rather than a join. Null where no winner was recorded - an
    # abandoned match, or a tie with no super over - and such a match
    # satisfies neither "won" nor "lost". A tie settled by a super over does
    # have a winner, and counts as one.
    deliveries["winner_id"] = (
        deliveries["match_id"].map(md["winner_id"]) if md is not None else pd.NA
    )

    # A handful of distinct values repeated on every ball: as a category this
    # costs ~0.3 MB instead of ~17 MB per 300k deliveries. It is only ever
    # filtered on (never grouped by), so category semantics cannot leak.
    deliveries["match_type"] = deliveries["match_type"].astype("category")

    if cache is not None:
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache.with_suffix(".tmp")
            deliveries.to_pickle(tmp)
            tmp.replace(cache)  # atomic: a reader never sees a half-written frame
            _evict_scope_files(cache)
        except OSError as exc:
            log.warning("could not cache scope %s: %s", cache, exc)
    return deliveries


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
    global _cache, _totals
    with _lock:
        _cache = load()
        # An explicit reload means the data changed, so the aggregate is rebuilt
        # from the ball table rather than trusted from disk.
        _totals = None
        _totals_path().unlink(missing_ok=True)
        # An explicit reload means the ball table may have changed under us.
        shutil.rmtree(_scope_cache_path([0]).parent, ignore_errors=True)
        _scoped.clear()
        _scope_locks.clear()
    return _cache


#: Per competition and batter: runs off the bat (super overs excluded, as
#: everywhere else) and balls bowled. The only figure the API needs over every
#: competition at once - the home page's totals and its suggested names.
_BALL_TOTALS = (
    select(
        Match.competition_id.label("competition_id"),
        Delivery.batter_id.label("batter_id"),
        func.sum(case((Delivery.is_super_over == False, Delivery.batter_runs),  # noqa: E712
                      else_=0)).label("runs"),
        func.count().label("balls"),
    )
    .join(Match, Match.id == Delivery.match_id)
    .group_by(Match.competition_id, Delivery.batter_id)
)


def _totals_path() -> Path:
    return Path(str(engine.url.database or "")).with_name("agg_ball_totals.pkl")


def _db_mtime() -> float:
    """When the database last changed, WAL included."""
    path = Path(str(engine.url.database or ""))
    return max((p.stat().st_mtime for p in (path, path.with_name(path.name + "-wal"))
                if p.exists()), default=0.0)


def ball_totals() -> pd.DataFrame:
    """:data:`_BALL_TOTALS`, cached on disk.

    It scans every delivery - ~30s over 12M of them - which would otherwise be
    paid on the first home-page request of every restart. The result only changes when
    the database does, so it is kept beside it and rebuilt on a newer mtime.
    """
    global _totals
    with _totals_lock:
        if _totals is not None:
            return _totals
        cache = _totals_path()
        try:
            if cache.exists() and cache.stat().st_mtime >= _db_mtime():
                _totals = pd.read_pickle(cache)
                return _totals
        except Exception as exc:  # a stale or truncated cache must never be fatal
            log.warning("ignoring unreadable aggregate cache %s: %s", cache, exc)
        log.info("building whole-database ball totals (one full scan)")
        _totals = _read(_BALL_TOTALS)
        try:
            _totals.to_pickle(cache)
        except OSError as exc:
            log.warning("could not write aggregate cache %s: %s", cache, exc)
        return _totals


def resolve_scope(ds: Dataset, slugs: Optional[Sequence[str]] = None) -> Scope:
    """Turn competition slugs (or ids) into a validated :class:`Scope`.

    No slugs means the configured default competition, which keeps every
    pre-existing URL meaning exactly what it meant when STRYK was IPL-only.
    """
    requested = list(slugs) if slugs else [settings.default_competition]
    comps = ds.competitions
    if comps.empty:
        raise ScopeError(503, "No competitions are loaded. Run scripts/migrate.py or an ingest.")
    by_slug = {str(slug): int(cid) for cid, slug in comps["slug"].items()}
    ids = []
    for token in requested:
        token = str(token).strip().lower()
        if token in by_slug:
            ids.append(by_slug[token])
        elif token.isdigit() and int(token) in comps.index:
            ids.append(int(token))
        else:
            raise ScopeError(404, f"Unknown competition {token!r}")
    ids = sorted(set(ids))
    genders = sorted(set(comps.loc[ids, "gender"]))
    if len(genders) > 1:
        raise ScopeError(422, "Men's and women's competitions cannot be combined in one analysis.")
    m = ds.matches[ds.matches["competition_id"].isin(ids)] if not ds.matches.empty else ds.matches
    formats = sorted({canonical_format(x) for x in m["match_type"]}) if not m.empty else []
    if len(formats) > 1:
        raise ScopeError(
            422, f"These competitions span formats {formats}; choose competitions of one format."
        )
    return Scope(
        competition_ids=tuple(ids),
        slugs=tuple(comps.loc[ids, "slug"]),
        names=tuple(comps.loc[ids, "name"]),
        gender=genders[0] if genders else None,
        match_type=formats[0] if formats else None,
    )


def scoped(scope: Scope, base: Optional[Dataset] = None) -> Dataset:
    """A view of the dataset restricted to ``scope``'s competitions (cached)."""
    base = base or get()
    key = (id(base), scope.competition_ids)
    hit = _touch(key)
    if hit is not None:
        return hit
    with _lock:
        loading = _scope_locks.setdefault(key, threading.Lock())
    with loading:
        # Another request may have finished this scope while we waited for it.
        hit = _touch(key)
        if hit is not None:
            return hit
        return _build_scope(key, scope, base)


def _touch(key) -> Optional[Dataset]:
    """The cached scope, marked as most recently used."""
    with _lock:
        hit = _scoped.pop(key, None)
        if hit is not None:
            _scoped[key] = hit
        return hit


def _build_scope(key, scope: Scope, base: Dataset) -> Dataset:
    ids = set(scope.competition_ids)
    matches = base.matches[base.matches["competition_id"].isin(ids)] if not base.matches.empty else base.matches
    match_ids = set(matches["id"]) if not matches.empty else set()
    deliveries = load_deliveries(scope.competition_ids, base.matches)
    log.info("scope %s: %s deliveries", list(scope.slugs), len(deliveries))
    view = Dataset(
        deliveries=deliveries,
        positions=batting_positions(deliveries),
        matches=matches,
        # The player registry stays whole so names always resolve; search and
        # directories are limited to the scope through squads and deliveries.
        players=base.players,
        teams=base.teams,
        squads=base.squads[base.squads["match_id"].isin(match_ids)] if not base.squads.empty else base.squads,
        venues=base.venues,
        loaded_at=base.loaded_at,
        competitions=base.competitions,
        seasons=base.seasons,
        stages=base.stages,
        innings=base.innings[base.innings["match_id"].isin(match_ids)] if not base.innings.empty else base.innings,
        registry=base.registry,
        scope=scope,
    )
    with _lock:
        _scoped[key] = view
        rows = sum(len(d.deliveries) for d in _scoped.values())
        # Always keep what was just read, however big it is: the request that
        # paid for it is about to use it.
        while len(_scoped) > 1 and rows > _SCOPE_ROW_BUDGET:
            evicted = _scoped.pop(next(iter(_scoped)))  # insertion order == least recently used
            rows -= len(evicted.deliveries)
    return view


def get_scoped(slugs: Optional[Sequence[str]] = None) -> Dataset:
    base = get()
    return scoped(resolve_scope(base, slugs), base)


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
    #: Season row ids. Unlike ``seasons`` (calendar years) these identify a
    #: competition's season exactly, including ones spanning two years.
    season_ids: Optional[List[int]] = None
    #: Inclusive over range as a person counts overs: "overs 17 to 20" is
    #: (17, 20). Deliveries carry Cricsheet's 0-based number, so :func:`apply`
    #: shifts by one. This generalises ``phases`` - a fixed three-way split -
    #: and the two intersect when both are given.
    over_from: Optional[int] = None
    over_to: Optional[int] = None
    #: Inclusive range on the runs required to win, so "a 180+ chase" is
    #: ``target_from=180``. Only deliveries in a second innings carry a target,
    #: so either bound also implies the delivery is part of a chase.
    target_from: Optional[int] = None
    target_to: Optional[int] = None
    #: "won" or "lost", from the point of view of whichever side
    #: :func:`apply` is filtering on - the batting side for a batting view,
    #: the bowling side for a bowling one. A tie or an abandoned match has no
    #: winner and so is in neither, which is the honest answer: "in a winning
    #: cause" is not a claim anyone makes about an abandoned match.
    result: Optional[str] = None
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
                "season_ids": self.season_ids,
                "over_from": self.over_from,
                "over_to": self.over_to,
                "target_from": self.target_from,
                "target_to": self.target_to,
                "result": self.result,
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
    if f.season_ids:
        mask &= df["season_id"].isin(f.season_ids)
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
    if f.over_from is not None:
        mask &= df["over"] >= f.over_from - 1
    if f.over_to is not None:
        mask &= df["over"] <= f.over_to - 1
    if f.target_from is not None:
        mask &= df["target_runs"].notna() & (df["target_runs"] >= f.target_from)
    if f.target_to is not None:
        mask &= df["target_runs"].notna() & (df["target_runs"] <= f.target_to)
    if f.innings_number is not None:
        mask &= df["innings_number"] == f.innings_number
    if f.chasing is not None:
        mask &= df["is_chase"] == f.chasing
    if f.date_from is not None:
        mask &= df["date"] >= pd.Timestamp(f.date_from)
    if f.date_to is not None:
        mask &= df["date"] <= pd.Timestamp(f.date_to)
    if f.result == "won":
        mask &= df["winner_id"].notna() & (df["winner_id"] == df[team_column])
    elif f.result == "lost":
        mask &= df["winner_id"].notna() & (df["winner_id"] != df[team_column])
    return df[mask]
