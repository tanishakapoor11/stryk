"use client";

import * as React from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { CHART, PHASE_COLORS, SERIES } from "./theme";

const axisProps = {
  stroke: CHART.axis,
  tick: { fill: CHART.tick, fontSize: 11 },
  tickLine: false,
  axisLine: { stroke: CHART.grid },
};

function TooltipBox({ active, payload, label, unit }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded border border-line-strong bg-surface-raised px-2.5 py-2 text-xs shadow-raise">
      {label !== undefined ? (
        <div className="mb-1 font-medium text-ink">{label}</div>
      ) : null}
      {payload.map((p: any) => (
        <div key={p.dataKey ?? p.name} className="flex items-center gap-2 text-ink-muted">
          <span
            className="inline-block h-2 w-2 rounded-sm"
            style={{ background: p.color ?? p.fill }}
            aria-hidden
          />
          <span>{p.name}</span>
          <span className="num ml-auto pl-3 text-ink">
            {typeof p.value === "number" ? p.value.toLocaleString() : p.value}
            {unit ?? ""}
          </span>
        </div>
      ))}
    </div>
  );
}

export function ChartFrame({
  height = 240,
  children,
}: {
  height?: number;
  children: React.ReactElement;
}) {
  // min-w-0 and overflow-hidden are load-bearing, not cosmetic: a grid or flex
  // item defaults to min-width:auto, so a ResponsiveContainer measures its own
  // content, renders wider than the viewport, and drags the whole page into a
  // horizontal scroll on a phone. Capping it here fixes every chart at once.
  return (
    <div style={{ height }} className="w-full min-w-0 overflow-hidden">
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  );
}

export function TrendLine({
  data,
  xKey,
  series,
  height = 240,
  unit,
  yDomain,
}: {
  data: any[];
  xKey: string;
  series: { key: string; name: string; color?: string }[];
  height?: number;
  unit?: string;
  yDomain?: [number | "auto", number | "auto"];
}) {
  return (
    <ChartFrame height={height}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
        <CartesianGrid stroke={CHART.grid} vertical={false} />
        <XAxis dataKey={xKey} {...axisProps} />
        <YAxis {...axisProps} domain={yDomain ?? ["auto", "auto"]} width={46} />
        <Tooltip content={<TooltipBox unit={unit} />} cursor={{ stroke: CHART.grid }} />
        {series.length > 1 ? (
          <Legend wrapperStyle={{ fontSize: 11, color: CHART.tick }} iconType="plainline" />
        ) : null}
        {series.map((s, i) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.name}
            stroke={s.color ?? SERIES[i % SERIES.length]}
            strokeWidth={1.75}
            dot={false}
            activeDot={{ r: 3 }}
          />
        ))}
      </LineChart>
    </ChartFrame>
  );
}

export function TrendArea({
  data,
  xKey,
  dataKey,
  name,
  height = 200,
}: {
  data: any[];
  xKey: string;
  dataKey: string;
  name: string;
  height?: number;
}) {
  return (
    <ChartFrame height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
        <defs>
          <linearGradient id="fillAccent" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={CHART.accent} stopOpacity={0.3} />
            <stop offset="100%" stopColor={CHART.accent} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={CHART.grid} vertical={false} />
        <XAxis dataKey={xKey} {...axisProps} />
        <YAxis {...axisProps} width={46} />
        <Tooltip content={<TooltipBox />} cursor={{ stroke: CHART.grid }} />
        <Area
          type="monotone"
          dataKey={dataKey}
          name={name}
          stroke={CHART.accent}
          strokeWidth={1.75}
          fill="url(#fillAccent)"
        />
      </AreaChart>
    </ChartFrame>
  );
}

