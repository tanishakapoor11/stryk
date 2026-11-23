"""Scoring rules and phase definitions - the single source of cricket truth.

Everything here is referenced by both the ingestion pipeline and the analytics
layer so that a rule can never drift between how data is stored and how it is
reported.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

#: Phase boundaries as inclusive 1-based over numbers, per match format.
#: IPL/T20: powerplay 1-6, middle 7-15, death 16-20 (the standard T20 split;
#: the fielding-restriction powerplay is exactly overs 1-6 in T20).
PHASE_DEFINITIONS: Dict[str, List[Tuple[str, int, int]]] = {
    "T20": [("powerplay", 1, 6), ("middle", 7, 15), ("death", 16, 10_000)],
    "ODI": [("powerplay", 1, 10), ("middle", 11, 40), ("death", 41, 10_000)],
}
DEFAULT_PHASES = PHASE_DEFINITIONS["T20"]
PHASE_ORDER = ["powerplay", "middle", "death"]

#: Wicket kinds credited to the bowler's figures. Everything else (run out,
#: retirements, obstructing the field, timed out, handled the ball, hit the
#: ball twice) is a dismissal but not a bowler's wicket.
BOWLER_CREDITED_DISMISSALS = frozenset(
    {"bowled", "caught", "caught and bowled", "lbw", "stumped", "hit wicket"}
)

#: Kinds that end the batter's innings as a dismissal (denominator of the
#: batting average). "retired hurt" / "retired not out" leave the batter not
#: out; "retired out" is a dismissal with no bowler credited.
NOT_OUT_RETIREMENTS = frozenset({"retired hurt", "retired not out"})

#: Extras that are debited to the bowler. Byes, leg-byes and penalty runs are
#: conceded by the fielding side, not the bowler.
BOWLER_DEBITED_EXTRAS = ("wides", "noballs")

#: Minimum samples before a rate statistic is published on a leaderboard.
#: Rates are meaningless on tiny denominators, so every leaderboard that ranks
#: by a rate states its threshold in the API response.
QUALIFICATION = {
    "batting_strike_rate_balls": 500,
    "batting_average_innings": 20,
    "bowling_economy_balls": 500,
    "bowling_average_wickets": 20,
    "season_strike_rate_balls": 150,
    "season_economy_balls": 150,
    "matchup_balls_reliable": 30,
    "matchup_balls_minimum": 12,
}


def phase_for_over(over_zero_based: int, match_type: str = "T20") -> str:
    """Map a Cricsheet 0-based over number onto a phase label.

    Shortened innings are handled by over *number*, not by proportion: in a
    rain-reduced 12-over game overs 1-6 are still the powerplay and the death
    overs are whatever is bowled from over 16 onwards (i.e. none). This keeps
    phase statistics comparable across matches.
    """
    over = over_zero_based + 1
    for label, lo, hi in PHASE_DEFINITIONS.get(match_type, DEFAULT_PHASES):
        if lo <= over <= hi:
            return label
    return "death"


#: Human-readable formulas, served at /api/meta/metrics and surfaced in the UI
#: tooltips. Keeping them next to the implementation keeps them honest.
METRIC_DEFINITIONS = {
    "runs": {
        "label": "Runs",
        "formula": "Sum of runs credited to the batter.",
        "notes": "Excludes byes, leg-byes, wides and penalty runs, which are team extras.",
    },
    "balls_faced": {
        "label": "Balls faced",
        "formula": "Deliveries faced excluding wides.",
        "notes": "No-balls count as balls faced because the batter can score from them.",
    },
    "batting_average": {
        "label": "Batting average",
        "formula": "Runs / dismissals",
        "notes": "Not-outs are excluded from the denominator. Undefined (shown as '-') when the batter has never been dismissed.",
    },
    "strike_rate": {
        "label": "Strike rate",
        "formula": "(Runs / balls faced) x 100",
        "notes": "Balls faced excludes wides.",
    },
    "boundary_percentage": {
        "label": "Boundary %",
        "formula": "(Fours + sixes) / balls faced x 100",
    },
    "dot_percentage": {
        "label": "Dot %",
        "formula": "Deliveries where the batter scored no run / balls faced x 100",
        "notes": "A ball that goes for byes or leg-byes is still a dot for the batter.",
    },
    "overs": {
        "label": "Overs",
        "formula": "Legal deliveries / 6, displayed as overs.balls",
        "notes": "Wides and no-balls do not count towards the over.",
    },
    "runs_conceded": {
        "label": "Runs conceded",
        "formula": "Batter runs + wides + no-balls",
        "notes": "Byes, leg-byes and penalty runs are not debited to the bowler.",
    },
    "wickets": {
        "label": "Wickets",
        "formula": "Dismissals credited to the bowler",
        "notes": "Bowled, caught, caught and bowled, lbw, stumped, hit wicket. Run-outs, retirements and obstructing the field are excluded.",
    },
    "economy": {
        "label": "Economy",
        "formula": "Runs conceded / overs bowled",
    },
    "bowling_average": {
        "label": "Bowling average",
        "formula": "Runs conceded / wickets",
        "notes": "Undefined when the bowler has no wickets.",
    },
    "bowling_strike_rate": {
        "label": "Bowling strike rate",
        "formula": "Legal deliveries bowled / wickets",
    },
    "phase": {
        "label": "Phase",
        "formula": "Powerplay = overs 1-6, middle = overs 7-15, death = overs 16-20",
        "notes": "Assigned by over number, so rain-shortened innings stay comparable.",
    },
}
