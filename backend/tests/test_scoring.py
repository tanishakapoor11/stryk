"""Statistical correctness tests built on hand-worked match scenarios.

Each scenario is a miniature Cricsheet document pushed through the real
parser and the real aggregation code, with the expected figures worked out by
hand in the docstring. If a scoring rule ever changes, these fail.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd
import pytest

from app.analytics import metrics, store
from app.analytics.constants import phase_for_over
from app.ingestion.cricsheet import IngestStats, parse_match


class StubRegistry:
    """Stands in for the DB-backed registry: ids are the names themselves."""

    def __init__(self):
        self.ids = {}

    def team(self, name, gender="MEN", national=False):
        return self.ids.setdefault(("team", name, gender), len(self.ids) + 1)

    def venue(self, name, city):
        return 1

    def player(self, pid, name):
        return pid


def build_match(innings, match_id="test001", season="2024", date="2024-04-01"):
    people = {}
    for inn in innings:
        for over in inn["overs"]:
            for d in over["deliveries"]:
                for key in ("batter", "bowler", "non_striker"):
                    people.setdefault(d[key], d[key])
                for w in d.get("wickets", []):
                    people.setdefault(w["player_out"], w["player_out"])
                    for fl in w.get("fielders", []):
                        people.setdefault(fl["name"], fl["name"])
    return {
        "meta": {"data_version": "1.1.0"},
        "info": {
            "balls_per_over": 6,
            "dates": [date],
            "event": {"name": "Test League"},
            "gender": "male",
            "match_type": "T20",
            "outcome": {"winner": "Alpha", "by": {"runs": 10}},
            "overs": 20,
            "players": {"Alpha": sorted(people), "Beta": []},
            "registry": {"people": people},
            "season": season,
            "team_type": "club",
            "teams": ["Alpha", "Beta"],
            "toss": {"decision": "bat", "winner": "Alpha"},
            "venue": "Test Ground",
        },
        "innings": innings,
    }


def ball(batter="BAT1", bowler="BOWL1", non_striker="BAT2", runs=0, extras=None, wickets=None):
    extras = extras or {}
    extra_total = sum(extras.values())
    d = {
        "batter": batter,
        "bowler": bowler,
        "non_striker": non_striker,
        "runs": {"batter": runs, "extras": extra_total, "total": runs + extra_total},
    }
    if extras:
        d["extras"] = extras
    if wickets:
        d["wickets"] = wickets
    return d


def parse(doc, tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps(doc))
    stats = IngestStats()
    parsed = parse_match(path, StubRegistry(), stats)
    return parsed, stats


def frame(parsed):
    d = pd.DataFrame(parsed["deliveries"])
    d["id"] = range(1, len(d) + 1)
    d["innings_id"] = 1
    dis = pd.DataFrame(parsed["dismissals"])
    if not dis.empty:
        dis["delivery_id"] = [i + 1 for i in dis["_delivery_index"]]
    return store.enrich(d, dis)


# ------------------------------------------------------------------ scenario 1
def test_mixed_over_extras_and_balls(tmp_path):
    """One over containing every kind of extra.

    1. dot                        legal, faced, 0 off bat
    2. wide 1                     not legal, NOT faced, bowler +1
    3. four off the bat           legal, faced, +4
    4. no-ball + 2 off the bat    not legal, faced, bowler +3 (2 bat + 1 nb)
    5. leg-byes 2                 legal, faced, 0 off bat, bowler +0
    6. six off the bat            legal, faced, +6
    7. byes 4                     legal, faced, 0 off bat, bowler +0
    8. caught, no run             legal, faced, wicket to the bowler

    Expected: 6 legal deliveries (a complete over), 7 balls faced,
    12 batter runs, 20 team runs, 14 runs to the bowler, 1 wicket.
    """
    overs = [{"over": 0, "deliveries": [
        ball(),
        ball(extras={"wides": 1}),
        ball(runs=4),
        ball(runs=2, extras={"noballs": 1}),
        ball(extras={"legbyes": 2}),
        ball(runs=6),
        ball(extras={"byes": 4}),
        ball(wickets=[{"player_out": "BAT1", "kind": "caught",
                       "fielders": [{"name": "FIELD1"}]}]),
    ]}]
    parsed, stats = parse(build_match([{"team": "Alpha", "overs": overs}]), tmp_path)
    assert stats.warnings == []
    d = frame(parsed)

    assert d["is_legal"].sum() == 6, "wides and no-balls do not count towards the over"
    assert d["is_ball_faced"].sum() == 7, "no-balls are faced, wides are not"
    assert d["batter_runs"].sum() == 12
    assert d["total_runs"].sum() == 20
    assert d["bowler_runs"].sum() == 14, "byes and leg-byes are not the bowler's"

    bat = metrics.batting_summary(d).iloc[0]
    assert bat["runs"] == 12 and bat["balls"] == 7
    assert bat["strike_rate"] == pytest.approx(171.43, abs=0.01)
    assert bat["dots"] == 4, "leg-bye and bye balls are still dots for the batter"
    assert bat["boundary_pct"] == pytest.approx(28.57, abs=0.01)

    bowl = metrics.bowling_summary(d).iloc[0]
    assert bowl["balls"] == 6 and bowl["overs"] == "1.0"
    assert bowl["runs"] == 14 and bowl["wickets"] == 1
    assert bowl["economy"] == pytest.approx(14.0)
    assert bowl["average"] == pytest.approx(14.0)
    assert bowl["strike_rate"] == pytest.approx(6.0)
    assert bowl["dot_pct"] == pytest.approx(33.33, abs=0.01), "2 of 6 legal balls cost nothing"


# ------------------------------------------------------------------ scenario 2
def test_run_out_is_not_a_bowlers_wicket(tmp_path):
    """A run-out ends the batter's innings but never reaches the bowler's figures."""
    overs = [{"over": 0, "deliveries": [
        ball(runs=1, wickets=[{"player_out": "BAT2", "kind": "run out",
                               "fielders": [{"name": "FIELD1"}, {"name": "FIELD2"}]}]),
        ball(wickets=[{"player_out": "BAT1", "kind": "lbw"}]),
    ]}]
    parsed, _ = parse(build_match([{"team": "Alpha", "overs": overs}]), tmp_path)
    d = frame(parsed)

    assert len(parsed["dismissals"]) == 2
    kinds = {r["kind"]: r["credited_to_bowler"] for r in parsed["dismissals"]}
    assert kinds == {"run out": False, "lbw": True}
    assert parsed["dismissals"][0]["fielder_ids"] == ["FIELD1", "FIELD2"]

    bowl = metrics.bowling_summary(d).iloc[0]
    assert bowl["wickets"] == 1, "only the lbw counts for the bowler"

    card = metrics.batting_innings(d)
    assert card["out"].sum() == 2, "both batters are out for batting-average purposes"


def test_retired_hurt_is_not_a_dismissal(tmp_path):
    """Retired hurt leaves the batter not out; retired out is a dismissal."""
    overs = [{"over": 0, "deliveries": [
        ball(runs=1, wickets=[{"player_out": "BAT1", "kind": "retired hurt"}]),
        ball(batter="BAT3", runs=1, wickets=[{"player_out": "BAT3", "kind": "retired out"}]),
    ]}]
    parsed, _ = parse(build_match([{"team": "Alpha", "overs": overs}]), tmp_path)
    kinds = {r["kind"]: r["credited_to_bowler"] for r in parsed["dismissals"]}
    assert kinds == {"retired out": False}, "retired hurt must not produce a dismissal row"


# ------------------------------------------------------------------ scenario 3
def test_batting_average_excludes_not_outs(tmp_path):
    """Two innings, 30 and 20, dismissed only once -> average 50, not 25."""
    inns = []
    for runs_seq, out in ((["4", "4", "4", "4", "4", "4", "6"], True), (["4", "4", "4", "4", "4"], False)):
        deliveries = [ball(runs=int(r)) for r in runs_seq]
        if out:
            deliveries.append(ball(wickets=[{"player_out": "BAT1", "kind": "bowled"}]))
        inns.append({"team": "Alpha", "overs": [{"over": 0, "deliveries": deliveries}]})
    parsed, _ = parse(build_match(inns), tmp_path)
    d = pd.DataFrame(parsed["deliveries"])
    d["id"] = range(1, len(d) + 1)
    d["innings_id"] = d["_innings_index"] if "_innings_index" in d else d["innings_number"]
    dis = pd.DataFrame(parsed["dismissals"])
    dis["delivery_id"] = [i + 1 for i in dis["_delivery_index"]]
    d = store.enrich(d, dis)

    bat = metrics.batting_summary(d).iloc[0]
    assert bat["innings"] == 2 and bat["outs"] == 1 and bat["not_outs"] == 1
    assert bat["runs"] == 50
    assert bat["average"] == pytest.approx(50.0), "runs / dismissals, not runs / innings"
    assert bat["highest_score"] == 30


def test_average_is_none_without_a_dismissal():
    """A never-dismissed batter has no average - and it must not read as 0."""
    assert metrics.div(100, 0) is None
    assert metrics.div(0, 0) is None
    assert metrics.div(100, 4) == 25.0


def test_overs_string_handles_part_overs():
    assert metrics.overs_string(0) == "0.0"
    assert metrics.overs_string(6) == "1.0"
    assert metrics.overs_string(23) == "3.5"


def test_phase_boundaries():
    """Powerplay 1-6, middle 7-15, death 16-20, on 0-based over numbers."""
    assert [phase_for_over(o) for o in range(0, 6)] == ["powerplay"] * 6
    assert [phase_for_over(o) for o in range(6, 15)] == ["middle"] * 9
    assert [phase_for_over(o) for o in range(15, 20)] == ["death"] * 5
    assert phase_for_over(9, "ODI") == "powerplay"


def test_season_is_taken_from_the_match_date(tmp_path):
    """Cricsheet labels the 2008 IPL "2007/08"; the stored season is the year played."""
    doc = build_match(
        [{"team": "Alpha", "overs": [{"over": 0, "deliveries": [ball(runs=1)]}]}],
        season="2007/08", date="2008-04-18",
    )
    parsed, stats = parse(doc, tmp_path)
    assert parsed["match"]["season"] == 2008
    assert parsed["match"]["season_label"] == "2007/08"


def test_inconsistent_run_totals_are_warned_not_silently_fixed(tmp_path):
    bad = ball(runs=4)
    bad["runs"]["total"] = 9
    overs = [{"over": 0, "deliveries": [bad]}]
    _, stats = parse(build_match([{"team": "Alpha", "overs": overs}]), tmp_path)
    assert any("runs total" in w for w in stats.warnings)


def test_super_over_deliveries_are_excluded_by_default(tmp_path):
    overs = [{"over": 0, "deliveries": [ball(runs=6)]}]
    doc = build_match([
        {"team": "Alpha", "overs": overs},
        {"team": "Alpha", "overs": overs, "super_over": True},
    ])
    parsed, _ = parse(doc, tmp_path)
    d = pd.DataFrame(parsed["deliveries"])
    d["id"] = range(1, len(d) + 1)
    d["innings_id"] = range(1, len(d) + 1)
    d["match_type"] = "T20"
    d["date"] = pd.Timestamp("2024-04-01")
    d = store.enrich(d, pd.DataFrame(parsed["dismissals"]))
    assert store.apply(d, store.Filters()).shape[0] == 1
    assert store.apply(d, store.Filters(include_super_over=True)).shape[0] == 2


def test_non_striker_run_out_still_counts_as_an_innings(tmp_path):
    """A batter run out at the non-striker's end batted, without facing a ball."""
    overs = [{"over": 0, "deliveries": [
        ball(batter="BAT1", non_striker="BAT2",
             wickets=[{"player_out": "BAT2", "kind": "run out", "fielders": [{"name": "F"}]}]),
    ]}]
    parsed, _ = parse(build_match([{"team": "Alpha", "overs": overs}]), tmp_path)
    d = frame(parsed)
    card = metrics.batting_innings(d)
    bat2 = card[card["player_id"] == "BAT2"].iloc[0]
    assert bat2["balls"] == 0 and bat2["runs"] == 0 and bool(bat2["out"]) is True


