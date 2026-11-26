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
from sqlalchemy import create_engine, select, text, update
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


def test_every_country_flag_decodes_to_an_iso_region():
    """The flag is load-bearing, not decoration.

    Cricket codes (IND, RSA, ENG) are not ISO, and the frontend orders the
    competition directory by matching a reader's ISO country against each
    competition's flag — decoding the regional indicator letters rather than
    keeping a second 111-row mapping that could drift from this one. A flag
    built by hand out of the wrong code points would break that silently, so
    the same decode runs here.
    """
    def region(flag: str) -> str | None:
        points = [ord(c) for c in flag]
        letters = "".join(chr(c - 0x1F1E6 + 65) for c in points if 0x1F1E6 <= c <= 0x1F1FF)
        if len(letters) == 2:
            return letters
        # England, Scotland and Wales: a black flag plus tags spelling "gbeng".
        tags = "".join(chr(c - 0xE0000) for c in points if 0xE0061 <= c <= 0xE007A)
        return tags[:2].upper() if len(tags) >= 2 else None

    countries = catalog.catalogue()["countries"]
    flagged = [c for c in countries if c["flag"]]
    # The multi-nation sides (West Indies, the World XIs) have no flag to fly.
    assert len(flagged) >= 100, "the catalogue lost its flags"
    for c in flagged:
        assert region(c["flag"]) is not None, f"{c['code']} has an undecodable flag"
    # Spot-check the two shapes, including the subdivision sequence that makes
    # a reader in the UK meet county cricket first.
    by_code = {c["code"]: c for c in countries}
    assert region(by_code["IND"]["flag"]) == "IN"
    assert region(by_code["RSA"]["flag"]) == "ZA"
    assert region(by_code["ENG"]["flag"]) == "GB"
    # Two competitions must never collide on one region by accident.
    regions = [region(c["flag"]) for c in flagged]
    assert regions.count("IN") == 1


def test_every_catalogued_competition_is_ranked_for_display():
    """Lists are ordered by prominence, so an unranked competition would sort
    behind the auto-created one-match tours - which is right for those, and
    wrong for anything curated."""
    from app.analytics.competitions import UNRANKED, prominence

    ranks = prominence()
    for c in catalog.catalogue()["competitions"]:
        assert ranks.get(c["slug"]) is not None, f"{c['slug']} has no prominence"
        assert ranks[c["slug"]] < UNRANKED


@pytest.mark.parametrize("ahead, behind", [
    ("ipl", "npl"),                       # the complaint that prompted the ranking
    ("ipl", "bbl"),
    ("bbl", "ilt20"),
    ("mens-t20is", "womens-tests"),
    ("icc-mens-cricket-world-cup", "icc-u19-mens-cricket-world-cup"),
    ("county-championship", "bob-willis-trophy"),
])
def test_prominence_order(ahead, behind):
    from app.analytics.competitions import prominence

    ranks = prominence()
    assert ranks[ahead] < ranks[behind], f"{ahead} should rank ahead of {behind}"


@pytest.mark.parametrize("slug, first_match, expected", [
    ("ipl", "2008-04-18", True),            # the IPL began in 2008; every ball is held
    ("mens-t20is", "2005-02-17", True),     # the first men's T20I was 17 Feb 2005
    ("mens-tests", "2001-12-19", False),    # Test cricket dates from 1877
    ("county-championship", "2014-04-06", False),
    ("one-day-cup-england", "2014-07-26", None),   # lineage ambiguous: no claim
    ("not-a-competition", "2014-01-01", None),     # uncatalogued: no claim
    ("ipl", None, None),                           # nothing ingested yet
])
def test_coverage_is_complete_only_where_the_data_reaches_the_first_season(
    slug, first_match, expected
):
    """A most-runs list is the competition's real order only where STRYK holds
    every season. Where it does not, the list ranks players by how much of
    their career falls inside the data - which is why Tendulkar is not top of
    the Test runs - so the interface withholds it."""
    from app.analytics.competitions import coverage_is_complete

    assert coverage_is_complete(slug, first_match) is expected


