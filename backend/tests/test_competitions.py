"""Competition-agnostic foundation: catalogue, linking, scoping, standings, migrations.

The integration tests build a real database through the real migrations and
the real importer from miniature Cricsheet files, so they exercise the same
path a production ingest takes.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app import catalog
from app.catalog import CatalogueError, MatchContext, classify_stage, resolve
from app.ingestion.linking import season_identity

# ----------------------------------------------------------------- catalogue


def test_catalogue_is_valid_and_complete():
    cat = catalog.catalogue()
    slugs = {c["slug"] for c in cat["competitions"]}
    # The brief's headline competitions are all listed, available or not.
    for slug in ("ipl", "wpl", "bbl", "wbbl", "psl", "sa20", "cpl", "ilt20", "mlc", "bpl", "lpl",
                 "the-hundred-mens", "the-hundred-womens", "mens-tests", "womens-odis",
                 "icc-mens-t20-world-cup", "icc-womens-cricket-world-cup", "ranji-trophy",
                 "county-championship", "sheffield-shield", "the-ford-trophy"):
        assert slug in slugs, slug
    # Every competition is either mappable to data or says why it is not.
    for c in cat["competitions"]:
        assert c["match"] or c.get("unavailable_reason"), c["slug"]


def test_women_have_their_own_competitions_not_a_filter():
    women = [c for c in catalog.catalogue()["competitions"] if c["gender"] == "WOMEN"]
    types = {c["type"] for c in women}
    assert {"INTERNATIONAL", "ICC_TOURNAMENT", "FRANCHISE_LEAGUE", "DOMESTIC"} <= types


@pytest.mark.parametrize("mutate, message", [
    (lambda c: c["competitions"].append(copy.deepcopy(c["competitions"][0])), "duplicate slug"),
    (lambda c: c["competitions"][0].update(type="LEAGUE"), "unknown type"),
    (lambda c: c["competitions"][0].update(match=[], unavailable_reason=None), "needs a match rule"),
    (lambda c: c["points_systems"][0].update(tie_breakers=["points", "coin_toss"]), "unknown tie-breakers"),
    (lambda c: c["competitions"][0].update(match=[{"provider": "cricsheet", "dataset": "nope"}]), "not in sources"),
])
def test_catalogue_validation_rejects_bad_data(mutate, message):
    cat = copy.deepcopy(catalog.catalogue())
    mutate(cat)
    with pytest.raises(CatalogueError, match=message):
        catalog.validate(cat)


# ---------------------------------------------------------------- resolution
COMPS = catalog.catalogue()["competitions"]


def _slug(**kw):
    hit = resolve(MatchContext(**kw), COMPS)
    return hit["slug"] if hit else None


def test_resolution_by_verified_event_name():
    assert _slug(event_name="Indian Premier League", gender="MEN", match_type="T20",
                 team_type="club") == "ipl"


def test_resolution_by_dataset_and_gender_split():
    assert _slug(event_name="whatever", gender="WOMEN", match_type="T20", team_type="club",
                 dataset="wpl") == "wpl"
    # The Hundred dataset holds both competitions; gender decides.
    assert _slug(event_name="x", gender="MEN", match_type="T20", team_type="club",
                 dataset="hnd") == "the-hundred-mens"
    assert _slug(event_name="x", gender="WOMEN", match_type="T20", team_type="club",
                 dataset="hnd") == "the-hundred-womens"


def test_bilateral_internationals_resolve_by_gender_and_format():
    assert _slug(event_name="England tour of India", gender="WOMEN", match_type="ODI",
                 team_type="international") == "womens-odis"
    assert _slug(event_name="Australia in South Africa", gender="MEN", match_type="Test",
                 team_type="international") == "mens-tests"


def test_unknown_club_event_is_not_forced_into_a_competition():
    ctx = MatchContext(event_name="Village Bash 2031", gender="MEN", match_type="T20",
                       team_type="club")
    assert resolve(ctx, COMPS) is None
    assert catalog.uncatalogued_slug(ctx) == "village-bash-2031-men"


def test_ipl_event_name_does_not_capture_womens_matches():
    assert _slug(event_name="Indian Premier League", gender="WOMEN", match_type="T20",
                 team_type="club") is None


# ------------------------------------------------------------------ seasons
def test_calendar_year_naming_ignores_misleading_labels():
    # Cricsheet labels IPL 2008 "2007/08"; the IPL season is 2008.
    assert season_identity("calendar_year", "2007/08", dt.date(2008, 4, 18)) == ("2008", 2008)


def test_source_label_naming_keeps_split_seasons_whole():
    # BBL 2023/24: matches in December and January are one season.
    assert season_identity("source_label", "2023/24", dt.date(2024, 1, 10)) == ("2023/24", 2023)
    assert season_identity("source_label", "2023/24", dt.date(2023, 12, 7)) == ("2023/24", 2023)


@pytest.mark.parametrize("stage, group, expected", [
    (None, None, ("League", "league")),
    ("Final", None, ("Final", "knockout")),
    ("Qualifier 1", None, ("Qualifier 1", "knockout")),
    ("3rd Place Play-Off", None, ("3rd Place Play-Off", "knockout")),
    ("Super 8", "1", ("Super 8", "group")),
    (None, "A", ("Group stage", "group")),
])
def test_stage_classification(stage, group, expected):
    assert classify_stage(stage, group) == expected


# ------------------------------------------------------- fixture generation
def _innings(team, runs, balls, wickets, batters, bowler, target=None, super_over=False):
    """An innings of ``balls`` legal deliveries scoring ``runs`` with ``wickets`` falling."""
    deliveries, out_so_far = [], 0
    for i in range(balls):
        r = runs // balls + (1 if i < runs % balls else 0)
        d = {"batter": batters[min(out_so_far, len(batters) - 1)],
             "bowler": bowler,
             "non_striker": batters[min(out_so_far + 1, len(batters) - 1)],
             "runs": {"batter": r, "extras": 0, "total": r}}
        # Wickets fall on the final balls, so the totals stay exact.
        if i >= balls - wickets:
            d["wickets"] = [{"player_out": d["batter"], "kind": "bowled"}]
            out_so_far += 1
        deliveries.append(d)
    overs = [{"over": n, "deliveries": deliveries[n * 6:(n + 1) * 6]}
             for n in range((balls + 5) // 6)]
    inn = {"team": team, "overs": overs}
    if target:
        inn["target"] = target
    if super_over:
        inn["super_over"] = True
    return inn


def _squad(team):
    return [f"{team}{i}" for i in range(1, 12)]


def _match_file(directory: Path, match_id: str, *, teams, innings, outcome, date="2030-04-01",
                event="Indian Premier League", gender="male", team_type="club",
                match_type="T20", overs=20, season=None, stage=None, extra_people=()):
    people = {}
    players = {}
    for t in teams:
        players[t] = _squad(t)
        for p in players[t]:
            people[p] = f"id-{p}"
    for p in extra_people:
        people[p] = f"id-{p}"
    event_doc = {"name": event}
    if stage:
        event_doc["stage"] = stage
    info = {
        "balls_per_over": 6, "dates": [date], "event": event_doc, "gender": gender,
        "match_type": match_type, "outcome": outcome, "overs": overs, "players": players,
        "registry": {"people": people}, "season": season or date[:4], "team_type": team_type,
        "teams": list(teams), "toss": {"decision": "bat", "winner": teams[0]},
        "venue": "Test Ground", "city": "Testville",
        "officials": {"umpires": list(extra_people)},
    }
    (directory / f"{match_id}.json").write_text(json.dumps({"meta": {}, "info": info, "innings": innings}))


def league_fixture(directory: Path):
    """Three teams; worked standings are in test_standings_hand_worked."""
    directory.mkdir(parents=True, exist_ok=True)
    A, B, C = "Alpha", "Beta", "Gamma"
    # M1: Alpha 160/5 (20) beat Beta 150 all out (18 ov) by 10 runs.
    _match_file(directory, "m1", teams=[A, B], outcome={"winner": A, "by": {"runs": 10}},
                date="2030-04-01", extra_people=["Ump One"], innings=[
                    _innings(A, 160, 120, 5, _squad(A), "Beta11"),
                    _innings(B, 150, 108, 10, _squad(B), "Alpha11", target={"runs": 161, "overs": 20}),
                ])
    # M2: Beta 140/7 (20) lost to Gamma 141/4 (15 ov) by 6 wickets.
    _match_file(directory, "m2", teams=[B, C], outcome={"winner": C, "by": {"wickets": 6}},
                date="2030-04-02", innings=[
                    _innings(B, 140, 120, 7, _squad(B), "Gamma11"),
                    _innings(C, 141, 90, 4, _squad(C), "Beta11", target={"runs": 141, "overs": 20}),
                ])
    # M3: Alpha v Gamma, no result after 6 overs.
    _match_file(directory, "m3", teams=[A, C], outcome={"result": "no result"},
                date="2030-04-03", innings=[_innings(A, 50, 36, 1, _squad(A), "Gamma11")])
    # M4: Gamma 120/8 (20), Alpha 120/9 (20): tie, Alpha win the super over.
    _match_file(directory, "m4", teams=[C, A], outcome={"result": "tie", "eliminator": A},
                date="2030-04-04", innings=[
                    _innings(C, 120, 120, 8, _squad(C), "Alpha11"),
                    _innings(A, 120, 120, 9, _squad(A), "Gamma11", target={"runs": 121, "overs": 20}),
                    _innings(C, 8, 6, 0, _squad(C), "Alpha10", super_over=True),
                    _innings(A, 9, 4, 0, _squad(A), "Gamma10", super_over=True),
                ])
    # A knockout final that must not count in the league table.
    _match_file(directory, "m5", teams=[A, C], outcome={"winner": C, "by": {"runs": 1}},
                date="2030-04-10", stage="Final", innings=[
                    _innings(A, 100, 120, 3, _squad(A), "Gamma11"),
                    _innings(C, 101, 60, 0, _squad(C), "Alpha11", target={"runs": 101, "overs": 20}),
                ])


# ------------------------------------------------------- database fixtures
@pytest.fixture()
def db_engine(tmp_path, monkeypatch):
    """A fresh database built by the real migrations, wired into the app."""
    from app.analytics import store
    from app.core import db as core_db
    from app.core.migrate import upgrade

    eng = create_engine(f"sqlite:///{tmp_path / 'stryk.db'}", future=True)
    assert upgrade(eng) == "0002"
    monkeypatch.setattr(core_db, "engine", eng)
    monkeypatch.setattr(store, "engine", eng)
    store._cache = None
    store._scoped.clear()
    yield eng
    store._cache = None
    store._scoped.clear()


def _ingest(eng, directory, dataset):
    from app.ingestion.cricsheet import ingest_directory

    with Session(eng) as db:
        stats = ingest_directory(db, directory, dataset=dataset)
    assert stats.skipped == 0, stats.warnings
    return stats


@pytest.fixture()
def mixed_db(db_engine, tmp_path):
    """IPL league + a WPL match + a men's T20I sharing a player with the IPL."""
    league_fixture(tmp_path / "ipl_json")
    _ingest(db_engine, tmp_path / "ipl_json", "ipl")

    wpl = tmp_path / "wpl_json"
    wpl.mkdir()
    # "Alpha" also exists as a women's side: a different team with the same name.
    _match_file(wpl, "w1", teams=["Alpha", "Delta"], gender="female", event="Women's Premier League",
                outcome={"winner": "Delta", "by": {"runs": 5}}, date="2030-03-01", innings=[
                    _innings("Alpha", 100, 120, 6, _squad("AlphaW"), "Delta11"),
                    _innings("Delta", 105, 120, 4, _squad("Delta"), "AlphaW11", target={"runs": 101, "overs": 20}),
                ])
    # Women's player ids must differ from the men's "Alpha1".."Alpha11".
    doc = json.loads((wpl / "w1.json").read_text())
    doc["info"]["players"]["Alpha"] = _squad("AlphaW")
    for p in _squad("AlphaW"):
        doc["info"]["registry"]["people"][p] = f"id-{p}"
    (wpl / "w1.json").write_text(json.dumps(doc))
    _ingest(db_engine, wpl, "wpl")

    t20is = tmp_path / "t20s_json"
    t20is.mkdir()
    # Alpha1 plays for "Nation" in a men's T20I: same person, one player row.
    nation = ["Alpha1"] + [f"Nation{i}" for i in range(2, 12)]
    _match_file(t20is, "i1", teams=["Nation", "Other"], team_type="international",
                event="Nation tour of Other", outcome={"winner": "Nation", "by": {"runs": 20}},
                date="2030-06-01", innings=[
                    _innings("Nation", 150, 120, 5, nation, "Other11"),
                    _innings("Other", 130, 120, 9, _squad("Other"), "Nation11", target={"runs": 151, "overs": 20}),
                ])
    doc = json.loads((t20is / "i1.json").read_text())
    doc["info"]["players"]["Nation"] = nation
    for p in nation:
        doc["info"]["registry"]["people"][p] = f"id-{p}"
    (t20is / "i1.json").write_text(json.dumps(doc))
    _ingest(db_engine, t20is, "t20s")
    return db_engine