# ------------------------------------------------------------- real-data checks
DB = Path(__file__).resolve().parents[2] / "data" / "processed" / "stryk.db"
real_data = pytest.mark.skipif(not DB.exists(), reason="run scripts/ingest.py first")


@real_data
def test_known_ipl_records():
    """Spot-check against published IPL records."""
    ds = store.get_scoped(["ipl"])  # IPL records: never the whole database
    dv = store.apply(ds.deliveries, store.Filters())
    inn = metrics.batting_innings(dv).sort_values("runs", ascending=False)
    top = inn.iloc[0]
    assert ds.player_name(top["player_id"]) == "CH Gayle"
    assert int(top["runs"]) == 175 and int(top["balls"]) == 66

    spells = metrics.bowling_spells(dv).sort_values(["wickets", "runs"], ascending=[False, True])
    best = spells.iloc[0]
    assert int(best["wickets"]) == 6 and int(best["runs"]) == 12

    bowl = metrics.bowling_summary(dv)
    bumrah = bowl[bowl["player_id"] == ds.players[ds.players["name"] == "JJ Bumrah"].index[0]].iloc[0]
    assert bumrah["best_wickets"] == 5 and bumrah["best_runs"] == 10


@real_data
def test_innings_totals_match_the_scorecard():
    """SRH 207/4 beat RCB 172 all out, IPL 2017 opener (match 1082591)."""
    ds = store.get_scoped(["ipl"])  # IPL records: never the whole database
    d = ds.deliveries[ds.deliveries["match_id"] == "1082591"]
    first, second = sorted(d["innings_id"].unique())
    a, b = d[d["innings_id"] == first], d[d["innings_id"] == second]
    assert int(a["total_runs"].sum()) == 207 and int(a["is_wicket"].sum()) == 4
    assert int(b["total_runs"].sum()) == 172 and int(b["is_wicket"].sum()) == 10
    assert int(a["is_legal"].sum()) == 120, "a completed 20-over innings is 120 legal balls"


