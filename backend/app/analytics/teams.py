"""Team and squad intelligence."""

from __future__ import annotations

from typing import List, Optional

import pandas as pd

from app.analytics import metrics, players, store
from app.analytics.constants import PHASE_ORDER
from app.analytics.store import Dataset, Filters

#: Cricsheet match files carry no player nationality, so overseas quotas
#: cannot be computed from this dataset without importing an external roster.
OVERSEAS_DATA_AVAILABLE = False


def _flag(ds: Dataset, team_id: int) -> Optional[str]:
    """The team's national flag, or None for a club side and the composite XIs.

    Franchise crests are trademarks and are not reproduced, so a club side has
    no mark here and the interface draws its own badge. A national side is a
    nation, and a flag is neither owned artwork nor a guess.
    """
    countries = ds.registry.get("countries")
    if countries is None or countries.empty:
        return None
    cid = ds.teams.at[team_id, "country_id"]
    if pd.isna(cid):
        return None
    row = countries[countries["id"] == int(cid)]
    if row.empty:
        return None
    flag = row.iloc[0]["flag"]
    return None if pd.isna(flag) else str(flag)


def list_teams(ds: Dataset) -> List[dict]:
    m = ds.matches
    played = pd.concat([
        m[["id", "season", "team1_id"]].rename(columns={"team1_id": "team_id"}),
        m[["id", "season", "team2_id"]].rename(columns={"team2_id": "team_id"}),
    ])
    agg = played.groupby("team_id").agg(
        matches=("id", "nunique"), first_season=("season", "min"), last_season=("season", "max")
    )
    wins = m.dropna(subset=["winner_id"]).groupby("winner_id").size()
    rows = []
    for tid, r in agg.iterrows():
        won = int(wins.get(tid, 0))
        rows.append({
            "id": int(tid),
            "name": ds.teams.at[tid, "name"],
            "short_name": ds.teams.at[tid, "short_name"],
            "flag": _flag(ds, tid),
            "aliases": ds.teams.at[tid, "aliases"],
            "matches": int(r["matches"]),
            "won": won,
            "win_pct": metrics.div(won * 100, int(r["matches"])),
            "first_season": int(r["first_season"]),
            "last_season": int(r["last_season"]),
            "active": int(r["last_season"]) == int(m["season"].max()),
        })
    return sorted(rows, key=lambda r: (-r["last_season"], -r["matches"]))


def _record(ds: Dataset, team_id: int, seasons: Optional[List[int]]) -> dict:
    m = ds.matches
    if seasons:
        m = m[m["season"].isin(seasons)]
    played = m[(m["team1_id"] == team_id) | (m["team2_id"] == team_id)]
    won = int((played["winner_id"] == team_id).sum())
    no_result = int(played["result"].isin(["no result", "abandoned"]).sum())
    return {
        "played": int(len(played)),
        "won": won,
        "lost": int(len(played)) - won - no_result,
        "no_result": no_result,
        "win_pct": metrics.div(won * 100, int(len(played)) - no_result),
    }


def squad(ds: Dataset, team_id: int, seasons: Optional[List[int]]) -> dict:
    sq = ds.squads[ds.squads["team_id"] == team_id]
    if seasons:
        sq = sq[sq["season"].isin(seasons)]
    if sq.empty:
        return {"players": [], "role_distribution": {}}

    f = Filters(seasons=seasons, team_ids=[team_id])
    bat_dv = store.apply(ds.deliveries, f, team_column="batting_team_id")
    bowl_dv = store.apply(ds.deliveries, f, team_column="bowling_team_id")
    bat = metrics.batting_summary(bat_dv).set_index("player_id")
    bowl = metrics.bowling_summary(bowl_dv).set_index("player_id")
    roles = players.infer_roles(ds)

    pos = ds.positions.merge(
        bat_dv[["innings_id"]].drop_duplicates(), on="innings_id", how="inner"
    )
    avg_pos = pos.groupby("player_id")["position"].mean().round(1)

    rows = []
    for pid, grp in sq.groupby("player_id"):
        rows.append({
            "player_id": pid,
            "name": ds.player_name(pid),
            "matches": int(grp["match_id"].nunique()),
            "seasons": sorted(int(s) for s in grp["season"].unique()),
            "role": roles.at[pid, "role"] if pid in roles.index else None,
            "batting_position": metrics.div(avg_pos.get(pid, float("nan")), 1)
            if pid in avg_pos.index else None,
            "runs": int(bat.at[pid, "runs"]) if pid in bat.index else 0,
            "balls": int(bat.at[pid, "balls"]) if pid in bat.index else 0,
            "batting_average": bat.at[pid, "average"] if pid in bat.index else None,
            "strike_rate": bat.at[pid, "strike_rate"] if pid in bat.index else None,
            "wickets": int(bowl.at[pid, "wickets"]) if pid in bowl.index else 0,
            "overs": bowl.at[pid, "overs"] if pid in bowl.index else "0.0",
            "economy": bowl.at[pid, "economy"] if pid in bowl.index else None,
        })
    rows.sort(key=lambda r: (-r["matches"], -r["runs"]))
    dist: dict = {}
    for r in rows:
        dist[r["role"] or "Unknown"] = dist.get(r["role"] or "Unknown", 0) + 1
    return {"players": metrics.records(pd.DataFrame(rows)), "role_distribution": dist}


