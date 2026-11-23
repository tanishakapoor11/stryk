"""Points tables from results, under a competition's own rules.

Nothing here knows about the IPL. Points per result, how a tie is settled,
the tie-break sequence and the stage that counts all come from the
competition's points system (app/catalog/points_systems.json). A competition
without one gets no table, rather than a table computed under borrowed rules.

Net run rate follows the standard limited-overs convention:

* A side bowled out is charged its full quota of overs, not the overs it lasted.
* In a chase the quota is the (possibly revised) target overs.
* The side batting first is credited with ``target - 1`` runs off the target
  overs. For an uninterrupted match that is exactly its score off its full
  quota; for a rain-revised match it is the par score the method set, which is
  how revised matches enter net run rate.
* Super overs, and matches with no result, do not count towards net run rate.

Completeness is reported, not assumed. A source that omits matches abandoned
without a ball (Cricsheet does) leaves those points out; when teams have
played different numbers of counted matches the table says so.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from app.analytics import metrics
from app.analytics.store import Dataset

ROUND_NRR = 3


def balls_from_overs(overs: Optional[float], balls_per_over: int = 6) -> Optional[int]:
    """Cricket overs notation (19.4 = 19 overs and 4 balls) to balls."""
    if overs is None or pd.isna(overs):
        return None
    whole = int(overs)
    part = int(round((float(overs) - whole) * 10))
    return whole * balls_per_over + part


def _innings_totals(ds: Dataset, match_ids) -> pd.DataFrame:
    """Runs, legal balls and dismissals per (match, innings), super overs excluded."""
    dv = ds.deliveries
    dv = dv[dv["match_id"].isin(match_ids) & ~dv["is_super_over"]]
    if dv.empty:
        return pd.DataFrame(columns=["match_id", "innings_number", "runs", "balls", "wickets",
                                     "batting_team_id", "bowling_team_id"])
    out = dv.assign(_out=dv["out_player_id"].notna()).groupby(
        ["match_id", "innings_number", "batting_team_id", "bowling_team_id"], as_index=False
    ).agg(runs=("total_runs", "sum"), balls=("is_legal", "sum"), wickets=("_out", "sum"))
    inn = ds.innings
    if not inn.empty:
        inn = inn[~inn["is_super_over"].astype(bool)][
            ["match_id", "innings_number", "target_runs", "target_overs"]
        ]
        out = out.merge(inn, on=["match_id", "innings_number"], how="left")
    else:
        out["target_runs"] = None
        out["target_overs"] = None
    return out


def _nrr_contributions(match: pd.Series, totals: pd.DataFrame) -> List[dict]:
    """Per-team (runs for, balls for) in one match, or [] if it does not count."""
    inns = totals[totals["match_id"] == match["id"]].sort_values("innings_number")
    if len(inns) < 2:
        return []
    first, second = inns.iloc[0], inns.iloc[1]
    bpo = int(match.get("balls_per_over") or 6)
    quota = int(match["overs_limit"]) * bpo if pd.notna(match.get("overs_limit")) else None
    target_balls = balls_from_overs(second.get("target_overs"), bpo) or quota
    if target_balls is None:
        return []
    wickets_for_all_out = 10

    if pd.notna(second.get("target_runs")):
        first_runs = int(second["target_runs"]) - 1
    else:
        first_runs = int(first["runs"])
    first_balls = target_balls

    second_runs = int(second["runs"])
    second_balls = target_balls if int(second["wickets"]) >= wickets_for_all_out else int(second["balls"])
    second_balls = min(second_balls, target_balls) if second_balls else target_balls
    return [
        {"team_id": int(first["batting_team_id"]), "runs_for": first_runs, "balls_for": first_balls,
         "runs_against": second_runs, "balls_against": second_balls},
        {"team_id": int(second["batting_team_id"]), "runs_for": second_runs, "balls_for": second_balls,
         "runs_against": first_runs, "balls_against": first_balls},
    ]


def _result_points(match: pd.Series, rules: dict) -> Dict[int, dict]:
    """Points and W/L/T/NR tallies for both sides of one match."""
    pts = rules["points"]
    t1, t2 = int(match["team1_id"]), int(match["team2_id"])
    blank = lambda: {"won": 0, "lost": 0, "tied": 0, "no_result": 0, "drawn": 0, "points": 0}
    out = {t1: blank(), t2: blank()}
    result = match.get("result")
    winner = match.get("winner_id")

    if result == "no result" or match.get("status") in ("no_result", "abandoned"):
        for t in out:
            out[t]["no_result"] = 1
            out[t]["points"] = pts["no_result"]
        return out
    if result == "draw":
        if pts.get("draw") is None:
            raise ValueError("points system has no value for a draw")
        for t in out:
            out[t]["drawn"] = 1
            out[t]["points"] = pts["draw"]
        return out
    if result == "tie" and not (rules["tie_resolution"] == "super_over" and pd.notna(winner)):
        for t in out:
            out[t]["tied"] = 1
            out[t]["points"] = pts["tie"]
        return out
    if pd.isna(winner):
        return {}
    w = int(winner)
    loser = t2 if w == t1 else t1
    out[w].update(won=1, points=pts["win"])
    out[loser].update(lost=1, points=pts["loss"])
    return out


def compute(ds: Dataset, season_id: int, rules: Optional[dict]) -> dict:
    """The standings for one season, one table per group."""
    if not rules:
        return {"available": False,
                "reason": "No points system is configured for this competition, so no table is shown."}
    stages = ds.stages
    season_stages = stages[stages["season_id"] == season_id] if not stages.empty else stages
    counted = season_stages[season_stages["stage_type"] == rules.get("standings_stage_type", "league")]
    m = ds.matches
    m = m[(m["season_id"] == season_id) & m["stage_id"].isin(counted.index)]
    if m.empty:
        return {"available": False,
                "reason": "No matches from the stage this competition's table is built from."}

    knockout_ids = season_stages.index[season_stages["stage_type"] == "knockout"]
    ko = ds.matches[(ds.matches["season_id"] == season_id) & ds.matches["stage_id"].isin(knockout_ids)]
    knockout_teams = set(ko["team1_id"]).union(ko["team2_id"])

    totals = _innings_totals(ds, set(m["id"]))
    bowling = totals.groupby("bowling_team_id").agg(w=("wickets", "sum"), b=("balls", "sum"))

    groups = []
    for group_id, gm in m.groupby(pd.to_numeric(m["group_id"], errors="coerce").fillna(-1).astype(int)):
        table: Dict[int, dict] = {}
        for _, match in gm.iterrows():
            for team, r in _result_points(match, rules).items():
                row = table.setdefault(team, {"team_id": team, "played": 0, "won": 0, "lost": 0,
                                              "tied": 0, "drawn": 0, "no_result": 0, "points": 0,
                                              "runs_for": 0, "balls_for": 0,
                                              "runs_against": 0, "balls_against": 0})
                row["played"] += 1
                for k in ("won", "lost", "tied", "drawn", "no_result", "points"):
                    row[k] += r[k]
            if match.get("result") == "no result":
                continue
            for c in _nrr_contributions(match, totals):
                row = table[c["team_id"]]
                for k in ("runs_for", "balls_for", "runs_against", "balls_against"):
                    row[k] += c[k]

        rows = []
        for row in table.values():
            rf, bf, ra, ba = row["runs_for"], row["balls_for"], row["runs_against"], row["balls_against"]
            nrr = (rf * 6 / bf - ra * 6 / ba) if bf and ba else None
            tid = row["team_id"]
            wpb = None
            if tid in bowling.index and bowling.at[tid, "b"]:
                wpb = float(bowling.at[tid, "w"]) / float(bowling.at[tid, "b"])
            rows.append({
                **row,
                "net_run_rate": round(nrr, ROUND_NRR) if nrr is not None else None,
                "_nrr": nrr if nrr is not None else float("-inf"),
                "_wpb": wpb if wpb is not None else float("-inf"),
                "overs_for": metrics.overs_string(bf) if bf else None,
                "overs_against": metrics.overs_string(ba) if ba else None,
                "name": str(ds.teams.at[tid, "name"]) if tid in ds.teams.index else str(tid),
                "short_name": ds.teams.at[tid, "short_name"] if tid in ds.teams.index else None,
                "reached_knockouts": tid in knockout_teams,
            })

        keys = {"points": "points", "wins": "won", "net_run_rate": "_nrr", "wickets_per_ball": "_wpb"}
        order = [keys[k] for k in rules["tie_breakers"]]
        rows.sort(key=lambda r: tuple(-r[k] for k in order) + (r["name"],))
        for pos, r in enumerate(rows, start=1):
            r["position"] = pos
            r.pop("_nrr"), r.pop("_wpb")

        played = sorted({r["played"] for r in rows})
        group_name = _group_name(int(group_id)) if group_id != -1 else None
        groups.append({"group": group_name, "rows": rows, "played_counts": played})

    warnings = []
    uneven = [g for g in groups if len(g["played_counts"]) > 1]
    if uneven:
        warnings.append(
            "Teams have played different numbers of counted matches "
            f"({', '.join(str(p) for p in uneven[0]['played_counts'])}). The source omits matches "
            "abandoned without a ball being bowled, so points from those matches are missing "
            "and this table may differ from the official one. Net run rate is unaffected."
        )
    return {
        "available": True,
        "complete": not uneven,
        "warnings": warnings,
        "matches_counted": int(len(m)),
        "points_system": {k: rules.get(k) for k in
                          ("slug", "name", "points", "tie_resolution", "tie_breakers",
                           "qualifiers", "sources", "verified_on", "notes")},
        "groups": groups,
    }


def _group_name(group_id: int) -> Optional[str]:
    # Groups are few; they are read on demand rather than cached in the store.
    from sqlalchemy import select

    from app.core.db import engine
    from app.models import TournamentGroup

    with engine.connect() as conn:
        return conn.execute(select(TournamentGroup.name).where(TournamentGroup.id == group_id)).scalar()
