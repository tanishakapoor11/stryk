"""Dashboard aggregates and automatically generated insights."""

from __future__ import annotations

import datetime as dt
from typing import List, Optional

import pandas as pd

from app.analytics import metrics, store
from app.analytics import players as player_service
from app.analytics.constants import PHASE_ORDER, QUALIFICATION
from app.analytics.store import Dataset, Filters


def _team_name(ds: Dataset, tid) -> Optional[str]:
    try:
        return str(ds.teams.at[int(tid), "name"])
    except (KeyError, TypeError, ValueError):
        return None


def _with_names(ds: Dataset, df: pd.DataFrame, limit: int) -> List[dict]:
    rows = metrics.records(df.head(limit), ds)
    for r in rows:
        if r.get("team_id") is not None:
            r["team_name"] = _team_name(ds, r["team_id"])
        if r.get("bowling_team_id") is not None:
            r["opposition"] = _team_name(ds, r["bowling_team_id"])
        if r.get("batting_team_id") is not None:
            r.setdefault("opposition", _team_name(ds, r["batting_team_id"]))
    return rows


def summary(ds: Dataset, f: Filters) -> dict:
    dv = store.apply(ds.deliveries, f)
    matches = ds.matches
    if f.seasons:
        matches = matches[matches["season"].isin(f.seasons)]
    seasons = sorted(matches["season"].unique().tolist())
    return {
        "matches": int(matches["id"].nunique()),
        "deliveries": int(len(dv)),
        "players": int(ds.players.shape[0]),
        "teams": int(ds.teams.shape[0]),
        "seasons": len(seasons),
        "season_range": [seasons[0], seasons[-1]] if seasons else [],
        "venues": int(ds.venues.shape[0]),
        "runs": int(dv["total_runs"].sum()) if not dv.empty else 0,
        "wickets": int(dv["is_wicket"].sum()) if not dv.empty else 0,
        "last_updated": ds.loaded_at.isoformat() + "Z",
        "source": "Cricsheet ball-by-ball IPL data",
    }


def leaderboards(ds: Dataset, f: Filters, limit: int = 10) -> dict:
    dv = store.apply(ds.deliveries, f)
    if dv.empty:
        return {}
    bat = metrics.batting_summary(dv)
    bowl = metrics.bowling_summary(dv)

    sr_min = QUALIFICATION["batting_strike_rate_balls"]
    ec_min = QUALIFICATION["bowling_economy_balls"]
    qualified_bat = bat[bat["balls"] >= sr_min]
    qualified_bowl = bowl[bowl["balls"] >= ec_min]

    inn = metrics.batting_innings(dv).sort_values(["runs", "balls"], ascending=[False, True])
    spells = metrics.bowling_spells(dv).sort_values(["wickets", "runs"], ascending=[False, True])
    spells = spells[spells["wickets"] > 0]

    def innings_rows(df: pd.DataFrame) -> List[dict]:
        df = df.head(limit).merge(
            ds.matches[["id", "season", "date"]].rename(columns={"id": "match_id"}),
            on="match_id", how="left", suffixes=("", "_m"),
        )
        rows = metrics.records(df, ds)
        for r in rows:
            r["opposition"] = _team_name(ds, r.get("bowling_team_id"))
            r["team_name"] = _team_name(ds, r.get("batting_team_id"))
            if isinstance(r.get("date"), pd.Timestamp):
                r["date"] = r["date"].date().isoformat()
        return rows

    def spell_rows(df: pd.DataFrame) -> List[dict]:
        df = df.head(limit).copy()
        df["figures"] = [f"{int(w)}/{int(r)}" for w, r in zip(df["wickets"], df["runs"])]
        df["overs"] = [metrics.overs_string(int(b)) for b in df["balls"]]
        rows = metrics.records(df, ds)
        for r in rows:
            r["opposition"] = _team_name(ds, r.get("batting_team_id"))
            r["team_name"] = _team_name(ds, r.get("bowling_team_id"))
        return rows

    return {
        "most_runs": _with_names(ds, bat.sort_values("runs", ascending=False), limit),
        "most_wickets": _with_names(ds, bowl.sort_values("wickets", ascending=False), limit),
        "highest_scores": innings_rows(inn),
        "best_figures": spell_rows(spells),
        "best_strike_rate": {
            "qualification": f"minimum {sr_min} balls faced",
            "rows": _with_names(
                ds, qualified_bat.sort_values("strike_rate", ascending=False), limit
            ),
        },
        "best_economy": {
            "qualification": f"minimum {ec_min} legal deliveries bowled",
            "rows": _with_names(ds, qualified_bowl.sort_values("economy"), limit),
        },
        "best_average": {
            "qualification": f"minimum {QUALIFICATION['batting_average_innings']} innings and a dismissal",
            "rows": _with_names(
                ds,
                bat[(bat["innings"] >= QUALIFICATION["batting_average_innings"])
                    & bat["average"].notna()].sort_values("average", ascending=False),
                limit,
            ),
        },
    }


