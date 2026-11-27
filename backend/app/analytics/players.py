"""Player discovery and profile assembly."""

from __future__ import annotations

from typing import List, Optional

import pandas as pd

from app.analytics import metrics, names, store
from app.analytics.constants import METRIC_DEFINITIONS, PHASE_ORDER, QUALIFICATION
from app.analytics.store import Dataset, Filters

#: Cricsheet match files carry no batting-hand or bowling-style metadata, so
#: Stryk does not publish "vs left-arm pace" style splits for IPL: inventing
#: them from names or from a partial register would be worse than omitting
#: them. Match-ups against named bowlers are offered instead.
BOWLING_STYLE_DATA_AVAILABLE = False


def infer_roles(ds: Dataset) -> pd.DataFrame:
    """Derive a playing role from workload. This is an analytical label, not
    an official designation, and the thresholds are published with it."""
    d = ds.deliveries[~ds.deliveries["is_super_over"]]
    faced = d.groupby("batter_id")["is_ball_faced"].sum()
    bowled = d.groupby("bowler_id")["is_legal"].sum()
    idx = ds.players.index
    df = pd.DataFrame(
        {"balls_faced": faced.reindex(idx).fillna(0), "balls_bowled": bowled.reindex(idx).fillna(0)}
    )
    df["role"] = [
        "All-rounder" if (bf >= 300 and bb >= 300)
        else "Bowler" if bb > bf
        else "Batter"
        for bf, bb in zip(df["balls_faced"], df["balls_bowled"])
    ]
    df["role_basis"] = (
        "All-rounder = 300+ balls faced and 300+ balls bowled; "
        "Bowler = more balls bowled than faced; otherwise Batter."
    )
    return df


def _team_history(ds: Dataset, pid: str) -> List[dict]:
    sq = ds.squads[ds.squads["player_id"] == pid]
    if sq.empty:
        return []
    g = sq.groupby("team_id").agg(matches=("match_id", "nunique"),
                                  first_season=("season", "min"),
                                  last_season=("season", "max")).reset_index()
    g["team_name"] = g["team_id"].map(ds.teams["name"])
    return metrics.records(g.sort_values("last_season", ascending=False))


def ball_sequences(faced: pd.DataFrame, innings_ids: List[int]) -> dict:
    """The outcome of every ball a batter faced, per innings, in order.

    Returned as the notation a cricket fan already reads off a live scorecard:
    "." for a dot, the runs off the bat as a digit, "W" for a dismissal, and
    "+" for a ball that produced extras but nothing off the bat. This is the
    one visual in cricket that needs no explanation to anyone who follows the
    game, which is why it is worth carrying through the API.
    """
    if faced.empty or not innings_ids:
        return {}
    # Only balls the batter actually faced, so the strip length always equals
    # the "balls" figure printed next to it. A wide is bowled at the batter but
    # is not a ball faced, and a strip that silently disagreed with its own
    # scorecard line would undermine both.
    sub = faced[faced["innings_id"].isin(innings_ids) & faced["is_ball_faced"]]
    if sub.empty:
        return {}
    sub = sub.sort_values(["innings_id", "over", "ball_in_over"])
    out: dict = {}
    for innings_id, grp in sub.groupby("innings_id", sort=False):
        marks = []
        for row in grp.itertuples():
            if getattr(row, "is_wicket", False) and row.out_player_id == row.batter_id:
                marks.append("W")
            elif row.batter_runs:
                marks.append(str(int(row.batter_runs)))
            elif row.extra_runs:
                marks.append("+")
            else:
                marks.append(".")
        out[int(innings_id)] = marks
    return out


