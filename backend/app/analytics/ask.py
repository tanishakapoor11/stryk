"""Natural language to the filter vocabulary Stryk already has.

A question like "most runs in a 180+ run chase in IPL" is answered by
translating it into the same query parameters the ``/api/players`` endpoint
takes, then running that query. Nothing here computes a statistic: the model
chooses filters, and :mod:`app.analytics.players` does the arithmetic as it
always has.

Two properties matter more than coverage, because a statistics tool that
quietly answers a question nobody asked is worse than one that declines:

* **Only real filters can be emitted.** The model fills in
  :class:`Translation`, whose fields are exactly the supported parameters, and
  structured outputs make a schema-valid object a guarantee rather than a
  hope. There is no path by which an invented parameter reaches the query.
* **Dropped clauses are reported, never swallowed.** Anything the vocabulary
  cannot express goes in ``unsupported`` and is shown to the reader beside the
  answer. "Against left-arm spin" has no filter behind it today, so a question
  asking for it gets a visible caveat instead of a silent lie.

The model is asked for one small JSON object, so this is a cheap call on a
short prompt - see ``Settings.ask_model`` and ``_EFFORT``.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

from pydantic import BaseModel, Field

from app.analytics import players as player_service
from app.analytics.constants import PHASE_ORDER
from app.analytics.store import Dataset, Filters
from app.core.config import settings

log = logging.getLogger("stryk.ask")

#: Translation is a short extraction into a fixed schema, not a reasoning
#: problem, so it runs at low effort on a small output budget. The model
#: itself is configurable - see Settings.ask_model.
_EFFORT = "low"
_MAX_TOKENS = 2048

#: Model families that accept server-side refusal fallback. Claude Haiku has
#: none, so the parameter is left off there rather than sent and rejected.
_FALLBACK_PREFIXES = ("claude-opus-", "claude-sonnet-5-5", "claude-fable-", "claude-mythos-")


class AskUnavailable(RuntimeError):
    """No Anthropic credential is configured, or the API could not be reached."""


class Translation(BaseModel):
    """The filter vocabulary, as the model is allowed to fill it in.

    Every field maps onto a real query parameter. Adding one here without
    adding it to :func:`_to_filters` would be a silent no-op, so the two are
    deliberately kept adjacent.

    **Every field is required, and "not specified" is a sentinel value** -
    an empty string, a zero, an empty list - rather than an absent key or a
    null. This is not a style choice. A schema whose keys may each be present
    or absent describes 2^n possible objects, and the API compiles that into
    a decoding grammar before it runs: at 13 optional fields the request takes
    over a minute, and at 14 it is rejected outright with "Schema is too
    complex". The same 22 fields, all required, compile in under five seconds.
    :func:`_to_filters` turns the sentinels back into ``None``.
    """

    competition: str = Field(
        ..., description="Competition slug, e.g. 'ipl'. Empty string if the question names none.")
    seasons: List[int] = Field(
        ..., description="Calendar years, e.g. [2024, 2025]. Empty list if unspecified.")
    team_names: List[str] = Field(
        ..., description="The player's own team(s), as written in the question. [] if none.")
    opposition_names: List[str] = Field(
        ..., description="The opposing team(s), as written in the question. [] if none.")
    chasing: str = Field(
        ..., description="'second' for batting second (chasing), 'first' for batting "
                         "first, empty string if the question does not say.")
    target_from: int = Field(
        ..., description="Minimum runs required to win. '180+ chase' is 180. 0 if unspecified.")
    target_to: int = Field(..., description="Maximum runs required to win. 0 if unspecified.")
    over_from: int = Field(
        ..., description="First over of a range, counting from 1. 0 if unspecified.")
    over_to: int = Field(
        ..., description="Last over of a range, counting from 1. 0 if unspecified.")
    phases: List[str] = Field(
        ..., description=f"Any of {PHASE_ORDER}. [] if unspecified. Prefer over_from/over_to "
                         "when the question names specific overs.")
    innings: int = Field(..., description="Innings number, 1-4. 0 if unspecified.")
    date_from: str = Field(..., description="ISO date, YYYY-MM-DD. Empty string if unspecified.")
    date_to: str = Field(..., description="ISO date, YYYY-MM-DD. Empty string if unspecified.")
    result: str = Field(
        ..., description="'won' for a winning cause, 'lost' for a losing one, empty "
                         "string if the question does not say. A tie is neither.")

    sort: str = Field(..., description="What 'most'/'best' refers to.")
    order: str = Field(..., description="'desc' or 'asc'. Economy and bowling "
                                        "average are best when low, so 'asc'.")
    role: str = Field(
        ..., description="'Batter', 'Bowler' or 'All-rounder'. Empty string if unspecified.")

    min_balls: int = Field(..., description="Qualification floor; 0 for none.")
    min_innings: int = Field(..., description="Qualification floor; 0 for none.")
    min_runs: int = Field(..., description="Qualification floor; 0 for none.")
    min_wickets: int = Field(..., description="Qualification floor; 0 for none.")

    interpretation: str = Field(
        ..., description="One plain sentence describing the query you built.")
    unsupported: List[str] = Field(
        ..., description="Every clause of the question you could NOT express. Empty list "
                         "if all of it was expressible.")


def vocabulary(ds: Dataset) -> str:
    """The prompt's description of what can be asked, built from live code.

    Generated rather than written out so that a filter or sort key added to
    the API cannot drift out of sync with what the model is told exists.
    """
    sorts = ", ".join(sorted(player_service.SORT_COLUMNS))
    comps = ds.competitions
    if not comps.empty:
        top = comps.sort_values("name").head(60)
        known = "; ".join(f"{r.slug} ({r['name']})" for _, r in top.iterrows())
    else:
        known = "none loaded"
    return (
        f"Sort keys: {sorts}.\n"
        f"Phases: {', '.join(PHASE_ORDER)}.\n"
        f"Competition slugs include: {known}."
    )


_SYSTEM = """You translate cricket statistics questions into query filters for \
Stryk, a ball-by-ball analytics tool. You never answer the question yourself and \
you never invent numbers - you only choose filters, and the application computes \
the result.