export function Bars({
  data,
  xKey,
  series,
  height = 240,
  stacked,
  colorByPhase,
  horizontal,
}: {
  data: any[];
  xKey: string;
  series: { key: string; name: string; color?: string }[];
  height?: number;
  stacked?: boolean;
  colorByPhase?: boolean;
  horizontal?: boolean;
}) {
  return (
    <ChartFrame height={height}>
      <BarChart
        data={data}
        layout={horizontal ? "vertical" : "horizontal"}
        margin={{ top: 8, right: 12, bottom: 0, left: horizontal ? 8 : -12 }}
      >
        <CartesianGrid stroke={CHART.grid} vertical={horizontal} horizontal={!horizontal} />
        {horizontal ? (
          <>
            <XAxis type="number" {...axisProps} />
            <YAxis type="category" dataKey={xKey} {...axisProps} width={120} />
          </>
        ) : (
          <>
            <XAxis dataKey={xKey} {...axisProps} />
            <YAxis {...axisProps} width={46} />
          </>
        )}
        <Tooltip content={<TooltipBox />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
        {series.length > 1 ? (
          <Legend wrapperStyle={{ fontSize: 11, color: CHART.tick }} iconType="square" />
        ) : null}
        {series.map((s, i) => (
          <Bar
            key={s.key}
            dataKey={s.key}
            name={s.name}
            stackId={stacked ? "a" : undefined}
            fill={s.color ?? SERIES[i % SERIES.length]}
            radius={stacked ? 0 : 1}
          >
            {colorByPhase
              ? data.map((d, idx) => (
                  <Cell key={idx} fill={PHASE_COLORS[d[xKey]] ?? SERIES[idx % SERIES.length]} />
                ))
              : null}
          </Bar>
        ))}
      </BarChart>
    </ChartFrame>
  );
}

export function Distribution({
  data,
  xKey,
  yKey,
  zKey,
  xLabel,
  yLabel,
  height = 320,
  xMedian,
  yMedian,
}: {
  data: any[];
  xKey: string;
  yKey: string;
  zKey?: string;
  xLabel: string;
  yLabel: string;
  height?: number;
  xMedian?: number;
  yMedian?: number;
}) {
  return (
    <ChartFrame height={height}>
      <ScatterChart margin={{ top: 12, right: 16, bottom: 16, left: -6 }}>
        <CartesianGrid stroke={CHART.grid} />
        <XAxis
          type="number"
          dataKey={xKey}
          name={xLabel}
          domain={["dataMin - 5", "dataMax + 5"]}
          label={{ value: xLabel, position: "insideBottom", offset: -8, fill: CHART.tick, fontSize: 11 }}
          {...axisProps}
        />
        <YAxis
          type="number"
          dataKey={yKey}
          name={yLabel}
          domain={["dataMin - 2", "dataMax + 2"]}
          width={48}
          label={{ value: yLabel, angle: -90, position: "insideLeft", offset: 14, fill: CHART.tick, fontSize: 11 }}
          {...axisProps}
        />
        {zKey ? <ZAxis type="number" dataKey={zKey} range={[12, 160]} /> : null}
        {xMedian !== undefined ? (
          <ReferenceLine x={xMedian} stroke={CHART.axis} strokeDasharray="3 3" />
        ) : null}
        {yMedian !== undefined ? (
          <ReferenceLine y={yMedian} stroke={CHART.axis} strokeDasharray="3 3" />
        ) : null}
        <Tooltip
          cursor={{ strokeDasharray: "3 3", stroke: CHART.grid }}
          content={({ active, payload }: any) => {
            if (!active || !payload?.length) return null;
            const p = payload[0].payload;
            return (
              <div className="rounded border border-line-strong bg-surface-raised px-2.5 py-2 text-xs shadow-raise">
                <div className="font-medium text-ink">{p.player_name}</div>
                <div className="num mt-1 text-ink-muted">
                  {xLabel}: <span className="text-ink">{p[xKey]}</span>
                </div>
                <div className="num text-ink-muted">
                  {yLabel}: <span className="text-ink">{p[yKey]}</span>
                </div>
              </div>
            );
          }}
        />
        <Scatter data={data} fill={CHART.accent} fillOpacity={0.55} />
      </ScatterChart>
    </ChartFrame>
  );
}

export function RadarCompare({
  data,
  series,
  height = 300,
}: {
  data: Array<Record<string, any>>;
  series: { key: string; name: string }[];
  height?: number;
}) {
  return (
    <ChartFrame height={height}>
      <RadarChart data={data} outerRadius="72%">
        <PolarGrid stroke={CHART.grid} />
        <PolarAngleAxis dataKey="metric" tick={{ fill: CHART.tick, fontSize: 11 }} />
        <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
        <Tooltip content={<TooltipBox />} />
        <Legend wrapperStyle={{ fontSize: 11, color: CHART.tick }} iconType="square" />
        {series.map((s, i) => (
          <Radar
            key={s.key}
            dataKey={s.key}
            name={s.name}
            stroke={SERIES[i % SERIES.length]}
            fill={SERIES[i % SERIES.length]}
            fillOpacity={0.16}
            strokeWidth={1.75}
          />
        ))}
      </RadarChart>
    </ChartFrame>
  );
}

export { SERIES, PHASE_COLORS };