def highlights(bat: Optional[dict], bowl: Optional[dict],
               bat_phases: List[dict], bowl_phases: List[dict]) -> List[dict]:
    """Plain-language reads on a player, each backed by its own figure.

    These exist so that someone who does not read statistics for a living gets
    a sentence before they get a table. Every one is derived from this player's
    own splits - nothing is compared against a league average here, and nothing
    is asserted that the numbers on the same page do not show.
    """
    reads: List[dict] = []
    phase_label = {"powerplay": "the powerplay", "middle": "the middle overs",
                   "death": "the death overs"}

    if bat and (bat.get("balls") or 0) >= 120:
        sr, avg = bat.get("strike_rate"), bat.get("average")
        if sr is not None:
            if sr >= 145:
                reads.append({"text": "Scores quickly", "figure": f"{sr:.1f} strike rate",
                              "tone": "good"})
            elif sr < 120:
                reads.append({"text": "Takes time to get going",
                              "figure": f"{sr:.1f} strike rate", "tone": "watch"})
        if avg is not None and avg >= 35:
            reads.append({"text": "Hard to dismiss", "figure": f"averages {avg:.1f}",
                          "tone": "good"})
        boundary_runs = bat.get("boundary_run_pct")
        if boundary_runs is not None and boundary_runs >= 60:
            reads.append({"text": "Relies on boundaries",
                          "figure": f"{boundary_runs:.0f}% of runs in fours and sixes",
                          "tone": "watch"})
        dot = bat.get("dot_pct")
        if dot is not None and dot <= 30:
            reads.append({"text": "Keeps the strike ticking over",
                          "figure": f"only {dot:.0f}% dot balls", "tone": "good"})

        # The phase a batter is most dangerous in, by their own standards.
        scored = [p for p in bat_phases if (p.get("balls") or 0) >= 60
                  and p.get("strike_rate") is not None]
        if len(scored) > 1:
            best = max(scored, key=lambda p: p["strike_rate"])
            reads.append({
                "text": f"Most dangerous in {phase_label.get(best['phase'], best['phase'])}",
                "figure": f"{best['strike_rate']:.1f} strike rate there", "tone": "good",
            })

    if bowl and (bowl.get("balls") or 0) >= 120:
        econ, swr = bowl.get("economy"), bowl.get("strike_rate")
        if econ is not None and econ <= 7.5:
            reads.append({"text": "Hard to get away", "figure": f"{econ:.2f} economy",
                          "tone": "good"})
        if swr is not None and swr <= 18:
            reads.append({"text": "Takes wickets often",
                          "figure": f"a wicket every {swr:.1f} balls", "tone": "good"})
        bowled = [p for p in bowl_phases if (p.get("balls") or 0) >= 60
                  and p.get("economy") is not None]
        if len(bowled) > 1:
            cheapest = min(bowled, key=lambda p: p["economy"])
            reads.append({
                "text": f"Most economical in {phase_label.get(cheapest['phase'], cheapest['phase'])}",
                "figure": f"{cheapest['economy']:.2f} an over there", "tone": "good",
            })

    return reads[:5]


def scoring_shape(faced: pd.DataFrame) -> Optional[dict]:
    """How a batter's runs are actually made, ball by ball.

    A strike rate hides the mechanism: two batters at 140 can get there by
    clearing the rope every fourth ball or by never missing a single. This
    splits the balls faced into what each one produced, and how many runs came
    from each kind of ball, which is the difference between the two.
    """
    # Only balls actually faced, so the total reconciles with the "balls"
    # figure on the same page. A wide is bowled at the batter but not faced.
    faced = faced[faced["is_ball_faced"]]
    if faced.empty:
        return None
    counts = faced["batter_runs"].value_counts()
    total_balls = int(len(faced))
    buckets = []
    labels = {0: "Dot", 1: "Single", 2: "Two", 3: "Three", 4: "Four", 6: "Six"}
    for value in (0, 1, 2, 3, 4, 6):
        balls = int(counts.get(value, 0))
        if not balls:
            continue
        buckets.append({
            "runs_per_ball": value,
            "label": labels[value],
            "balls": balls,
            "runs": balls * value,
            "ball_share": round(balls * 100 / total_balls, 1),
        })
    # Odd values (5s, all-run) are real but rare; fold them in rather than drop.
    other = total_balls - sum(b["balls"] for b in buckets)
    if other > 0:
        other_runs = int(faced["batter_runs"].sum()) - sum(b["runs"] for b in buckets)
        buckets.append({
            "runs_per_ball": None, "label": "Other", "balls": other,
            "runs": other_runs, "ball_share": round(other * 100 / total_balls, 1),
        })
    total_runs = sum(b["runs"] for b in buckets)
    for b in buckets:
        b["run_share"] = round(b["runs"] * 100 / total_runs, 1) if total_runs else 0.0
    return {"balls": total_balls, "runs": total_runs, "buckets": buckets}