# --------------------------------------------------------- integration tests
def test_matches_link_to_competitions_seasons_and_stages(mixed_db):
    with mixed_db.connect() as c:
        rows = dict(c.execute(text(
            "SELECT m.id, c.slug FROM match m JOIN competition c ON c.id = m.competition_id")).all())
        assert rows == {"m1": "ipl", "m2": "ipl", "m3": "ipl", "m4": "ipl", "m5": "ipl",
                        "w1": "wpl", "i1": "mens-t20is"}
        stages = dict(c.execute(text(
            "SELECT m.id, s.stage_type FROM match m JOIN tournament_stage s ON s.id = m.stage_id")).all())
        assert stages["m5"] == "knockout" and stages["m1"] == "league"
        assert c.execute(text(
            "SELECT status FROM season s JOIN competition c ON c.id = s.competition_id "
            "WHERE c.slug = 'ipl'")).scalar() == "completed"  # a Final was played
        assert c.execute(text("SELECT status FROM match WHERE id = 'm3'")).scalar() == "no_result"
        assert c.execute(text("SELECT MIN(data_level) FROM match")).scalar() == 4
        assert c.execute(text(
            "SELECT COUNT(*) FROM external_id WHERE entity_type='match' AND source='cricsheet'")).scalar() == 7


def test_same_team_name_in_mens_and_womens_cricket_is_two_teams(mixed_db):
    with mixed_db.connect() as c:
        alphas = c.execute(text("SELECT gender, team_type FROM team WHERE name = 'Alpha'")).all()
    assert sorted(alphas) == [("MEN", "FRANCHISE"), ("WOMEN", "FRANCHISE")]