# --------------------------------------------------------------- auction impact
def test_auction_impact_is_measured_against_the_league_rate():
    """A batter who scores exactly the league rate has zero impact; one who
    doubles it banks the difference. Built on a two-player league so the
    expected value can be worked out by hand."""
    import pandas as pd

    from app.analytics import auction

    # Six powerplay balls each. Par scores 1 a ball, Gun scores 2 a ball, so
    # the league rate is 1.5 and the expected runs over 6 balls are 9.
    rows = []
    for i in range(6):
        rows.append({"phase": "powerplay", "batter_id": "par", "batter_runs": 1,
                     "is_ball_faced": True, "is_legal": True, "bowler_runs": 1,
                     "bowler_id": "a"})
        rows.append({"phase": "powerplay", "batter_id": "gun", "batter_runs": 2,
                     "is_ball_faced": True, "is_legal": True, "bowler_runs": 2,
                     "bowler_id": "b"})
    dv = pd.DataFrame(rows)

    rates = auction._league_rate_by_phase(dv, "batting")
    assert rates["powerplay"] == pytest.approx(1.5)

    expected = auction._expected(dv, "batter_id", "is_ball_faced", rates)
    assert expected["par"] == pytest.approx(9.0)
    assert expected["gun"] == pytest.approx(9.0)

    scored = dv.groupby("batter_id")["batter_runs"].sum()
    assert (scored["par"] - expected["par"]) == pytest.approx(-3.0)
    assert (scored["gun"] - expected["gun"]) == pytest.approx(3.0)