def test_a_competitions_first_season_is_never_after_its_data():
    """A founding year later than the first indexed match would mean one of
    the two is wrong, and would wrongly mark the competition as complete."""
    from app.analytics import competitions as service
    from app.analytics import store

    ds = store.get()
    if ds.competitions.empty:
        pytest.skip("no ingested data")
    firsts = service.first_seasons()
    for cid, row in ds.competitions.iterrows():
        began = firsts.get(row["slug"])
        m = ds.matches[ds.matches["competition_id"] == cid]
        if began is None or m.empty:
            continue
        played = int(m["date"].min().year)
        assert began <= played, (
            f"{row['slug']}: catalogue says it began in {began} but the data starts {played}"
        )


def test_one_event_name_can_be_two_competitions_when_the_format_differs():
    """The men's Asia Cup is called "Asia Cup" whether it is played as ODIs or
    T20s, and no analysis may pool formats, so the event rule has to be able
    to tell them apart."""
    odi = resolve(MatchContext("Asia Cup", "MEN", "ODI", None), COMPS)
    t20 = resolve(MatchContext("Asia Cup", "MEN", "T20", None), COMPS)
    assert odi["slug"] == "asia-cup"
    assert t20["slug"] == "mens-t20-asia-cup"


def test_twenty_over_internationals_are_one_format_however_the_source_marks_them():
    """Cricsheet writes "IT20" for a twenty-over international between
    associate members and "T20" when a full member plays. They are the same
    format, and the Asian Games - which has both - must not be refused as a
    scope spanning two."""
    from app.analytics.store import canonical_format

    assert canonical_format("IT20") == canonical_format("T20") == "T20"
    assert canonical_format("ODI") == "ODI"
    assert canonical_format(None) is None


def test_an_event_rule_claims_every_format_it_does_not_name():
    """A rule without a match_type takes the whole event; one with a
    match_type takes only that format."""
    asian_games = resolve(MatchContext("Asian Games Men's Cricket Competition", "MEN", "IT20", None), COMPS)
    assert asian_games["slug"] == "asian-games-cricket-men"
    assert resolve(MatchContext("Asia Cup", "MEN", "Test", None), COMPS) is None


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
    (lambda c: c["competitions"][0].update(prominence=0), "prominence must be 1-5"),
    (lambda c: c["competitions"][0].update(prominence="1"), "prominence must be 1-5"),
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
    from app.core.migrate import head, upgrade

    eng = create_engine(f"sqlite:///{tmp_path / 'stryk.db'}", future=True)
    assert upgrade(eng) == head()
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
def test_relink_leaves_bilateral_matches_where_they_are(mixed_db):
    """The re-link moves a match only when a catalogue event rule names its
    event. A bilateral tour ("Nation tour of Other") is not a competition of
    its own, and a rule that started claiming those would quietly empty the
    men's T20I record into hundreds of two-match "competitions"."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    import relink

    with Session(mixed_db) as db:
        _, moves = relink.plan(db)
    assert moves == [], f"nothing here should move, got {[(m[2], m[3]) for m in moves]}"


def test_relink_moves_a_match_an_event_rule_now_claims(mixed_db):
    """Ingest skips matches it has already imported, so a rule added to the
    catalogue later never moves the matches it now owns. That is why the Asia
    Cup sat inside Men's ODIs: the re-link is what closes the gap."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    import relink
    from app.models import Competition, Match

    with Session(mixed_db) as db:
        # Put a men's T20I where an "Asia Cup" rule will disagree with it.
        wrong = db.execute(select(Competition.id).where(Competition.slug == "mens-t20is")).scalar()
        match_id = db.execute(
            select(Match.id).where(Match.event_name == "Nation tour of Other")
        ).scalar()
        db.execute(update(Match).where(Match.id == match_id)
                   .values(event_name="Asia Cup", competition_id=wrong))
        db.flush()

        _, moves = relink.plan(db)
        assert len(moves) == 1, moves
        _row, _ctx, src, dst = moves[0]
        # A T20 "Asia Cup" is the T20 competition, never the ODI one.
        assert (src, dst) == ("mens-t20is", "mens-t20-asia-cup")


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