def test_one_player_identity_across_competitions(mixed_db):
    with mixed_db.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM player WHERE id = 'id-Alpha1'")).scalar() == 1
        comps = {r[0] for r in c.execute(text(
            "SELECT c.slug FROM player_team pt JOIN competition c ON c.id = pt.competition_id "
            "WHERE pt.player_id = 'id-Alpha1'"))}
        assert comps == {"ipl", "mens-t20is"}
        teams = c.execute(text("SELECT team_type FROM team WHERE name = 'Nation'")).scalar()
        assert teams == "NATIONAL"


def test_officials_are_recorded_but_not_searchable_as_players(mixed_db):
    from app.analytics import names, store

    with mixed_db.connect() as c:
        assert c.execute(text("SELECT role FROM match_official WHERE match_id = 'm1'")).scalar() == "umpire"
    assert names.search(store.get(), "Ump One") == []


def test_reimport_is_idempotent(mixed_db, tmp_path):
    from app.ingestion.cricsheet import ingest_directory

    with Session(mixed_db) as db:
        stats = ingest_directory(db, tmp_path / "ipl_json", dataset="ipl")
    assert stats.ingested == 0 and stats.skipped == 5


# ------------------------------------------------------------------ scoping
def test_default_scope_is_the_default_competition(mixed_db):
    from app.analytics import store

    ds = store.get_scoped(None)
    assert ds.scope.slugs == ("ipl",)
    assert set(ds.matches["id"]) == {"m1", "m2", "m3", "m4", "m5"}
    assert set(ds.deliveries["match_id"]) <= {"m1", "m2", "m3", "m4", "m5"}


