import * as React from "react";
import { cn } from "@/lib/utils";
import type { ScoringShape } from "@/types";

/**
 * How a batter's runs are made, as two concentric arcs.
 *
 * The outer ring is the share of *balls* that produced each outcome; the inner
 * ring is the share of *runs* those balls produced. The gap between the two is
 * the point: a batter can hit a boundary off a tenth of their balls and take a
 * third of their runs from it, and no strike rate shows that.
 *
 * Drawn as inline SVG with stroke-dasharray rather than a chart library: it is
 * two circles, and it needs to render identically on the server.
 */
/**
 * Ones, twos and threes stay deliberately muted and only step in lightness;
 * the boundaries get the only saturated hues, because a boundary is the event
 * and strike rotation is the background rhythm.
 */
const BUCKET_COLORS: Record<string, string> = {
  Dot: "#232E3C",
  Single: "#47596B",
  Two: "#687E93",
  Three: "#8EA2B6",
  Four: "#6AA9E0",
  Six: "#3FBF7F",
  Other: "#55606E",
};

function Arcs({
  buckets,
  radius,
  width,
  shareKey,
  size,
}: {
  buckets: ScoringShape["buckets"];
  radius: number;
  width: number;
  shareKey: "ball_share" | "run_share";
  size: number;
}) {
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  return (
    <>
      {buckets.map((b) => {
        const share = b[shareKey] ?? 0;
        if (share <= 0) return null;
        const length = (share / 100) * circumference;
        const dash = `${Math.max(length - 1.5, 0)} ${circumference - Math.max(length - 1.5, 0)}`;
        const el = (
          <circle
            key={`${shareKey}-${b.label}`}
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={BUCKET_COLORS[b.label] ?? "#64748B"}
            strokeWidth={width}
            strokeDasharray={dash}
            strokeDashoffset={-offset}
            opacity={shareKey === "run_share" ? 0.95 : 0.8}
          />
        );
        offset += length;
        return el;
      })}
    </>
  );
}

export function ScoringRing({
  shape,
  size = 168,
  className,
}: {
  shape: ScoringShape;
  size?: number;
  className?: string;
}) {
  const boundary = shape.buckets
    .filter((b) => b.label === "Four" || b.label === "Six")
    .reduce((a, b) => a + b.run_share, 0);

  return (
    <div className={cn("flex flex-wrap items-center gap-5", className)}>
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          // Start both rings at twelve o'clock.
          style={{ transform: "rotate(-90deg)" }}
          role="img"
          aria-label="Share of balls and share of runs by outcome"
        >
          <Arcs buckets={shape.buckets} radius={size / 2 - 9} width={14} shareKey="ball_share" size={size} />
          <Arcs buckets={shape.buckets} radius={size / 2 - 30} width={14} shareKey="run_share" size={size} />
        </svg>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="num font-display text-2xl font-bold leading-none text-ink">
            {boundary.toFixed(0)}%
          </span>
          <span className="mt-1 max-w-[72px] text-center text-[0.5625rem] leading-tight text-ink-faint">
            of runs in boundaries
          </span>
        </div>
      </div>

      <dl className="min-w-0 flex-1 space-y-1.5">
        <div className="flex items-center gap-2 text-2xs text-ink-faint">
          <span className="w-16 shrink-0" />
          <span className="w-12 shrink-0 text-right">balls</span>
          <span className="w-12 shrink-0 text-right">runs</span>
        </div>
        {shape.buckets.map((b) => (
          <div key={b.label} className="flex items-center gap-2">
            <dt className="flex w-16 shrink-0 items-center gap-1.5 text-2xs text-ink-muted">
              <span
                className="h-2 w-2 shrink-0 rounded-sm"
                style={{ background: BUCKET_COLORS[b.label] ?? "#64748B" }}
                aria-hidden
              />
              {b.label}
            </dt>
            <dd className="num w-12 shrink-0 text-right text-2xs text-ink-muted">
              {b.ball_share}%
            </dd>
            <dd className="num w-12 shrink-0 text-right text-2xs text-ink">{b.run_share}%</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