def batting_depth(ds: Dataset, team_id: int, seasons: Optional[List[int]]) -> List[dict]:
    """Runs and scoring rate by batting position - how deep the batting goes."""
    f = Filters(seasons=seasons, team_ids=[team_id])
    dv = store.apply(ds.deliveries, f, team_column="batting_team_id")
    if dv.empty:
        return []
    card = metrics.batting_innings(dv)
    card = card.merge(ds.positions, on=["innings_id", "player_id"], how="left")
    g = card.groupby("position").agg(
        innings=("innings_id", "count"), runs=("runs", "sum"), balls=("balls", "sum"),
        outs=("out", "sum"),
    ).reset_index()
    g = g[g["position"] <= 11]
    g["strike_rate"] = [metrics.div(r * 100, b) for r, b in zip(g["runs"], g["balls"])]
    g["average"] = [metrics.div(r, o) for r, o in zip(g["runs"], g["outs"])]
    g["runs_per_innings"] = [metrics.div(r, i) for r, i in zip(g["runs"], g["innings"])]
    g["position"] = g["position"].astype(int)
    return metrics.records(g)


def phase_profile(ds: Dataset, team_id: int, seasons: Optional[List[int]]) -> dict:
    """Batting and bowling rates by phase, each shown against the league."""
    f = Filters(seasons=seasons)
    all_dv = store.apply(ds.deliveries, f)
    out: dict = {"batting": [], "bowling": []}
    for side, col in (("batting", "batting_team_id"), ("bowling", "bowling_team_id")):
        team_dv = all_dv[all_dv[col] == team_id]
        for phase in PHASE_ORDER:
            t = team_dv[team_dv["phase"] == phase]
            lg = all_dv[all_dv["phase"] == phase]
            if t.empty or lg.empty:
                continue
            out[side].append({
                "phase": phase,
                "runs": int(t["total_runs"].sum()),
                "balls": int(t["is_legal"].sum()),
                "wickets": int(t["is_wicket"].sum()),
                "run_rate": metrics.div(int(t["total_runs"].sum()) * 6, int(t["is_legal"].sum())),
                "league_run_rate": metrics.div(int(lg["total_runs"].sum()) * 6, int(lg["is_legal"].sum())),
                "balls_per_wicket": metrics.div(int(t["is_legal"].sum()), int(t["is_wicket"].sum())),
            })
    return out


def profile(ds: Dataset, team_id: int, f: Filters) -> Optional[dict]:
    if team_id not in ds.teams.index:
        return None
    seasons = f.seasons
    m = ds.matches
    if seasons:
        m = m[m["season"].isin(seasons)]
    played = m[(m["team1_id"] == team_id) | (m["team2_id"] == team_id)]

    by_season = []
    for season, grp in played.groupby("season"):
        won = int((grp["winner_id"] == team_id).sum())
        by_season.append({
            "season": int(season), "played": int(len(grp)), "won": won,
            "lost": int(len(grp)) - won,
            "win_pct": metrics.div(won * 100, int(len(grp))),
        })

    dv = store.apply(ds.deliveries, Filters(seasons=seasons))
    bat = dv[dv["batting_team_id"] == team_id]
    chase = {
        key: {
            "innings": int(sub["innings_id"].nunique()),
            "runs": int(sub["total_runs"].sum()),
            "balls": int(sub["is_legal"].sum()),
            "run_rate": metrics.div(int(sub["total_runs"].sum()) * 6, int(sub["is_legal"].sum())),
            "wickets_lost": int(sub["is_wicket"].sum()),
        }
        for key, sub in (("chasing", bat[bat["is_chase"]]), ("setting", bat[~bat["is_chase"]]))
    }
    chase_matches = played[played["result"] == "normal"]
    chase_wins = 0
    set_wins = 0
    for _, r in chase_matches.iterrows():
        if r["winner_id"] != team_id:
            continue
        if r["result_type"] == "wickets":
            chase_wins += 1
        elif r["result_type"] == "runs":
            set_wins += 1
    chase["chasing"]["wins"] = chase_wins
    chase["setting"]["wins"] = set_wins

    return {
        "team": {
            "id": team_id,
            "name": ds.teams.at[team_id, "name"],
            "short_name": ds.teams.at[team_id, "short_name"],
            "flag": _flag(ds, team_id),
            "aliases": ds.teams.at[team_id, "aliases"],
        },
        "filters": f.describe(),
        "record": _record(ds, team_id, seasons),
        "by_season": by_season,
        "squad": squad(ds, team_id, seasons),
        "batting_depth": batting_depth(ds, team_id, seasons),
        "phase_profile": phase_profile(ds, team_id, seasons),
        "innings_type": chase,
        "data_notes": {
            "overseas_data_available": OVERSEAS_DATA_AVAILABLE,
            "overseas_note": (
                "Player nationality is not present in Cricsheet ball-by-ball files, so "
                "overseas-quota composition is not shown. It would need an external roster."
            ),
            "batting_position_note": (
                "Batting position is reconstructed from the order players arrive at the crease."
            ),
        },
    }