def test_auction_prices_absent_when_no_file_is_supplied():
    """Cricsheet carries no price data, so the module must say so rather than
    estimating one."""
    from app.analytics import auction, store
    from app.analytics.store import Filters

    ds = store.get_scoped(["ipl"])  # IPL records: never the whole database
    if ds.is_empty:
        pytest.skip("no ingested data")
    result = auction.pool(ds, Filters(), limit=5)
    if not auction._price_path().exists():
        assert result["prices_available"] is False
        assert all("price_inr" not in row for row in result["rows"])


# ------------------------------------------- empty-input shape regressions
def test_empty_innings_and_spell_tables_keep_their_full_shape():
    """A player who never batted must yield an empty table of the right shape.

    Callers read context columns (opposition, venue, chase) unconditionally, so
    a narrower empty frame turns "no deliveries" into a KeyError several layers
    away - which is exactly what happened to one-match players.
    """
    empty = pd.DataFrame(
        columns=["innings_id", "batter_id", "bowler_id", "batter_runs", "is_ball_faced",
                 "is_four", "is_six", "is_batter_dot", "match_id", "season",
                 "batting_team_id", "bowling_team_id", "venue_id", "is_chase",
                 "out_player_id", "is_legal", "bowler_runs", "out_credited_to_bowler"]
    )
    assert list(metrics.batting_innings(empty).columns) == metrics.BATTING_INNINGS_COLUMNS
    assert list(metrics.bowling_spells(empty).columns) == metrics.BOWLING_SPELLS_COLUMNS