def test_scope_refuses_to_pool_genders(mixed_db):
    from app.analytics import store

    with pytest.raises(store.ScopeError) as err:
        store.get_scoped(["ipl", "wpl"])
    assert err.value.status == 422


def test_scope_allows_same_gender_and_format(mixed_db):
    from app.analytics import store

    ds = store.get_scoped(["ipl", "mens-t20is"])
    assert ds.scope.match_type == "T20" and ds.scope.gender == "MEN"
    assert "i1" in set(ds.matches["id"])


def test_api_scoping_and_profile_competitions(mixed_db):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    assert client.get("/api/overview").json()["summary"]["matches"] == 5
    assert client.get("/api/overview?competition=wpl").json()["summary"]["matches"] == 1
    assert client.get("/api/overview?competition=ipl&competition=wpl").status_code == 422
    assert client.get("/api/overview?competition=nope").status_code == 404

    profile = client.get("/api/players/id-Alpha1").json()
    assert profile["scope"]["competitions"] == ["ipl"]  # busiest competition
    assert {c["slug"] for c in profile["competitions"]} == {"ipl", "mens-t20is"}
    t20i = client.get("/api/players/id-Alpha1?competition=mens-t20is").json()
    assert t20i["scope"]["competitions"] == ["mens-t20is"]