Rules:
- Use only the fields in the schema. If part of the question cannot be expressed \
by them, put that part in `unsupported`, in the reader's words. This matters more \
than appearing capable: a dropped clause that is not reported produces a confident \
answer to a different question.
- `unsupported` is for clauses with no field behind them. Known examples: bowling \
type (pace vs spin), batting hand, batting position, venue, toss, day/night, \
captaincy, partnerships. None of these are filterable.
- "In a winning cause" / "in a losing cause" IS filterable: set result='won' or \
'lost'. It means the player's own side won or lost that match.
- A target is the runs needed to win, which is one more than the total the \
opposition posted. So "a 180+ run chase" - meaning the side batting first made \
180 or more - is target_from=181, not 180. Convert the same way for any number: \
"chasing N or more" is target_from=N+1.
- "At the death" is overs 17-20 in T20; the powerplay is overs 1-6. Prefer \
over_from/over_to when the question names overs, phases otherwise.
- Economy and bowling average are better when lower: order='asc'.
- When the question asks for a rate (strike rate, economy, average) and names no \
cut-off, set a sensible qualification floor so the result is not topped by a \
two-ball sample: min_balls=500 for batting rates, min_wickets=20 for bowling ones.
- Set `interpretation` to one sentence a reader can check your work against.
- Every field is required. Where the question says nothing, emit the empty \
value - "" for text, 0 for numbers, [] for lists - rather than omitting the key. \
An empty value means "the question did not constrain this"; it is not a guess.
"""


def _to_filters(t: Translation, ds: Dataset) -> tuple[Filters, List[str]]:
    """Build the real filter object, resolving team names to ids.

    A name that matches no team in this scope is reported rather than ignored,
    for the same reason an inexpressible clause is.
    """
    import datetime as dt

    notes: List[str] = []

    def team_ids(names: Optional[List[str]]) -> Optional[List[int]]:
        if not names or ds.teams.empty:
            return None
        found: List[int] = []
        for name in names:
            needle = name.strip().lower()
            hits = [
                int(i) for i, row in ds.teams.iterrows()
                if needle in str(row.get("name", "")).lower()
                or needle in str(row.get("short_name") or "").lower()
            ]
            if hits:
                found.extend(hits)
            else:
                notes.append(f"no team matching {name!r} in this competition")
        return found or None

    def date(value: Optional[str]) -> Optional[dt.date]:
        if not value:
            return None
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            notes.append(f"could not read the date {value!r}")
            return None

    phases = [p for p in t.phases if p in PHASE_ORDER] or None
    # The model speaks in sentinels because the schema has no optional keys
    # (see Translation); "" / 0 / [] all mean "the question did not say".
    none_if_empty = lambda v: v or None
    if t.result and t.result not in ("won", "lost"):
        notes.append(f"could not read {t.result!r} as a match result")
    if t.chasing and t.chasing not in ("first", "second"):
        notes.append(f"could not read {t.chasing!r} as batting first or second")
    return Filters(
        seasons=none_if_empty(t.seasons),
        team_ids=team_ids(t.team_names),
        opposition_ids=team_ids(t.opposition_names),
        phases=phases,
        innings_number=none_if_empty(t.innings),
        chasing={"first": False, "second": True}.get(t.chasing),
        date_from=date(t.date_from),
        date_to=date(t.date_to),
        result=t.result if t.result in ("won", "lost") else None,
        over_from=none_if_empty(t.over_from),
        over_to=none_if_empty(t.over_to),
        target_from=none_if_empty(t.target_from),
        target_to=none_if_empty(t.target_to),
    ), notes


def translate(question: str, ds: Dataset, client: Optional[Callable] = None) -> Translation:
    """Ask the model for a :class:`Translation` of ``question``.

    ``client`` exists so the tests can exercise everything around the call
    without a network or a credential; production passes nothing.
    """
    if client is not None:
        return client(question)

    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise AskUnavailable("the anthropic package is not installed") from exc

    try:
        # The SDK resolves its own credential (env var, then a profile written
        # by `ant auth login`), so an unset ANTHROPIC_API_KEY is not on its own
        # a failure and is not second-guessed here.
        api = anthropic.Anthropic()
        model = settings.ask_model
        extra = {}
        if model.startswith(_FALLBACK_PREFIXES):
            # A question the safety classifier declines is retried on another
            # model rather than reaching the reader as a dead end. Only the
            # beta namespace accepts this, which is why it is used throughout.
            extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
        response = api.beta.messages.parse(
            model=model,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM + "\n" + vocabulary(ds),
            output_config={"effort": _EFFORT},
            messages=[{"role": "user", "content": question}],
            output_format=Translation,
            **extra,
        )
    except Exception as exc:
        log.warning("translation failed: %s", exc)
        raise AskUnavailable(str(exc)) from exc

    if response.stop_reason == "refusal":
        raise AskUnavailable("the question was declined by the safety classifier")
    return response.parsed_output


def answer(question: str, ds: Dataset, limit: int = 10,
           client: Optional[Callable] = None,
           rescope: Optional[Callable[[str], Dataset]] = None) -> dict:
    """Translate ``question``, run it, and return the rows with the reasoning.

    The response carries the filters that were used and everything that could
    not be expressed, so a reader can always see which question was answered.

    ``rescope`` loads a dataset for a competition slug, and is how "in the BBL"
    reaches the data. Competition is not a filter: it chooses which deliveries
    are read at all, so naming one in the question has to re-open the dataset.
    Callers that have already pinned a scope pass nothing, and a question
    naming a different competition is then reported rather than silently
    answered from the wrong one.
    """
    t = translate(question, ds, client=client)
    scope_notes: List[str] = []
    if t.competition:
        slug = t.competition.strip().lower()
        showing = tuple(getattr(getattr(ds, "scope", None), "slugs", ()) or ())
        if rescope is not None:
            try:
                ds = rescope(slug)
            except Exception as exc:  # unknown slug, or genders that cannot mix
                scope_notes.append(
                    f"could not narrow to {slug!r} ({exc}); answered over "
                    f"{', '.join(showing) or 'the default competition'} instead")
        elif slug not in showing:
            scope_notes.append(
                f"the question names {slug!r}, but these results cover "
                f"{', '.join(showing)}")
    filters, notes = _to_filters(t, ds)
    notes = scope_notes + notes
    sort = t.sort if t.sort in player_service.SORT_COLUMNS else "runs"
    if sort != t.sort:
        notes.append(f"cannot sort by {t.sort!r}; used runs instead")

    result = player_service.directory(
        ds, filters,
        role=t.role or None, sort=sort, order=("asc" if t.order == "asc" else "desc"),
        limit=limit,
        min_balls=t.min_balls, min_innings=t.min_innings,
        min_runs=t.min_runs, min_wickets=t.min_wickets,
    )
    result["question"] = question
    result["interpretation"] = t.interpretation
    # The competition that was actually read, not the one the sentence claims.
    # `interpretation` is the model's prose; if a rescope failed, only this
    # tells the reader which deliveries the numbers came from.
    result["scope"] = list(getattr(getattr(ds, "scope", None), "slugs", ()) or ())
    result["unsupported"] = list(t.unsupported) + notes
    return result