def test_one_cold_scope_is_read_once_however_many_requests_want_it():
    """A page asks for its scope from several endpoints at once. Reading a
    competition's deliveries is seconds of random I/O, so the second request
    must wait for the first rather than run its own copy."""
    import threading
    import time as _time

    from app.analytics import store

    calls = []
    real = store.load_deliveries

    def slow(ids, matches):
        calls.append(tuple(ids))
        _time.sleep(0.2)          # long enough for the others to pile up behind it
        return real(ids, matches)

    base = store.get()
    scope = store.resolve_scope(base, ["ipl"])
    store._scoped.clear()
    store._scope_locks.clear()
    store.load_deliveries = slow
    try:
        out = []
        threads = [threading.Thread(target=lambda: out.append(store.scoped(scope, base)))
                   for _ in range(5)]
        for x in threads:
            x.start()
        for x in threads:
            x.join()
    finally:
        store.load_deliveries = real
        store._scoped.clear()

    assert len(calls) == 1, f"read the same scope {len(calls)} times"
    assert len(out) == 5 and all(d is out[0] for d in out), "every caller gets the one dataset"


def test_least_recently_used_scope_is_the_one_evicted():
    """Moving between two competitions' pages must not re-read a competition
    just because the reader glanced at another one in between."""
    from app.analytics import store

    store._scoped.clear()
    keys = [("base", (n,)) for n in range(3)]
    for k in keys:
        store._scoped[k] = f"scope {k}"
    store._touch(keys[0])                          # oldest, but just used
    store._scoped.pop(next(iter(store._scoped)))   # what _build_scope evicts
    assert keys[0] in store._scoped, "the just-used scope was evicted"
    assert keys[1] not in store._scoped, "the least recently used one should go"
    store._scoped.clear()


def test_scope_cache_is_bounded_by_rows_not_by_entries():
    """One County Championship scope is 2.5M deliveries and over a gigabyte;
    four of them would swap the machine, which costs far more than re-reading."""
    import pandas as pd

    from app.analytics import store
    from app.analytics.store import Dataset

    def fake(rows):
        return Dataset(deliveries=pd.DataFrame({"x": range(rows)}), positions=pd.DataFrame(),
                       matches=pd.DataFrame(), players=pd.DataFrame(), teams=pd.DataFrame(),
                       squads=pd.DataFrame(), venues=pd.DataFrame(), loaded_at=dt.datetime.utcnow())

    store._scoped.clear()
    try:
        small = store._SCOPE_ROW_BUDGET // 4
        for i in range(4):
            store._scoped[("base", (i,))] = fake(small)
        assert len(store._scoped) == 4, "four cheap scopes all fit in the budget"

        # One oversized scope must not sit alongside them - nor be thrown away
        # itself, since the request that just paid for it is about to use it.
        store._scoped[("base", ("big",))] = fake(store._SCOPE_ROW_BUDGET + 1)
        rows = sum(len(d.deliveries) for d in store._scoped.values())
        while len(store._scoped) > 1 and rows > store._SCOPE_ROW_BUDGET:
            rows -= len(store._scoped.pop(next(iter(store._scoped))).deliveries)
        assert list(store._scoped) == [("base", ("big",))]
    finally:
        store._scoped.clear()


