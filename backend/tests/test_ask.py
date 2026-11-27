"""The natural-language layer, exercised without a credential or a network.

``translate`` takes an injectable client so everything around the model call -
the mapping onto real filters, and the reporting of whatever could not be
expressed - is testable from a fixed Translation.

The property worth protecting here is not coverage but honesty: a clause the
vocabulary cannot express must reach the caller, because an answer that
quietly ignores "against left-arm spin" is an answer to a different question.
"""

from __future__ import annotations

import datetime as dt
import json
import types

import pandas as pd
import pytest

from app.analytics import ask, players as player_service


def _ds(teams: dict[int, str] | None = None):
    """A Dataset stub with only what the translation layer touches."""
    frame = pd.DataFrame(
        [{"name": n, "short_name": None} for n in (teams or {}).values()],
        index=list((teams or {}).keys()),
    )
    return types.SimpleNamespace(teams=frame, competitions=pd.DataFrame())


def _t(**kw) -> ask.Translation:
    """A Translation with every required field at its "not specified" value.

    The schema deliberately has no optional keys - see Translation - so even a
    test that cares about one field has to supply all 22. Keeping that in one
    place means adding a field does not edit every test.
    """
    base = dict(
        competition="", seasons=[], team_names=[], opposition_names=[],
        chasing="", result="", target_from=0, target_to=0, over_from=0, over_to=0,
        phases=[], innings=0, date_from="", date_to="",
        sort="runs", order="desc", role="",
        min_balls=0, min_innings=0, min_runs=0, min_wickets=0,
        interpretation="", unsupported=[],
    )
    return ask.Translation(**{**base, **kw})


def test_the_schema_has_no_optional_fields():
    """The regression that cost an afternoon: optional keys do not compile.

    A JSON schema whose keys may each be present or absent describes 2^n
    objects, and structured outputs compile that grammar before running. At 13
    optional fields a request took over a minute; at 14 the API rejected it
    with "Schema is too complex". All-required compiles in seconds, so a
    stray ``Optional[...]`` or default value here breaks /api/ask in
    production while every other test still passes.
    """
    schema = ask.Translation.model_json_schema()
    assert set(schema["required"]) == set(ask.Translation.model_fields)
    # Optional[X] renders as anyOf[X, null], which is the same trap by another
    # spelling: the sentinel values exist so that nullable types are not needed.
    assert "anyOf" not in json.dumps(schema)

def test_a_clause_with_no_filter_behind_it_is_reported():
    t = _t(
        competition="ipl", sort="runs",
        interpretation="Most runs in the IPL.",
        unsupported=["against left-arm spin"],
    )
    filters, notes = ask._to_filters(t, _ds())
    # Nothing invented to stand in for the clause ...
    assert filters.describe() == {"include_super_over": False}
    # ... and the clause itself survives to the caller.
    assert t.unsupported == ["against left-arm spin"]
    assert notes == []


def test_the_worked_example_maps_onto_real_filters():
    """"Most runs in a 180+ run chase in IPL" is target_from, nothing more."""
    t = _t(
        competition="ipl", target_from=180, sort="runs", order="desc",
        interpretation="Most runs while chasing 180 or more in the IPL.",
    )
    filters, notes = ask._to_filters(t, _ds())
    assert filters.target_from == 180
    assert filters.target_to is None
    assert notes == []


def test_overs_and_dates_cross_over_intact():
    t = _t(
        over_from=17, over_to=20, date_from="2024-01-01", date_to="2024-12-31",
        innings=2, chasing="second", sort="economy", order="asc",
        interpretation="Death-over economy while chasing in 2024.",
    )
    filters, notes = ask._to_filters(t, _ds())
    assert (filters.over_from, filters.over_to) == (17, 20)
    assert filters.date_from == dt.date(2024, 1, 1)
    assert filters.chasing is True
    assert notes == []


def test_an_unreadable_date_is_reported_not_dropped():
    t = _t(date_from="last April", sort="runs",
                        interpretation="Since last April.")
    filters, notes = ask._to_filters(t, _ds())
    assert filters.date_from is None
    assert any("last April" in n for n in notes)


def test_team_names_resolve_to_ids_and_misses_are_reported():
    ds = _ds({7: "Mumbai Indians", 10: "Rajasthan Royals"})
    t = _t(team_names=["Mumbai"], opposition_names=["Sydney Sixers"],
                        sort="runs", interpretation="Mumbai against Sydney.")
    filters, notes = ask._to_filters(t, ds)
    assert filters.team_ids == [7]
    # A competition that has never met that side must say so, not silently
    # return every opponent.
    assert filters.opposition_ids is None
    assert any("Sydney Sixers" in n for n in notes)