def by_over(faced: pd.DataFrame, bowled: pd.DataFrame) -> List[dict]:
    """Per-over-number profile across the innings, overs 1 to 20.

    Phases answer "is this a death-overs player"; this answers "which over".
    Overs with too few balls to carry a rate return null for it rather than a
    number built on three deliveries.
    """
    faced = faced[faced["is_ball_faced"]]
    rows = []
    for over_index in range(20):
        bat = faced[faced["over"] == over_index]
        bowl = bowled[bowled["over"] == over_index]
        bat_balls = int(len(bat))
        bowl_balls = int(bowl["is_legal"].sum()) if not bowl.empty else 0
        rows.append({
            "over": over_index + 1,
            "balls_faced": bat_balls,
            "runs": int(bat["batter_runs"].sum()) if bat_balls else 0,
            "strike_rate": (round(bat["batter_runs"].sum() * 100 / bat_balls, 1)
                            if bat_balls >= 20 else None),
            "dismissals": int(bat["is_wicket"].sum()) if bat_balls else 0,
            "balls_bowled": bowl_balls,
            "runs_conceded": int(bowl["bowler_runs"].sum()) if bowl_balls else 0,
            "economy": (round(bowl["bowler_runs"].sum() * 6 / bowl_balls, 2)
                        if bowl_balls >= 20 else None),
            "wickets": int(bowl["out_credited_to_bowler"].sum()) if bowl_balls else 0,
        })
    return rows


#: Sort key -> the column it orders by. Every column is already computed by
#: metrics.batting_summary / bowling_summary; this map only decides what a
#: caller may sort on. app.analytics.ask advertises these keys verbatim.
SORT_COLUMNS = {
    "runs": "runs", "average": "batting_average", "strike_rate": "strike_rate",
    "wickets": "wickets", "economy": "economy", "matches": "matches",
    "name": "name", "bowling_average": "bowling_average",
    "sixes": "sixes", "balls": "balls",
    "highest_score": "highest_score", "fifties": "fifties",
    "hundreds": "hundreds", "boundary_pct": "boundary_pct",
    "innings": "innings", "overs": "balls_bowled",
}


def directory(ds: Dataset, f: Filters, search: Optional[str] = None,
              role: Optional[str] = None, sort: str = "runs",
              order: str = "desc", limit: int = 50, offset: int = 0,
              min_balls: int = 0, min_innings: int = 0, min_runs: int = 0,
              min_wickets: int = 0) -> dict:
    """Searchable, sortable player index with batting and bowling totals.

    The ``min_*`` floors exist because a rate sorted without one is noise: the
    best strike rate in any competition belongs to whoever faced two balls and
    hit a six. They are applied to the batting sample, except ``min_wickets``,
    which filters the bowling side.
    """
    bat_dv = store.apply(ds.deliveries, f, team_column="batting_team_id")
    bowl_dv = store.apply(ds.deliveries, f, team_column="bowling_team_id")
    bat = metrics.batting_summary(bat_dv).set_index("player_id")
    bowl = metrics.bowling_summary(bowl_dv).set_index("player_id")

    roles = infer_roles(ds)
    ids = sorted(set(bat.index) | set(bowl.index))
    df = pd.DataFrame(index=pd.Index(ids, name="player_id"))
    # The readable name is the one a person recognises; the scorecard form is
    # kept beside it so the Cricsheet provenance stays visible.
    df["name"] = ds.players["display_name"].reindex(df.index)
    df["scorecard_name"] = ds.players["name"].reindex(df.index)
    df["role"] = roles["role"].reindex(df.index)
    for col, src, prefix in (("runs", bat, ""), ("balls", bat, ""), ("innings", bat, ""),
                             ("average", bat, "batting_"), ("strike_rate", bat, ""),
                             ("highest_score", bat, ""), ("fifties", bat, ""),
                             ("hundreds", bat, ""), ("boundary_pct", bat, "")):
        df[prefix + col] = src[col].reindex(df.index) if col in src else None
    df["wickets"] = bowl["wickets"].reindex(df.index)
    df["economy"] = bowl["economy"].reindex(df.index)
    df["bowling_average"] = bowl["average"].reindex(df.index)
    df["balls_bowled"] = bowl["balls"].reindex(df.index)
    df["overs"] = bowl["overs"].reindex(df.index)

    sq = ds.squads
    if f.seasons:
        sq = sq[sq["season"].isin(f.seasons)]
    if f.team_ids:
        sq = sq[sq["team_id"].isin(f.team_ids)]
    df["matches"] = sq.groupby("player_id")["match_id"].nunique().reindex(df.index).fillna(0).astype(int)
    last_team = sq.sort_values("season").groupby("player_id")["team_id"].last()
    df["team_id"] = last_team.reindex(df.index)
    df["team_name"] = df["team_id"].map(ds.teams["name"])
    df["seasons"] = sq.groupby("player_id")["season"].nunique().reindex(df.index).fillna(0).astype(int)

    if f.team_ids is not None:
        df = df[df["matches"] > 0]
    if search:
        # Same matcher as the global search box: either name form, initials and
        # first names all work. See app/analytics/names.py.
        hits = names.matching_ids(ds, search)
        df = df[df.index.isin(hits or [])]
    if role:
        df = df[df["role"] == role]
    for column, floor in (("balls", min_balls), ("innings", min_innings),
                          ("runs", min_runs), ("wickets", min_wickets)):
        if floor:
            df = df[df[column].fillna(0) >= floor]

    total = len(df)
    sort_col = SORT_COLUMNS.get(sort, "runs")
    if sort_col not in df.columns:
        sort_col = "runs"
    ascending = order == "asc"
    df = df.sort_values(sort_col, ascending=ascending, na_position="last")
    page = df.iloc[offset: offset + limit].reset_index()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "sort": sort,
        "order": order,
        "minimums": {k: v for k, v in {
            "balls": min_balls, "innings": min_innings,
            "runs": min_runs, "wickets": min_wickets}.items() if v},
        "filters": f.describe(),
        "rows": metrics.records(page, ds),
    }


