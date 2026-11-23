"use client";

import * as React from "react";
import { Bars, RadarCompare, TrendLine, SERIES } from "@/components/charts";
import { EmptyState } from "@/components/ui/states";
import type { PlayerProfile } from "@/types";

/**
 * Radar axes are normalised to the best value *within this comparison*, not
 * against the league. A 100 therefore means "highest of the players shown",
 * never "elite". Metrics where lower is better are inverted so that further
 * from the centre always reads as stronger.
 */
interface Axis {
  metric: string;
  get: (p: PlayerProfile) => number | null | undefined;
  invert?: boolean;
}

const BATTING_AXES: Axis[] = [
  { metric: "Average", get: (p) => p.batting?.average },
  { metric: "Strike rate", get: (p) => p.batting?.strike_rate },
  { metric: "Boundary %", get: (p) => p.batting?.boundary_pct },
  { metric: "Dot % (low)", get: (p) => p.batting?.dot_pct, invert: true },
  { metric: "Runs", get: (p) => p.batting?.runs },
  { metric: "Fifty+ rate", get: (p) =>
      p.batting && p.batting.innings
        ? ((p.batting.fifties + p.batting.hundreds) / p.batting.innings) * 100
        : null },
];

const BOWLING_AXES: Axis[] = [
  { metric: "Wickets", get: (p) => p.bowling?.wickets },
  { metric: "Economy (low)", get: (p) => p.bowling?.economy, invert: true },
  { metric: "Average (low)", get: (p) => p.bowling?.average, invert: true },
  { metric: "Strike rate (low)", get: (p) => p.bowling?.strike_rate, invert: true },
  { metric: "Dot %", get: (p) => p.bowling?.dot_pct },
];

function buildRadar(players: PlayerProfile[], axes: Axis[]) {
  return axes
    .map((axis) => {
      const raw = players.map((p) => {
        const v = axis.get(p);
        return typeof v === "number" && Number.isFinite(v) ? v : null;
      });
      const defined = raw.filter((v): v is number => v !== null && v > 0);
      if (defined.length < 1) return null;
      // Invert first (so smaller becomes larger), then scale the set to 100.
      const scored = raw.map((v) => (v === null || v <= 0 ? null : axis.invert ? 1 / v : v));
      const max = Math.max(...scored.filter((v): v is number => v !== null));
      const row: Record<string, any> = { metric: axis.metric };
      players.forEach((p, i) => {
        const s = scored[i];
        row[p.player.id] = s === null || max <= 0 ? 0 : Math.round((s / max) * 100);
      });
      return row;
    })
    .filter(Boolean) as Array<Record<string, any>>;
}

export function CompareRadar({
  players,
  kind,
}: {
  players: PlayerProfile[];
  kind: "batting" | "bowling";
}) {
  const axes = kind === "batting" ? BATTING_AXES : BOWLING_AXES;
  const data = buildRadar(players, axes);
  if (data.length < 3) {
    return (
      <EmptyState
        title="Not enough shared metrics to plot"
        detail="At least three comparable axes are needed. These players have no overlapping record in this discipline under the current filters."
        className="py-10"
      />
    );
  }
  return (
    <>
      <RadarCompare
        data={data}
        series={players.map((p) => ({ key: p.player.id, name: p.player.name }))}
      />
      <p className="px-4 pb-3 text-2xs leading-relaxed text-ink-faint">
        Each axis is scaled so the strongest of these {players.length} players reads 100. The shape
        shows relative profile within this comparison only — it is not a league-wide rating, and a
        larger area does not make a player better.
      </p>
    </>
  );
}

export function CompareSeasons({
  players,
  kind,
  metric,
}: {
  players: PlayerProfile[];
  kind: "batting" | "bowling";
  metric: "runs" | "strike_rate" | "average" | "wickets" | "economy";
}) {
  const seasons = Array.from(
    new Set(
      players.flatMap((p) =>
        (kind === "batting" ? p.batting_by_season : p.bowling_by_season).map((r) => r.season),
      ),
    ),
  ).sort((a, b) => a - b);

  if (!seasons.length) return <EmptyState title="No seasons in common" className="py-10" />;

  const data = seasons.map((season) => {
    const row: Record<string, any> = { season };
    players.forEach((p) => {
      const rows: any[] = kind === "batting" ? p.batting_by_season : p.bowling_by_season;
      const hit = rows.find((r) => r.season === season);
      // A season the player did not play is a gap in the line, not a zero.
      row[p.player.id] = hit ? (hit as any)[metric] ?? null : null;
    });
    return row;
  });

  return (
    <TrendLine
      data={data}
      xKey="season"
      series={players.map((p, i) => ({
        key: p.player.id,
        name: p.player.name,
        color: SERIES[i % SERIES.length],
      }))}
      height={240}
    />
  );
}

export function ComparePhases({
  players,
  kind,
  metric,
}: {
  players: PlayerProfile[];
  kind: "batting" | "bowling";
  metric: "strike_rate" | "economy" | "average" | "dot_pct";
}) {
  const labels: Record<string, string> = {
    powerplay: "Powerplay (1–6)",
    middle: "Middle (7–15)",
    death: "Death (16–20)",
  };
  const phases = ["powerplay", "middle", "death"];
  const data = phases.map((phase) => {
    const row: Record<string, any> = { phase: labels[phase] };
    players.forEach((p) => {
      const rows: any[] = kind === "batting" ? p.batting_by_phase : p.bowling_by_phase;
      const hit = rows.find((r) => r.phase === phase);
      row[p.player.id] = hit && (hit.balls ?? 0) > 0 ? hit[metric] ?? null : null;
    });
    return row;
  });
  return (
    <Bars
      data={data}
      xKey="phase"
      series={players.map((p, i) => ({
        key: p.player.id,
        name: p.player.name,
        color: SERIES[i % SERIES.length],
      }))}
      height={240}
    />
  );
}

