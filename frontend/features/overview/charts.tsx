"use client";

import * as React from "react";
import { Panel, PanelHeader, PanelBody } from "@/components/ui/card";
import { Bars, Distribution, TrendLine } from "@/components/charts";
import { PHASE_COLORS } from "@/components/charts/theme";
import type { OverviewPayload } from "@/types";

export function OverviewCharts({
  trends,
  distribution,
}: {
  trends: OverviewPayload["trends"];
  distribution: OverviewPayload["distribution"];
}) {
  // Phase run rates pivoted to one row per season.
  const phaseBySeason = React.useMemo(() => {
    const map = new Map<number, Record<string, number | string>>();
    for (const row of trends.phases) {
      const entry = map.get(row.season) ?? { season: row.season };
      entry[row.phase] = row.run_rate;
      map.set(row.season, entry);
    }
    return Array.from(map.values()).sort((a, b) => Number(a.season) - Number(b.season));
  }, [trends.phases]);

  // Only teams still playing in the most recent season keep the chart readable.
  const teamTrend = React.useMemo(() => {
    const latest = Math.max(...trends.teams.map((t) => t.season));
    const active = new Set(
      trends.teams.filter((t) => t.season === latest).map((t) => t.team_name),
    );
    const bySeason = new Map<number, Record<string, number | string>>();
    for (const t of trends.teams) {
      if (!active.has(t.team_name)) continue;
      const row = bySeason.get(t.season) ?? { season: t.season };
      row[t.team_name] = t.win_pct;
      bySeason.set(t.season, row);
    }
    return {
      data: Array.from(bySeason.values()).sort((a, b) => Number(a.season) - Number(b.season)),
      teams: Array.from(active),
    };
  }, [trends.teams]);

  const batMedian = median(distribution.batting.map((d) => d.strike_rate));
  const avgMedian = median(distribution.batting.map((d) => d.average));

  return (
    <div className="grid min-w-0 gap-4 xl:grid-cols-2 [&>*]:min-w-0">
      <Panel>
        <PanelHeader
          title="Scoring by season"
          description="Runs per over across all innings, and balls per wicket as a measure of how hard wickets are to take."
        />
        <PanelBody>
          <TrendLine
            data={trends.seasons}
            xKey="season"
            series={[
              { key: "run_rate", name: "Run rate (RPO)" },
              { key: "boundary_pct", name: "Boundary %", color: "#7FA8C9" },
            ]}
          />
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader
          title="Wickets and volume by season"
          description="Total wickets alongside matches played, so expansion seasons are not mistaken for bowler-friendly ones."
        />
        <PanelBody>
          <Bars
            data={trends.seasons}
            xKey="season"
            series={[
              { key: "wickets", name: "Wickets" },
              { key: "matches", name: "Matches", color: "#8E978F" },
            ]}
          />
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader
          title="Phase scoring patterns"
          description="Run rate in the powerplay (1–6), middle overs (7–15) and death (16–20)."
        />
        <PanelBody>
          <TrendLine
            data={phaseBySeason}
            xKey="season"
            series={[
              { key: "powerplay", name: "Powerplay", color: PHASE_COLORS.powerplay },
              { key: "middle", name: "Middle", color: PHASE_COLORS.middle },
              { key: "death", name: "Death", color: PHASE_COLORS.death },
            ]}
          />
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader
          title="Team win rate by season"
          description="Currently active franchises. Teams are tracked through rebrands, so Delhi and Punjab lines are continuous."
        />
        <PanelBody>
          <TrendLine
            data={teamTrend.data}
            xKey="season"
            height={240}
            series={teamTrend.teams.map((name) => ({ key: name, name }))}
            yDomain={[0, 100]}
          />
        </PanelBody>
      </Panel>

      <Panel className="xl:col-span-2">
        <PanelHeader
          title="Batting profile distribution"
          description="Every qualified batter plotted by strike rate against average. The dashed lines are the medians — top right is both quick and durable, bottom right is a pure accelerator."
        />
        <PanelBody>
          <Distribution
            data={distribution.batting}
            xKey="strike_rate"
            yKey="average"
            zKey="runs"
            xLabel="Strike rate"
            yLabel="Average"
            xMedian={batMedian}
            yMedian={avgMedian}
          />
        </PanelBody>
      </Panel>
    </div>
  );
}

function median(values: number[]): number | undefined {
  const clean = values.filter((v) => typeof v === "number" && !Number.isNaN(v)).sort((a, b) => a - b);
  if (!clean.length) return undefined;
  const mid = Math.floor(clean.length / 2);
  return clean.length % 2 ? clean[mid] : (clean[mid - 1] + clean[mid]) / 2;
}