def test_competition_directory_and_coverage(mixed_db):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    women = client.get("/api/competitions?gender=WOMEN").json()
    wpl = next(c for c in women["items"] if c["slug"] == "wpl")
    assert wpl["coverage"]["status"] == "ball_by_ball" and wpl["coverage"]["matches"] == 1
    bbl = client.get("/api/competitions/bbl").json()
    assert bbl["coverage"]["status"] == "not_ingested"
    ranji = client.get("/api/competitions/ranji-trophy").json()
    assert ranji["coverage"]["status"] == "unavailable" and ranji["seasons"] == []
    fixtures = client.get("/api/competitions/ipl/seasons/2030/fixtures").json()
    assert fixtures["available"] is False and fixtures["items"] == []
    results = client.get("/api/competitions/ipl/seasons/2030/results").json()
    texts = {r["id"]: r["result"] for r in results["items"]}
    assert texts["m1"] == "Alpha won by 10 runs"
    assert texts["m2"] == "Gamma won by 6 wickets"
    assert texts["m3"] == "No result"
    assert texts["m4"] == "Match tied; Alpha won the super over"


def test_competition_without_points_system_shows_no_table(mixed_db):
    from fastapi.testclient import TestClient

    from app.main import app

    table = TestClient(app).get("/api/competitions/wpl/seasons/2030/standings").json()
    assert table["available"] is False
    assert "No points system" in table["reason"]