def test_an_invented_sort_key_cannot_reach_the_query():
    """Structured output fixes the schema, but not the *value* of `sort`."""
    assert "control_pct" not in player_service.SORT_COLUMNS
    captured = {}

    def fake_directory(ds, f, **kw):
        captured.update(kw)
        return {"rows": [], "total": 0}

    t = _t(sort="control_pct", interpretation="By control percentage.")
    monkey = player_service.directory
    player_service.directory = fake_directory
    try:
        out = ask.answer("whatever", _ds(), client=lambda q: t)
    finally:
        player_service.directory = monkey

    assert captured["sort"] == "runs"
    assert any("control_pct" in n for n in out["unsupported"])


def test_translate_without_a_credential_raises_ask_unavailable(monkeypatch):
    """A missing or broken credential is a clear 503, not a wrong answer."""
    import anthropic

    def explode(*a, **k):
        raise anthropic.AnthropicError("no credential")

    monkeypatch.setattr(anthropic, "Anthropic", explode)
    with pytest.raises(ask.AskUnavailable):
        ask.translate("most runs", _ds())


def test_a_competition_named_in_the_question_reopens_the_dataset(monkeypatch):
    """"In the BBL" must change which deliveries are read, not just the prose.

    Competition is a scope, not a filter: the default scope is the IPL, so a
    question about the BBL that never reaches ``rescope`` returns IPL rows
    under a BBL sentence - the exact silent wrong answer this module exists
    to prevent.
    """
    bbl = _ds()
    seen = {}

    def fake_directory(ds, f, **kw):
        seen["ds"] = ds
        return {"rows": [], "total": 0}

    monkeypatch.setattr(player_service, "directory", fake_directory)
    t = _t(competition="bbl", interpretation="Most runs in the BBL.")
    out = ask.answer("most runs in the bbl", _ds(), client=lambda q: t,
                     rescope=lambda slug: bbl if slug == "bbl" else None)
    assert seen["ds"] is bbl
    assert out["unsupported"] == []


def test_a_scope_the_question_cannot_reach_is_reported(monkeypatch):
    """A caller that pinned the scope wins, but the mismatch must be visible."""
    ds = _ds()
    ds.scope = types.SimpleNamespace(slugs=("ipl",))
    monkeypatch.setattr(player_service, "directory", lambda ds, f, **kw: {"rows": [], "total": 0})
    t = _t(competition="bbl", interpretation="Most runs in the BBL.")
    out = ask.answer("most runs in the bbl", ds, client=lambda q: t)  # no rescope
    assert any("bbl" in n and "ipl" in n for n in out["unsupported"])


def test_an_unknown_competition_does_not_silently_fall_back(monkeypatch):
    ds = _ds()
    ds.scope = types.SimpleNamespace(slugs=("ipl",))
    monkeypatch.setattr(player_service, "directory", lambda ds, f, **kw: {"rows": [], "total": 0})

    def boom(slug):
        raise LookupError(f"Unknown competition {slug!r}")

    t = _t(competition="nonsuch", interpretation="Most runs.")
    out = ask.answer("most runs in nonsuch", ds, client=lambda q: t, rescope=boom)
    assert any("nonsuch" in n for n in out["unsupported"])


def test_the_answer_states_the_scope_it_actually_read(monkeypatch):
    """`interpretation` is the model's prose; `scope` is the ground truth.

    If a rescope fails, the sentence still says "in the BBL". Only this field
    tells the reader the rows came from somewhere else.
    """
    ds = _ds()
    ds.scope = types.SimpleNamespace(slugs=("ipl",))
    monkeypatch.setattr(player_service, "directory", lambda ds, f, **kw: {"rows": [], "total": 0})
    t = _t(competition="bbl", interpretation="Most runs in the BBL.")
    out = ask.answer("most runs in the bbl", ds, client=lambda q: t)
    assert out["scope"] == ["ipl"]


def test_a_winning_cause_is_a_filter_not_a_caveat():
    """"In a winning cause" used to be reported as inexpressible. It is not."""
    t = _t(result="won", team_names=["Punjab"], interpretation="PBKS runs in wins.")
    filters, notes = _to_filters_of(t)
    assert filters.result == "won"
    assert notes == []


def test_an_unreadable_result_is_reported_not_guessed():
    t = _t(result="draw", interpretation="Runs in draws.")
    filters, notes = _to_filters_of(t)
    assert filters.result is None
    assert any("draw" in n for n in notes)


def _to_filters_of(t):
    return ask._to_filters(t, _ds({3: "Punjab Kings"}))