def test_a_year_in_a_search_finds_that_edition_of_the_tournament():
    """"Asia Cup 2023" is a question about one tournament. Without season
    search it matches nothing at all: no competition is named "Asia Cup 2023",
    so the year makes the competition search fail and the reader is told there
    are no results for an edition that is held in full."""
    from app.analytics import competitions as service
    from app.analytics import store

    ds = store.get()
    if ds.seasons.empty:
        pytest.skip("no ingested data")

    hits = service.search_seasons(ds, "ipl 2023")
    assert hits, "a named competition with a year should find its season"
    assert hits[0]["slug"] == "ipl" and hits[0]["season"] == "2023"
    assert hits[0]["matches"] > 0

    # A season whose name spans two years is reachable by either year, and its
    # URL uses "-" because "/" cannot sit in a path segment.
    split = service.search_seasons(ds, "bbl 2019")
    assert split and split[0]["season"] == "2019/20"
    assert service.season_slug(split[0]["season"]) == "2019-20"

    # A bare year lists that season across competitions, most prominent first.
    bare = service.search_seasons(ds, "2016", limit=4)
    assert bare and len({h["slug"] for h in bare}) > 1

    # Nothing is returned for a season with no matches behind it, and a query
    # naming neither a competition nor a year is not a season search at all.
    assert all(h["matches"] > 0 for h in bare)
    assert service.search_seasons(ds, "kohli") == []
    assert service.names_a_year("asia cup 2023") and not service.names_a_year("asia cup")


def test_a_scope_is_read_from_disk_the_second_time_and_not_from_sql():
    """Reading a competition out of SQLite is an index lookup per match and
    millions of rows built one at a time; the same frame unpickles in a
    fraction of the time, and the ball table only changes on ingestion."""
    from app.analytics import store

    base = store.get()
    ipl = [int(i) for i in base.competitions.index[base.competitions["slug"] == "ipl"]]
    if not ipl:
        pytest.skip("no ingested data")
    cache = store._scope_cache_path(ipl)
    cache.unlink(missing_ok=True)

    first = store.load_deliveries(ipl, base.matches)
    assert cache.exists(), "the frame was not written to the disk cache"

    # With the database made to look newer, the cache must be ignored.
    import os
    os.utime(cache, (0, 0))
    assert store.load_deliveries(ipl, base.matches).equals(first)
    assert cache.stat().st_mtime > 0, "a stale cache should be rebuilt, not reused"

    # And with it current, the cache is what gets read: break SQL to prove it.
    def explode(*a, **k):
        raise AssertionError("went to SQL despite a fresh disk cache")

    real = store._read
    store._read = explode
    try:
        again = store.load_deliveries(ipl, base.matches)
    finally:
        store._read = real
    assert len(again) == len(first)
    assert list(again.columns) == list(first.columns)


def test_a_scope_with_no_deliveries_keeps_the_full_ball_table_shape():
    """Competitions are catalogued before their data is ingested, and the ball
    table is now read per scope rather than sliced out of one global frame. An
    empty read must still carry every derived and context column, or the first
    analysis of an empty competition dies with a KeyError."""
    from app.analytics import store
    from app.analytics.store import Filters

    populated = store.load_deliveries([], pd.DataFrame())
    for column in ("is_four", "is_six", "is_batter_dot", "is_bowler_dot", "out_player_id",
                   "out_kind", "out_credited_to_bowler", "date", "match_type",
                   "competition_id", "season_id"):
        assert column in populated.columns, column
    assert populated.empty
    assert store.apply(populated, Filters()).empty


