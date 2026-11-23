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

    def team(self, name):
        return self.ids.setdefault(("team", name), len(self.ids) + 1)

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
    ds = store.get()
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
    ds = store.get()
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

    ds = store.get()
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


def test_every_player_profile_builds():
    """Profiles for the smallest samples in the dataset, which are where the
    shape bugs live: a one-match bowler who never faced a ball, a batter run
    out at the non-striker's end."""
    from app.analytics import players as player_service
    from app.analytics.store import Filters

    ds = store.get()
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