def season_trends(ds: Dataset, f: Filters) -> dict:
    dv = store.apply(ds.deliveries, f)
    if dv.empty:
        return {"seasons": [], "phases": [], "teams": []}

    by_season = dv.groupby("season").agg(
        runs=("total_runs", "sum"),
        balls=("is_legal", "sum"),
        wickets=("is_wicket", "sum"),
        sixes=("is_six", "sum"),
        fours=("is_four", "sum"),
        matches=("match_id", "nunique"),
    ).reset_index()
    by_season["run_rate"] = (by_season["runs"] * 6 / by_season["balls"]).round(2)
    by_season["balls_per_wicket"] = (by_season["balls"] / by_season["wickets"]).round(1)
    by_season["boundary_pct"] = (
        (by_season["fours"] + by_season["sixes"]) * 100 / by_season["balls"]
    ).round(2)

    phase = dv.groupby(["season", "phase"]).agg(
        runs=("total_runs", "sum"), balls=("is_legal", "sum"), wickets=("is_wicket", "sum")
    ).reset_index()
    phase["run_rate"] = (phase["runs"] * 6 / phase["balls"]).round(2)
    phase["phase_order"] = phase["phase"].map({p: i for i, p in enumerate(PHASE_ORDER)})
    phase = phase.sort_values(["season", "phase_order"])

    m = ds.matches
    if f.seasons:
        m = m[m["season"].isin(f.seasons)]
    played = pd.concat([
        m[["season", "team1_id"]].rename(columns={"team1_id": "team_id"}),
        m[["season", "team2_id"]].rename(columns={"team2_id": "team_id"}),
    ])
    team_trend = played.groupby(["season", "team_id"]).size().reset_index(name="played")
    wins = m.dropna(subset=["winner_id"]).groupby(["season", "winner_id"]).size()
    team_trend["won"] = [
        int(wins.get((s, t), 0)) for s, t in zip(team_trend["season"], team_trend["team_id"])
    ]
    team_trend["win_pct"] = (team_trend["won"] * 100 / team_trend["played"]).round(1)
    team_trend["team_name"] = team_trend["team_id"].map(ds.teams["name"])

    return {
        "seasons": metrics.records(by_season),
        "phases": metrics.records(phase.drop(columns="phase_order")),
        "teams": metrics.records(team_trend),
    }


def performance_distribution(ds: Dataset, f: Filters) -> dict:
    """Scatter inputs: batting average vs strike rate, economy vs bowling average."""
    dv = store.apply(ds.deliveries, f)
    if dv.empty:
        return {"batting": [], "bowling": []}
    bat = metrics.batting_summary(dv)
    bat = bat[(bat["balls"] >= QUALIFICATION["batting_strike_rate_balls"]) & bat["average"].notna()]
    bowl = metrics.bowling_summary(dv)
    bowl = bowl[(bowl["balls"] >= QUALIFICATION["bowling_economy_balls"]) & bowl["average"].notna()]
    return {
        "batting": metrics.records(
            bat[["player_id", "runs", "balls", "average", "strike_rate", "boundary_pct"]], ds
        ),
        "bowling": metrics.records(
            bowl[["player_id", "wickets", "balls", "average", "economy", "dot_pct"]], ds
        ),
    }


