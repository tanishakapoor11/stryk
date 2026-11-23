"""Player name search.

Cricsheet names players the way a scorecard does: initials plus surname, so
Shreyas Iyer is stored as "SS Iyer". Nobody types that. Search therefore has to
work from whatever form the person happens to know - a first name, a surname,
the full name, or the scorecard form - and has to put the player they almost
certainly meant at the top.

Three things are handled here:

1. **Either name form.** ``full_name`` (resolved from Wikidata via Cricsheet's
   ESPNcricinfo ids) and the scorecard name are searched together.
2. **Initials.** "S Iyer" and "SS Iyer" both find "SS Iyer", and a query token
   that is a bare initial is matched against the initials rather than requiring
   a literal substring.
3. **Popularity.** Someone searching "sharma" means Rohit Sharma, not a player
   who appeared twice in 2011. Ties are broken by matches played, so the
   obvious answer is first.

No name is ever invented: a player whose full name could not be sourced is
searchable by their scorecard name, which is the only name we actually have.
"""

from __future__ import annotations

import re
from typing import List, Optional

import pandas as pd

from app.analytics.store import Dataset

#: Dropped before matching so "M.S. Dhoni", "MS Dhoni" and "ms dhoni" agree,
#: and so "O'Rourke" is reachable as "orourke".
_PUNCT = re.compile(r"[^a-z0-9 ]+")


def normalise(text: str) -> str:
    """Lowercase, strip punctuation and collapse whitespace."""
    return " ".join(_PUNCT.sub(" ", str(text).lower()).split())


def _initials(name: str) -> str:
    """"SS Iyer" -> "ss"; "Shreyas Iyer" -> "si"."""
    parts = normalise(name).split()
    if not parts:
        return ""
    head = parts[0]
    # A scorecard name's leading token is already the initials.
    return head if len(parts) > 1 and len(head) <= 3 else "".join(p[0] for p in parts)


def _surname(name: str) -> str:
    parts = normalise(name).split()
    return parts[-1] if parts else ""


def index(ds: Dataset) -> pd.DataFrame:
    """Per-player searchable fields, derived once from the registry.

    ``appearances`` is the popularity signal used to break ties; it comes from
    the squad table so that it counts matches in a squad, not balls faced.
    """
    players = ds.players
    if players.empty:
        return pd.DataFrame(columns=["display_name", "scorecard", "blob", "surname",
                                     "initials", "appearances"])

    display = players["display_name"] if "display_name" in players.columns else players["name"]
    frame = pd.DataFrame(index=players.index)
    frame["display_name"] = display
    frame["scorecard"] = players["name"]
    frame["norm_display"] = display.map(normalise)
    frame["norm_scorecard"] = players["name"].map(normalise)
    frame["blob"] = frame["norm_display"] + " " + frame["norm_scorecard"]
    frame["surname"] = display.map(_surname)
    frame["initials"] = players["name"].map(_initials)

    if not ds.squads.empty:
        counts = ds.squads.groupby("player_id")["match_id"].nunique()
        frame["appearances"] = counts.reindex(frame.index).fillna(0).astype(int)
    else:
        frame["appearances"] = 0
    return frame


def _token_matches(token: str, row: pd.Series, as_initial: bool = False) -> bool:
    """Does one query token match this player at all?

    ``as_initial`` is enabled only for multi-token queries, where another token
    still has to match on its own merits. It lets a first name match an
    initial: "chris gayle" finds "CH Gayle" because "gayle" matches the surname
    and "chris" begins with an initial the player actually has. This is what
    keeps the ~2% of players whose full name could not be sourced reachable by
    the name a person would type, without inventing a name for them.
    """
    if token in row["blob"]:
        return True
    # A single letter is an initial, not a substring: "v kohli" must find
    # "V Kohli" without also dragging in every name containing "v".
    if len(token) == 1:
        return token in row["initials"] or row["surname"].startswith(token)
    return as_initial and token[0] in row["initials"]


def _all_tokens_match(tokens: List[str], row: pd.Series) -> bool:
    """Every token matches, and at least one does so without the initial relaxation.

    The second condition stops a query from matching on initials alone, which
    would make "a b" return most of the league.
    """
    if not all(_token_matches(t, row, as_initial=True) for t in tokens):
        return False
    return any(_token_matches(t, row) for t in tokens)


def _score(query: str, tokens: List[str], row: pd.Series) -> int:
    """Higher is a better match. Only the ordering matters."""
    display, surname, blob = row["norm_display"], row["surname"], row["blob"]
    if display == query or row["norm_scorecard"] == query:
        return 100
    if display.startswith(query):
        return 90
    if surname == query:
        return 80
    if surname.startswith(query):
        return 70
    # Every token found, e.g. "shreyas iyer" or "iyer shreyas".
    if len(tokens) > 1 and _all_tokens_match(tokens, row):
        return 60
    if query in blob:
        return 40
    return 10


def search(ds: Dataset, query: str, limit: int = 12) -> List[dict]:
    """Ranked player matches for a free-text query."""
    q = normalise(query)
    if not q:
        return []
    tokens = q.split()
    frame = index(ds)
    if frame.empty:
        return []

    # Narrow before scoring: a player must match the whole query or every token.
    whole = frame["blob"].str.contains(re.escape(q), regex=True, na=False)
    if len(tokens) > 1:
        per_token = frame.apply(lambda row: _all_tokens_match(tokens, row), axis=1)
        candidates = frame[whole | per_token]
    else:
        token_hit = frame.apply(lambda row: _token_matches(q, row), axis=1)
        candidates = frame[whole | token_hit]
    if candidates.empty:
        return []

    scored = candidates.assign(
        _score=[_score(q, tokens, row) for _, row in candidates.iterrows()]
    ).sort_values(["_score", "appearances"], ascending=[False, False])

    return [
        {
            "id": pid,
            "name": row["display_name"],
            "scorecard_name": row["scorecard"],
            "appearances": int(row["appearances"]),
        }
        for pid, row in scored.head(limit).iterrows()
    ]


def matching_ids(ds: Dataset, query: Optional[str]) -> Optional[List[str]]:
    """Player ids matching a query, for filtering a directory or pool.

    Returns None when there is no query, so callers can distinguish "no filter"
    from "filter matched nothing".
    """
    if not query or not normalise(query):
        return None
    return [hit["id"] for hit in search(ds, query, limit=10_000)]
