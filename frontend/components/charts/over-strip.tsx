import * as React from "react";
import { cn } from "@/lib/utils";
import { dec, num } from "@/lib/format";
import type { OverProfile } from "@/types";

/**
 * Twenty overs as twenty bars: where in the innings this player operates.
 *
 * Height encodes the *rate* — strike rate batting, economy bowling — because
 * that is the question being asked, and a reader takes height as "better".
 * Sample size is carried by opacity instead, so a confident over looks solid
 * and a thin one looks faint, rather than the two encodings competing. An over
 * below 20 balls has no rate it has earned and is drawn as an empty outline.
 *
 * For a bowler the scale is inverted, so a tall bar is always the good end.
 */
export function OverStrip({
  overs,
  mode,
  teamColor,
  className,
}: {
  overs: OverProfile[];
  mode: "batting" | "bowling";
  teamColor?: string;
  className?: string;
}) {
  const accent = teamColor ?? "#F2B134";
  const sampleKey = mode === "batting" ? "balls_faced" : "balls_bowled";
  const rateKey = mode === "batting" ? "strike_rate" : "economy";

  const rated = overs.filter((o) => o[rateKey] !== null);
  if (!rated.length) return null;

  const rates = rated.map((o) => o[rateKey] as number);
  const maxRate = Math.max(...rates);
  const minRate = Math.min(...rates);
  // A floor below the lowest rate, so the weakest over still reads as a bar
  // rather than vanishing, while differences stay visible.
  const floor = mode === "batting" ? Math.max(minRate - (maxRate - minRate) * 0.5, 0) : 0;
  const maxSample = Math.max(...overs.map((o) => o[sampleKey] as number), 1);

  const heightOf = (rate: number) => {
    if (mode === "batting") {
      return Math.max(((rate - floor) / (maxRate - floor || 1)) * 100, 8);
    }
    // Bowling: cheapest over is tallest.
    return Math.max(((maxRate - rate) / (maxRate - minRate || 1)) * 92 + 8, 8);
  };

  return (
    <div className={cn("w-full", className)}>
      <div className="flex items-end gap-[3px]" style={{ height: 104 }}>
        {overs.map((o) => {
          const sample = o[sampleKey] as number;
          const rate = o[rateKey] as number | null;
          if (sample === 0) {
            return <div key={o.over} className="flex-1" aria-hidden />;
          }
          const unrated = rate === null;
          // Confidence: a near-full-sample over is solid, a thin one is faint.
          const confidence = 0.45 + Math.min(sample / maxSample, 1) * 0.55;
          return (
            <div
              key={o.over}
              title={
                unrated
                  ? `Over ${o.over}: only ${num(sample)} balls — too few to rate`
                  : `Over ${o.over}: ${
                      mode === "batting"
                        ? `${dec(rate)} strike rate off ${num(sample)} balls`
                        : `${dec(rate)} an over across ${num(sample)} balls`
                    }`
              }
              className="flex-1 rounded-t-sm"
              style={{
                height: unrated ? "8%" : `${heightOf(rate as number)}%`,
                background: unrated ? "transparent" : accent,
                opacity: unrated ? 1 : confidence,
                border: unrated ? "1px dashed #334253" : undefined,
              }}
            />
          );
        })}
      </div>
      <div className="mt-1.5 flex gap-[3px]">
        {overs.map((o) => (
          <span
            key={o.over}
            className="num flex-1 text-center text-[0.5rem] leading-none text-ink-faint"
          >
            {o.over % 5 === 0 || o.over === 1 ? o.over : ""}
          </span>
        ))}
      </div>
      <p className="mt-2 text-2xs leading-relaxed text-ink-faint">
        Taller is better: height is{" "}
        {mode === "batting" ? "strike rate" : "economy, inverted so a cheap over is tall"}. Solid
        bars have the most balls behind them; faint bars have fewer. An outline means fewer than 20
        balls — too few to rate.
      </p>
    </div>
  );
}