# --------------------------------------------------------------------------
# Insights
# --------------------------------------------------------------------------
def insights(ds: Dataset, f: Filters, count: int = 4) -> List[dict]:
    """Derive statistical observations from the loaded data.

    Each generator returns a fact computed at request time. Nothing here is a
    stored narrative: if the dataset changes, the insight changes with it.
    The daily rotation is a deterministic function of the date so the page is
    stable within a day but not identical every day.
    """
    dv = store.apply(ds.deliveries, f)
    if dv.empty:
        return []
    out: List[dict] = []
    latest = int(dv["season"].max())

    def add(title, detail, metric=None, context=None, link=None):
        out.append({"title": title, "detail": detail, "metric": metric,
                    "context": context, "link": link})

    # 1. Death-overs specialist
    death = dv[dv["phase"] == "death"]
    db = metrics.bowling_summary(death)
    db = db[db["balls"] >= QUALIFICATION["bowling_economy_balls"]]
    if not db.empty:
        r = db.sort_values("economy").iloc[0]
        all_death_er = round(death["bowler_runs"].sum() * 6 / death["is_legal"].sum(), 2)
        add(
            "Death-overs control",
            f"{ds.player_name(r['player_id'])} concedes {r['economy']} runs per over in overs 16-20, "
            f"against a league death-overs rate of {all_death_er}.",
            f"{r['economy']} econ",
            f"{int(r['balls'])} balls bowled at the death, minimum {QUALIFICATION['bowling_economy_balls']}",
            f"/players/{r['player_id']}",
        )

    # 2. Powerplay aggression
    pp = dv[dv["phase"] == "powerplay"]
    pb = metrics.batting_summary(pp)
    pb = pb[pb["balls"] >= QUALIFICATION["batting_strike_rate_balls"]]
    if not pb.empty:
        r = pb.sort_values("strike_rate", ascending=False).iloc[0]
        league = round(pp["batter_runs"].sum() * 100 / pp["is_ball_faced"].sum(), 1)
        add(
            "Powerplay acceleration",
            f"{ds.player_name(r['player_id'])} strikes at {r['strike_rate']} in the first six overs, "
            f"{round(r['strike_rate'] - league, 1)} above the league powerplay rate of {league}.",
            f"{r['strike_rate']} SR",
            f"{int(r['balls'])} powerplay balls faced, minimum {QUALIFICATION['batting_strike_rate_balls']}",
            f"/players/{r['player_id']}",
        )

    # 3. Scoring-rate drift across seasons
    per_season = dv.groupby("season").apply(
        lambda g: g["total_runs"].sum() * 6 / g["is_legal"].sum(), include_groups=False
    )
    if len(per_season) >= 2:
        first, last = per_season.index[0], per_season.index[-1]
        delta = round(per_season.iloc[-1] - per_season.iloc[0], 2)
        direction = "risen" if delta > 0 else "fallen"
        add(
            "Scoring rate over time",
            f"League run rate has {direction} from {round(per_season.iloc[0], 2)} in {first} "
            f"to {round(per_season.iloc[-1], 2)} in {last}.",
            f"{'+' if delta > 0 else ''}{delta} RPO",
            f"All non-super-over deliveries, {first}-{last}",
        )

    # 4. Chasing vs batting first
    chase = dv[dv["is_chase"]]
    first_inns = dv[~dv["is_chase"]]
    if not chase.empty and not first_inns.empty:
        c_rr = round(chase["total_runs"].sum() * 6 / chase["is_legal"].sum(), 2)
        f_rr = round(first_inns["total_runs"].sum() * 6 / first_inns["is_legal"].sum(), 2)
        add(
            "Chasing vs setting",
            f"Teams score at {f_rr} per over batting first and {c_rr} chasing - "
            f"a {abs(round(c_rr - f_rr, 2))} run-per-over difference.",
            f"{f_rr} vs {c_rr}",
            "All innings, super overs excluded",
        )

    # 5. Most improved strike rate, latest season vs career
    recent = dv[dv["season"] == latest]
    rb = metrics.batting_summary(recent)
    rb = rb[rb["balls"] >= QUALIFICATION["season_strike_rate_balls"]]
    cb = metrics.batting_summary(dv[dv["season"] < latest]).set_index("player_id")
    if not rb.empty and not cb.empty:
        joined = rb.set_index("player_id").join(cb[["strike_rate"]], rsuffix="_prior").dropna(
            subset=["strike_rate_prior"]
        )
        joined = joined[joined["strike_rate"].notna()]
        if not joined.empty:
            joined["delta"] = joined["strike_rate"] - joined["strike_rate_prior"]
            r = joined.sort_values("delta", ascending=False).iloc[0]
            add(
                f"Biggest strike-rate jump in {latest}",
                f"{ds.player_name(r.name)} struck at {r['strike_rate']} in {latest} against "
                f"{r['strike_rate_prior']} across previous seasons.",
                f"+{round(r['delta'], 1)} SR",
                f"{int(r['balls'])} balls in {latest}, minimum {QUALIFICATION['season_strike_rate_balls']}",
                f"/players/{r.name}",
            )

    # 6. Dot-ball pressure
    bowl_all = metrics.bowling_summary(dv)
    bowl_all = bowl_all[bowl_all["balls"] >= QUALIFICATION["bowling_economy_balls"] * 2]
    if not bowl_all.empty:
        r = bowl_all.sort_values("dot_pct", ascending=False).iloc[0]
        add(
            "Dot-ball pressure",
            f"{ds.player_name(r['player_id'])} has gone for nothing off {r['dot_pct']}% of deliveries, "
            f"the highest dot-ball share among bowlers with {int(QUALIFICATION['bowling_economy_balls'] * 2)}+ balls.",
            f"{r['dot_pct']}% dots",
            f"{int(r['balls'])} legal deliveries",
            f"/players/{r['player_id']}",
        )

    # Deterministic daily rotation.
    if len(out) <= count:
        return out
    seed = dt.date.today().toordinal()
    return [out[(seed + i) % len(out)] for i in range(count)]


