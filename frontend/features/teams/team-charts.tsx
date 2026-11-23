"use client";

import * as React from "react";
import { Bars, RadarCompare, TrendLine } from "@/components/charts";
import type { TeamProfile } from "@/types";

const PHASE_LABEL: Record<string, string> = {
  powerplay: "Powerplay (1–6)",
  middle: "Middle (7–15)",
  death: "Death (16–20)",
};

/**
 * Team balance, plotted against the league rather than in isolation.
 *
 * Each axis is the team's phase performance expressed as a percentage of the
 * league average for the same phase and the same filters, with bowling
 * inverted so that outward always means stronger. 100 is league-average, so
 * the reference ring — not the centre — is the thing to read against.
 */
export function TeamBalance({ profile }: { profile: TeamProfile }) {
  const axes: Array<Record<string, any>> = [];

  for (const p of profile.phase_profile.batting) {
    if (!p.run_rate || !p.league_run_rate) continue;
    axes.push({
      metric: `Bat ${PHASE_LABEL[p.phase]?.split(" ")[0] ?? p.phase}`,
      value: Math.round((p.run_rate / p.league_run_rate) * 100),
      league: 100,
    });
  }
  for (const p of profile.phase_profile.bowling) {
    if (!p.run_rate || !p.league_run_rate) continue;
    // Conceding below the league rate is good, so invert the ratio.
    axes.push({
      metric: `Bowl ${PHASE_LABEL[p.phase]?.split(" ")[0] ?? p.phase}`,
      value: Math.round((p.league_run_rate / p.run_rate) * 100),
      league: 100,
    });
  }

  if (axes.length < 3) return null;

  return (
    <>
      <RadarCompare
        data={axes}
        series={[
          { key: "value", name: profile.team.short_name ?? profile.team.name },
          { key: "league", name: "League average" },
        ]}
        height={320}
      />
      <p className="px-4 pb-3 text-2xs leading-relaxed text-ink-faint">
        100 is the league average for that phase under the same filters. Batting axes are the
        team&apos;s run rate as a share of the league&apos;s; bowling axes are inverted, so a value
        above 100 means the team concedes less than the league does in that phase.
      </p>
    </>
  );
}

export function SeasonRecordChart({ profile }: { profile: TeamProfile }) {
  const data = profile.by_season.map((s) => ({
    season: s.season,
    won: s.won,
    lost: s.lost,
    win_pct: s.win_pct ?? null,
  }));
  return (
    <div className="space-y-4">
      <Bars
        data={data}
        xKey="season"
        stacked
        series={[
          { key: "won", name: "Won" },
          { key: "lost", name: "Lost" },
        ]}
        height={200}
      />
      <TrendLine
        data={data}
        xKey="season"
        series={[{ key: "win_pct", name: "Win %" }]}
        height={180}
        yDomain={[0, 100]}
      />
    </div>
  );
}

export function BattingDepthChart({ profile }: { profile: TeamProfile }) {
  const data = profile.batting_depth.map((d) => ({
    position: `#${d.position}`,
    runs_per_innings: d.runs_per_innings ?? 0,
    strike_rate: d.strike_rate ?? 0,
  }));
  return (
    <Bars
      data={data}
      xKey="position"
      series={[
        { key: "runs_per_innings", name: "Runs per innings" },
        { key: "strike_rate", name: "Strike rate" },
      ]}
      height={220}
    />
  );
}

export function RoleMix({ distribution }: { distribution: Record<string, number> }) {
  const data = Object.entries(distribution).map(([role, count]) => ({ role, count }));
  if (!data.length) return null;
  return <Bars data={data} xKey="role" series={[{ key: "count", name: "Players" }]} height={180} horizontal />;
}