def _split(dv: pd.DataFrame, pid: str, kind: str, by: str) -> List[dict]:
    col = "batter_id" if kind == "batting" else "bowler_id"
    sub = dv[dv[col] == pid]
    if sub.empty:
        return []
    fn = metrics.batting_summary if kind == "batting" else metrics.bowling_summary
    rows = []
    for key, grp in sub.groupby(by, sort=True):
        summary = fn(grp)
        if summary.empty:
            continue
        rec = metrics.records(summary)[0]
        rec.pop("player_id", None)
        rec[by] = key.item() if hasattr(key, "item") else key
        rows.append(rec)
    return rows


def profile(ds: Dataset, pid: str, f: Filters) -> Optional[dict]:
    if pid not in ds.players.index:
        return None
    bat_dv = store.apply(ds.deliveries, f, team_column="batting_team_id")
    bowl_dv = store.apply(ds.deliveries, f, team_column="bowling_team_id")
    bat_dv = bat_dv[(bat_dv["batter_id"] == pid) | (bat_dv["non_striker_id"] == pid)]
    bowl_dv = bowl_dv[bowl_dv["bowler_id"] == pid]

    bat = metrics.batting_summary(bat_dv)
    bat_row = metrics.records(bat[bat["player_id"] == pid])
    bowl = metrics.bowling_summary(bowl_dv)
    bowl_row = metrics.records(bowl[bowl["player_id"] == pid])

    sq = ds.squads[ds.squads["player_id"] == pid]
    if f.seasons:
        sq = sq[sq["season"].isin(f.seasons)]
    roles = infer_roles(ds)

    # Phase, venue and opposition splits are built from deliveries this player
    # actually faced, so that batting_summary() yields exactly one row.
    faced = bat_dv[bat_dv["batter_id"] == pid]
    # The innings list, by contrast, is given the same frame as the career
    # batting line above, which includes appearances as non-striker. Otherwise
    # a batter run out at the non-striker's end without facing a ball counts
    # as an innings in the career total but is missing from the innings list.
    innings = metrics.batting_innings(bat_dv)
    innings = innings[innings["player_id"] == pid].merge(
        ds.matches[["id", "date", "season"]].rename(columns={"id": "match_id"}),
        on="match_id", how="left", suffixes=("", "_m"),
    ).sort_values("date", ascending=False)
    innings["opposition"] = innings["bowling_team_id"].map(ds.teams["name"])
    innings["strike_rate"] = [metrics.div(r * 100, b) for r, b in zip(innings["runs"], innings["balls"])]
    innings["date"] = innings["date"].dt.date.astype(str)

    spells = metrics.bowling_spells(bowl_dv)
    spells = spells[spells["player_id"] == pid].merge(
        ds.matches[["id", "date"]].rename(columns={"id": "match_id"}), on="match_id", how="left"
    ).sort_values("date", ascending=False)
    spells["opposition"] = spells["batting_team_id"].map(ds.teams["name"])
    spells["overs"] = [metrics.overs_string(int(b)) for b in spells["balls"]]
    spells["economy"] = [metrics.div(r * 6, b) for r, b in zip(spells["runs"], spells["balls"])]
    spells["date"] = spells["date"].dt.date.astype(str)

    recent = innings.head(20)
    sequences = ball_sequences(faced, [int(i) for i in recent["innings_id"].tolist()])
    recent_innings = metrics.records(
        recent[["innings_id", "date", "opposition", "runs", "balls", "fours", "sixes",
                "strike_rate", "out", "season"]]
    )
    for row in recent_innings:
        row["sequence"] = sequences.get(int(row.pop("innings_id")), [])

    # Includes dismissals taken while at the non-striker's end (run outs).
    dismissals = bat_dv[bat_dv["out_player_id"] == pid]
    dismissal_patterns = (
        dismissals.groupby("out_kind").size().sort_values(ascending=False).to_dict()
        if not dismissals.empty else {}
    )

    def venue_split(dv, kind):
        rows = _split(dv, pid, kind, "venue_id")
        for r in rows:
            vid = r.pop("venue_id")
            r["venue"] = ds.venues.at[vid, "name"] if vid in ds.venues.index else "Unknown"
        return sorted(rows, key=lambda r: -(r.get("balls") or 0))

    def opposition_split(dv, kind):
        col = "bowling_team_id" if kind == "batting" else "batting_team_id"
        rows = _split(dv, pid, kind, col)
        for r in rows:
            tid = r.pop(col)
            r["opposition"] = ds.teams.at[tid, "name"] if tid in ds.teams.index else "Unknown"
        return rows

    return {
        "player": {
            "id": pid,
            "name": ds.player_name(pid),
            "scorecard_name": ds.scorecard_name(pid),
            "role": roles.at[pid, "role"] if pid in roles.index else None,
            "role_basis": roles.at[pid, "role_basis"] if pid in roles.index else None,
            "matches": int(sq["match_id"].nunique()),
            "seasons": sorted(sq["season"].unique().tolist()),
            "teams": _team_history(ds, pid),
        },
        "filters": f.describe(),
        "batting": bat_row[0] if bat_row else None,
        "bowling": bowl_row[0] if bowl_row else None,
        "batting_by_phase": metrics.phase_split(faced, "batting"),
        "bowling_by_phase": metrics.phase_split(bowl_dv, "bowling"),
        "batting_by_innings_type": {
            "chasing": metrics.records(metrics.batting_summary(faced[faced["is_chase"]])),
            "setting": metrics.records(metrics.batting_summary(faced[~faced["is_chase"]])),
        },
        "bowling_by_innings_type": {
            "defending": metrics.records(metrics.bowling_summary(bowl_dv[bowl_dv["is_chase"]])),
            "first_innings": metrics.records(metrics.bowling_summary(bowl_dv[~bowl_dv["is_chase"]])),
        },
        "batting_by_season": _split(bat_dv, pid, "batting", "season"),
        "bowling_by_season": _split(bowl_dv, pid, "bowling", "season"),
        "batting_by_venue": venue_split(bat_dv, "batting")[:15],
        "bowling_by_venue": venue_split(bowl_dv, "bowling")[:15],
        "batting_by_opposition": opposition_split(bat_dv, "batting"),
        "bowling_by_opposition": opposition_split(bowl_dv, "bowling"),
        "recent_innings": recent_innings,
        "recent_spells": metrics.records(
            spells[["date", "opposition", "overs", "runs", "wickets", "economy", "season"]].head(20)
        ),
        "dismissal_patterns": {k: int(v) for k, v in dismissal_patterns.items()},
        "scoring_shape": scoring_shape(faced),
        "by_over": by_over(faced, bowl_dv),
        "highlights": highlights(
            bat_row[0] if bat_row else None,
            bowl_row[0] if bowl_row else None,
            metrics.phase_split(faced, "batting"),
            metrics.phase_split(bowl_dv, "bowling"),
        ),
        "data_notes": {
            "bowling_style_splits_available": BOWLING_STYLE_DATA_AVAILABLE,
            "bowling_style_note": (
                "Cricsheet ball-by-ball files do not carry bowling style or batting hand, "
                "so pace/spin and arm splits are not published. Use Match-ups for "
                "head-to-head records against named bowlers."
            ),
            "qualification": QUALIFICATION,
            "metrics": METRIC_DEFINITIONS,
            "phases": PHASE_ORDER,
        },
    }