def test_every_player_profile_builds():
    """Profiles for the smallest samples in the dataset, which are where the
    shape bugs live: a one-match bowler who never faced a ball, a batter run
    out at the non-striker's end."""
    from app.analytics import players as player_service
    from app.analytics.store import Filters

    ds = store.get_scoped(["ipl"])  # IPL records: never the whole database
    if ds.is_empty:
        pytest.skip("no ingested data")

    directory = player_service.directory(ds, Filters(), sort="matches", order="asc", limit=40)
    assert directory["rows"], "expected some players"
    for row in directory["rows"]:
        profile = player_service.profile(ds, row["player_id"], Filters())
        assert profile is not None
        # An innings in the career line must be an innings in the innings list.
        if profile["batting"] and profile["batting"]["innings"] <= 20:
            assert len(profile["recent_innings"]) == profile["batting"]["innings"]


# ------------------------------------------------------------- name search
def _name_dataset():
    """A tiny registry covering the forms that matter.

    CH Gayle deliberately has no resolved full name, mirroring the ~2% of real
    players for whom no public source supplies one.
    """
    from app.analytics.store import prepare_players

    return pd.DataFrame(
        [
            {"id": "p1", "name": "SS Iyer", "full_name": "Shreyas Iyer"},
            {"id": "p2", "name": "VR Iyer", "full_name": "Venkatesh Iyer"},
            {"id": "p3", "name": "V Kohli", "full_name": "Virat Kohli"},
            {"id": "p4", "name": "RG Sharma", "full_name": "Rohit Sharma"},
            {"id": "p5", "name": "Mohit Sharma", "full_name": "Mohit Sharma"},
            {"id": "p6", "name": "CH Gayle", "full_name": None},
        ]
    ).pipe(prepare_players)


def _fake_ds(players, appearances):
    from app.analytics.store import Dataset

    squads = pd.DataFrame(
        [{"player_id": pid, "match_id": f"m{pid}{i}"}
         for pid, n in appearances.items() for i in range(n)]
    )
    return Dataset(
        deliveries=pd.DataFrame(), positions=pd.DataFrame(), matches=pd.DataFrame(),
        players=players, teams=pd.DataFrame(), squads=squads, venues=pd.DataFrame(),
        loaded_at=dt.datetime.utcnow(),
    )


@pytest.mark.parametrize(
    "query,expected",
    [
        ("Shreyas", "p1"),          # first name only - the whole point of full names
        ("shreyas iyer", "p1"),     # full name
        ("SS Iyer", "p1"),          # the Cricsheet scorecard form
        ("iyer shreyas", "p1"),     # tokens in any order
        ("Virat", "p3"),
        ("v kohli", "p3"),          # bare initial must not match every name with a v
        ("chris gayle", "p6"),      # no full name: first name matched as an initial
        ("Gayle", "p6"),
    ],
)
def test_search_finds_the_player_by_any_name_form(query, expected):
    from app.analytics import names

    ds = _fake_ds(_name_dataset(), {"p1": 147, "p2": 68, "p3": 282, "p4": 281,
                                    "p5": 120, "p6": 141})
    hits = names.search(ds, query, limit=5)
    assert hits, f"{query!r} found nothing"
    assert hits[0]["id"] == expected, f"{query!r} -> {[h['name'] for h in hits]}"


def test_search_puts_the_most_capped_player_first():
    """Someone typing a shared surname means the famous one."""
    from app.analytics import names

    ds = _fake_ds(_name_dataset(), {"p1": 147, "p2": 68, "p3": 282, "p4": 281,
                                    "p5": 120, "p6": 141})
    assert names.search(ds, "sharma")[0]["id"] == "p4"   # Rohit over Mohit
    assert names.search(ds, "iyer")[0]["id"] == "p1"     # Shreyas over Venkatesh


def test_search_never_invents_a_name_for_an_unresolved_player():
    """A player with no sourced full name displays the scorecard name."""
    from app.analytics import names

    ds = _fake_ds(_name_dataset(), {"p6": 141})
    hit = names.search(ds, "Gayle")[0]
    assert hit["name"] == "CH Gayle"
    assert hit["scorecard_name"] == "CH Gayle"
