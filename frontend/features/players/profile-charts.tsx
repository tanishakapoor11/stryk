"use client";

import * as React from "react";
import { Bars, TrendLine } from "@/components/charts";
import { PanelBody, PanelHeader } from "@/components/ui/card";
import type { BattingLine, BowlingLine, PhaseLine } from "@/types";

const PHASE_LABEL: Record<string, string> = {
  powerplay: "Powerplay (1–6)",
  middle: "Middle (7–15)",
  death: "Death (16–20)",
};

export function SeasonBattingChart({ rows }: { rows: Array<BattingLine & { season: number }> }) {
  const data = rows.map((r) => ({
    season: r.season,
    runs: r.runs,
    strike_rate: r.strike_rate ?? null,
    average: r.average ?? null,
  }));
  return (
    <>
      <PanelHeader
        title="Season-wise batting"
        description="Runs scored each season against the strike rate and average achieved in that season — the shape of a career rather than one career number."
      />
      <PanelBody className="space-y-4">
        <Bars data={data} xKey="season" series={[{ key: "runs", name: "Runs" }]} height={180} />
        <TrendLine
          data={data}
          xKey="season"
          series={[
            { key: "strike_rate", name: "Strike rate" },
            { key: "average", name: "Average" },
          ]}
          height={180}
        />
      </PanelBody>
    </>
  );
}

export function SeasonBowlingChart({ rows }: { rows: Array<BowlingLine & { season: number }> }) {
  const data = rows.map((r) => ({
    season: r.season,
    wickets: r.wickets,
    economy: r.economy ?? null,
    strike_rate: r.strike_rate ?? null,
  }));
  return (
    <>
      <PanelHeader
        title="Season-wise bowling"
        description="Wickets taken each season with the economy and bowling strike rate from the same season."
      />
      <PanelBody className="space-y-4">
        <Bars data={data} xKey="season" series={[{ key: "wickets", name: "Wickets" }]} height={180} />
        <TrendLine
          data={data}
          xKey="season"
          series={[
            { key: "economy", name: "Economy" },
            { key: "strike_rate", name: "Balls per wicket" },
          ]}
          height={180}
        />
      </PanelBody>
    </>
  );
}

export function PhaseChart({
  batting,
  bowling,
}: {
  batting: PhaseLine[];
  bowling: PhaseLine[];
}) {
  const bat = batting
    .filter((p) => (p.balls ?? 0) > 0)
    .map((p) => ({ phase: PHASE_LABEL[p.phase] ?? p.phase, strike_rate: p.strike_rate ?? 0, dot_pct: p.dot_pct ?? 0 }));
  const bowl = bowling
    .filter((p) => (p.balls ?? 0) > 0)
    .map((p) => ({ phase: PHASE_LABEL[p.phase] ?? p.phase, economy: p.economy ?? 0, dot_pct: p.dot_pct ?? 0 }));
  return (
    <div className="grid min-w-0 gap-4 lg:grid-cols-2 [&>*]:min-w-0">
      {bat.length ? (
        <div>
          <p className="label-xs mb-2">Batting by phase</p>
          <Bars
            data={bat}
            xKey="phase"
            series={[
              { key: "strike_rate", name: "Strike rate" },
              { key: "dot_pct", name: "Dot %" },
            ]}
            height={200}
          />
        </div>
      ) : null}
      {bowl.length ? (
        <div>
          <p className="label-xs mb-2">Bowling by phase</p>
          <Bars
            data={bowl}
            xKey="phase"
            series={[
              { key: "economy", name: "Economy" },
              { key: "dot_pct", name: "Dot %" },
            ]}
            height={200}
          />
        </div>
      ) : null}
    </div>
  );
}

export function DismissalChart({ patterns }: { patterns: Record<string, number> }) {
  const data = Object.entries(patterns)
    .map(([kind, count]) => ({ kind, count }))
    .sort((a, b) => b.count - a.count);
  if (!data.length) return null;
  return <Bars data={data} xKey="kind" series={[{ key: "count", name: "Dismissals" }]} height={200} horizontal />;
}