# ---------------------------------------------------------------- standings
def test_standings_hand_worked(mixed_db):
    """IPL rules (2 win, 1 no result, super over decides ties).

    Points:  Alpha  W(m1) + NR(m3) + W(m4, super over)  = 2 + 1 + 2 = 5
             Gamma  W(m2) + NR(m3) + L(m4)              = 2 + 1 + 0 = 3
             Beta   L(m1) + L(m2)                       = 0
    The m5 Final is a knockout and is not counted.

    Net run rate (runs per over; all-out charged the full 20 overs; super
    over and no-result excluded; side batting first credited target-1):
      Alpha  for (160 + 120) / 40 ov = 7.000; against (150 + 120) / 40 = 6.750  -> +0.250
      Beta   for (150 + 140) / 40 ov = 7.250; against (160 + 141) / 35 = 8.600  -> -1.350
      Gamma  for (141 + 120) / 35 ov = 7.457; against (140 + 120) / 40 = 6.500  -> +0.957
    """
    from app.analytics import standings, store

    ds = store.get_scoped(["ipl"])
    sid = int(ds.seasons.index[ds.seasons["name"] == "2030"][0])
    rules = next(p for p in catalog.catalogue()["points_systems"] if p["slug"] == "ipl-league")
    table = standings.compute(ds, sid, rules)
    rows = {r["name"]: r for r in table["groups"][0]["rows"]}

    assert [r["name"] for r in table["groups"][0]["rows"]] == ["Alpha", "Gamma", "Beta"]
    assert (rows["Alpha"]["points"], rows["Gamma"]["points"], rows["Beta"]["points"]) == (5, 3, 0)
    assert (rows["Alpha"]["won"], rows["Alpha"]["no_result"], rows["Alpha"]["tied"]) == (2, 1, 0)
    assert rows["Alpha"]["net_run_rate"] == 0.25
    assert rows["Beta"]["net_run_rate"] == -1.35
    assert rows["Gamma"]["net_run_rate"] == pytest.approx(0.957, abs=1e-3)
    # Beta played two counted matches, the others three: flagged, not hidden.
    assert table["complete"] is False and table["warnings"]
    assert rows["Gamma"]["reached_knockouts"] and not rows["Beta"]["reached_knockouts"]


def test_standings_tie_breaker_order_is_configurable(mixed_db):
    from app.analytics import standings, store

    ds = store.get_scoped(["ipl"])
    sid = int(ds.seasons.index[ds.seasons["name"] == "2030"][0])
    rules = dict(next(p for p in catalog.catalogue()["points_systems"] if p["slug"] == "ipl-league"))
    # Under "share a tie" rules Alpha's super-over win becomes a tie: 1 + 1 + 2 = 4 points.
    rules["tie_resolution"] = "shared"
    rows = {r["name"]: r for r in standings.compute(ds, sid, rules)["groups"][0]["rows"]}
    assert rows["Alpha"]["points"] == 4 and rows["Alpha"]["tied"] == 1
    assert rows["Gamma"]["points"] == 4


def test_rain_revised_target_uses_par_for_side_batting_first():
    """Side batting first is credited target-1 off the revised overs."""
    import pandas as pd

    from app.analytics.standings import _nrr_contributions

    match = pd.Series({"id": "r1", "balls_per_over": 6, "overs_limit": 20})
    totals = pd.DataFrame([
        {"match_id": "r1", "innings_number": 1, "batting_team_id": 1, "bowling_team_id": 2,
         "runs": 100, "balls": 72, "wickets": 3, "target_runs": None, "target_overs": None},
        {"match_id": "r1", "innings_number": 2, "batting_team_id": 2, "bowling_team_id": 1,
         "runs": 91, "balls": 48, "wickets": 2, "target_runs": 90, "target_overs": 10},
    ])
    first, second = _nrr_contributions(match, totals)
    assert (first["runs_for"], first["balls_for"]) == (89, 60)
    assert (second["runs_for"], second["balls_for"]) == (91, 48)