def featured_innings(ds: Dataset, f: Filters) -> Optional[dict]:
    """The highest individual score under the current filters, ball by ball.

    The front page leads on the ball-by-ball sequence because that is what this
    dataset actually is - every other figure in the product is an aggregate of
    it. Showing one real innings in the notation a fan already reads makes the
    source material legible before any statistic is claimed about it.
    """
    dv = store.apply(ds.deliveries, f, team_column="batting_team_id")
    if dv.empty:
        return None
    innings = metrics.batting_innings(dv)
    if innings.empty:
        return None
    top = innings.sort_values("runs", ascending=False).iloc[0]

    faced = dv[dv["batter_id"] == top["player_id"]]
    sequence = player_service.ball_sequences(faced, [int(top["innings_id"])]).get(
        int(top["innings_id"]), []
    )
    if not sequence:
        return None

    match = ds.matches[ds.matches["id"] == top["match_id"]]
    date = None
    if not match.empty and isinstance(match.iloc[0]["date"], pd.Timestamp):
        date = match.iloc[0]["date"].date().isoformat()

    return {
        "player_id": top["player_id"],
        "player_name": ds.player_name(top["player_id"]),
        "runs": int(top["runs"]),
        "balls": int(top["balls"]),
        "fours": int(top["fours"]),
        "sixes": int(top["sixes"]),
        "out": bool(top["out"]),
        "opposition": _team_name(ds, top.get("bowling_team_id")),
        "team_name": _team_name(ds, top.get("batting_team_id")),
        "season": int(top["season"]),
        "date": date,
        "sequence": sequence,
        "strike_rate": metrics.div(int(top["runs"]) * 100, int(top["balls"])),
    }