def test_one_person_in_both_squads_does_not_abort_the_import(db_engine, tmp_path):
    """Cricsheet sometimes resolves two scorecard names to one registry person.

    Real example: match 1130677 lists KV Sharma for both Vidarbha and Railways,
    so the squad carries the same player_id twice and the (match_id, player_id)
    unique constraint rejects the batch. One bad file used to abort a whole
    dataset -- it took down the entire Syed Mushtaq Ali and T20I imports.
    """
    directory = tmp_path / "ipl_json"
    directory.mkdir(parents=True, exist_ok=True)
    _match_file(directory, "dup1", teams=["Alpha", "Beta"],
                outcome={"winner": "Alpha", "by": {"runs": 10}},
                innings=[_innings("Alpha", 60, 36, 2, _squad("Alpha"), "Beta11")])
    doc = json.loads((directory / "dup1.json").read_text())
    people = doc["info"]["registry"]["people"]
    people["Beta1"] = people["Alpha1"]  # one person, listed on both sides
    (directory / "dup1.json").write_text(json.dumps(doc))

    stats = _ingest(db_engine, directory, "ipl")
    assert stats.ingested == 1

    with Session(db_engine) as db:
        squad = db.execute(text(
            "select count(*) from match_player where match_id = 'dup1'")).scalar()
    # 22 listed, but one is the same person twice: 21 distinct rows.
    assert squad == 21


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


def test_compare_scopes_itself_to_common_ground_not_the_default_competition(mixed_db):
    """A comparison is only meaningful inside a competition both have played.

    Defaulting to the site-wide competition would show one real record beside
    a blank one and call that a comparison.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)

    # Alpha1 plays IPL and men's T20Is; Nation2 only the T20I. The default
    # competition is the IPL, and the comparison must not use it.
    both = client.get("/api/compare?player=id-Alpha1&player=id-Nation2").json()
    assert both["scope"]["competitions"] == ["mens-t20is"]
    assert [c["slug"] for c in both["competitions"]] == ["mens-t20is"]

    # Alpha1 and Beta1 share the IPL, which is also where Alpha1 has played most.
    ipl = client.get("/api/compare?player=id-Alpha1&player=id-Beta1").json()
    assert ipl["scope"]["competitions"] == ["ipl"]

    # An explicit scope still wins over the shared default.
    forced = client.get("/api/compare?player=id-Alpha1&player=id-Beta1&competition=mens-t20is")
    assert forced.json()["scope"]["competitions"] == ["mens-t20is"]

    # A men's and a women's player share nothing: an empty list, not a scope
    # in which one of them is all zeroes.
    none = client.get("/api/compare?player=id-Alpha1&player=id-AlphaW1").json()
    assert none["competitions"] == []


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
    from app.core.migrate import downgrade, head, upgrade

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

    assert upgrade(eng) == head()
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


def test_national_teams_are_linked_to_a_country_and_clubs_are_not(tmp_path):
    """A nation gets its country, flag and code; anything else is left alone.

    The interface draws a flag only when the API sends one, so the thing that
    must hold is that a flag never appears for a side that has no nation —
    a club, or a composite XI like the ICC World XI, which is a real team and
    deliberately carries a null flag.
    """
    from sqlalchemy import create_engine

    from app import catalog
    from app.core.migrate import upgrade
    from app.ingestion.linking import link_countries

    eng = create_engine(f"sqlite:///{tmp_path / 'c.db'}", future=True)
    upgrade(eng)
    with Session(eng) as db:
        catalog.seed(db)
        db.execute(text(
            "INSERT INTO team (name, gender, aliases, is_national_team, team_type) VALUES "
            "('India', 'MEN', '[]', 1, 'NATIONAL'),"
            "('United States of America', 'MEN', '[]', 1, 'NATIONAL'),"
            "('ICC World XI', 'MEN', '[]', 1, 'NATIONAL'),"
            "('Atlantis', 'MEN', '[]', 1, 'NATIONAL'),"
            "('Surrey', 'MEN', '[]', 0, 'DOMESTIC')"))
        assert link_countries(db) == 3   # Atlantis is no country; Surrey is no nation
        db.commit()

        got = dict(db.execute(text(
            "SELECT t.name, c.flag FROM team t LEFT JOIN country c ON c.id = t.country_id")).all())
        assert got["India"] == "\U0001F1EE\U0001F1F3"
        # The match files spell it out; the catalogue matches it by alias.
        assert got["United States of America"] == "\U0001F1FA\U0001F1F8"
        assert got["ICC World XI"] is None      # a real side, no single nation
        assert got["Atlantis"] is None          # unknown: linked to nothing, invented nothing
        assert got["Surrey"] is None            # a club has no flag here

        codes = dict(db.execute(text("SELECT name, short_name FROM team")).all())
        assert codes["India"] == "IND" and codes["ICC World XI"] == "WLDXI"
        assert codes["Atlantis"] is None and codes["Surrey"] is None

        # Idempotent: a second pass changes nothing.
        assert link_countries(db) == 3