# ---------------------------------------------------------------- migrations
def test_legacy_database_is_upgraded_in_place(tmp_path, monkeypatch):
    """A database built by the old create_all path keeps its rows and gets linked."""
    from app.core.migrate import downgrade, upgrade

    eng = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}", future=True)
    assert upgrade(eng, "0001") == "0001"
    with eng.begin() as c:
        c.execute(text("DROP TABLE alembic_version"))  # as create_all left it
        c.execute(text("INSERT INTO team (id, name, short_name, aliases) VALUES "
                       "(1, 'Alpha', 'ALP', '[]'), (2, 'Beta', NULL, '[]')"))
        c.execute(text(
            "INSERT INTO match (id, match_type, event_name, gender, season, season_label, date, "
            "team1_id, team2_id, winner_id, result, balls_per_over, source_file, stage) VALUES "
            "('L1', 'T20', 'Indian Premier League', 'male', 2008, '2007/08', '2008-04-18', "
            "1, 2, 1, 'normal', 6, 'L1.json', NULL),"
            "('L2', 'T20', 'Indian Premier League', 'male', 2008, '2007/08', '2008-06-01', "
            "1, 2, 2, 'normal', 6, 'L2.json', 'Final')"))
        c.execute(text("INSERT INTO innings (id, match_id, innings_number, batting_team_id, "
                       "bowling_team_id, is_super_over, is_chase) VALUES (1, 'L1', 1, 1, 2, 0, 0)"))

    assert upgrade(eng) == "0002"
    with eng.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM innings")).scalar() == 1  # not cascaded away
        linked = c.execute(text(
            "SELECT c.slug, s.name, s.status FROM match m JOIN competition c ON c.id = m.competition_id "
            "JOIN season s ON s.id = m.season_id WHERE m.id = 'L1'")).one()
        assert tuple(linked) == ("ipl", "2008", "completed")
        assert c.execute(text("SELECT gender, team_type FROM team WHERE id = 1")).one() == ("MEN", "FRANCHISE")

    downgrade("0001", eng)
    with eng.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM match")).scalar() == 2
        assert c.execute(text("SELECT COUNT(*) FROM innings")).scalar() == 1
        tables = {r[0] for r in c.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        assert "competition" not in tables


# ------------------------------------------------- decisions from real data
def test_the_hundred_is_its_own_format():
    from app.analytics.constants import phase_for_over
    from app.ingestion.cricsheet import normalise_match_type

    # Cricsheet labels The Hundred "T20" with 5-ball overs.
    assert normalise_match_type({"match_type": "T20", "balls_per_over": 5}) == "Hundred"
    assert normalise_match_type({"match_type": "T20", "balls_per_over": 6}) == "T20"
    # Its powerplay is the first 25 balls: sets 1-5, not T20's overs 1-6.
    assert [phase_for_over(o, "Hundred") for o in (4, 5)] == ["powerplay", "middle"]


def test_challenger_is_a_knockout():
    assert classify_stage("Challenger", None) == ("Challenger", "knockout")


def test_season_naming_choices_follow_the_data():
    by_slug = {c["slug"]: c["season_naming"] for c in catalog.catalogue()["competitions"]}
    # Seasons that cross 31 December keep the source label...
    assert by_slug["bbl"] == by_slug["sa20"] == "source_label"
    # ...and PSL uses the calendar year: its 2020 playoffs (Nov 2020) are
    # labelled 2020/21 by the source, alongside PSL 2021.
    assert by_slug["psl"] == "calendar_year"
    assert season_identity("calendar_year", "2020/21", dt.date(2020, 11, 14)) == ("2020", 2020)


def test_global_summary_counts_without_pooling(mixed_db):
    from fastapi.testclient import TestClient

    from app.main import app

    s = TestClient(app).get("/api/summary").json()
    assert s["matches"] == 7 and s["matches_by_gender"] == {"MEN": 6, "WOMEN": 1}
    assert s["competitions"]["with_data"] == 3
    assert s["competitions"]["women_with_data"] == 1
    assert {c["slug"] for c in s["with_data"]} == {"ipl", "wpl", "mens-t20is"}
    # Latest results carry their competition, newest first.
    assert s["latest_results"][0]["id"] == "i1"
    assert s["latest_results"][0]["competition"]["slug"] == "mens-t20is"
    # Suggestions are leaders within one competition each, never a combined total.
    assert len({p["competition"] for p in s["suggestions"]}) == len(s["suggestions"])
