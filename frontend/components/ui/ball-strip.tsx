import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * The ball-by-ball strip.
 *
 * Every cricket follower reads this without being taught: a dot is a dot, a
 * digit is runs off the bat, W is out. It is the one place in the product
 * where the raw ball-by-ball data is shown as itself, and it is the reason
 * this dataset is worth having at all.
 *
 * Symbols come from the API (app/analytics/players.py) and always number
 * exactly the balls faced in that innings.
 */
const STYLES: Record<string, string> = {
  ".": "bg-ball-dot text-ink-faint",
  "1": "bg-ball-run/25 text-ink-muted",
  "2": "bg-ball-run/35 text-ink-muted",
  "3": "bg-ball-run/45 text-ink",
  "4": "bg-ball-four/25 text-ball-four",
  "5": "bg-ball-four/25 text-ball-four",
  "6": "bg-ball-six/25 text-ball-six",
  W: "bg-ball-wicket/25 text-ball-wicket",
  "+": "bg-ball-extra/20 text-ball-extra",
};

export function BallStrip({
  sequence,
  className,
}: {
  sequence: string[];
  className?: string;
}) {
  if (!sequence.length) return null;
  return (
    <span className={cn("flex flex-wrap items-center gap-1", className)} role="img"
      aria-label={`Ball by ball: ${sequence.join(", ").replace(/\./g, "dot").replace(/W/g, "out")}`}>
      {sequence.map((mark, i) => (
        <span
          key={i}
          aria-hidden
          className={cn(
            "num inline-flex h-5 w-5 items-center justify-center rounded-full text-[0.625rem] font-medium",
            STYLES[mark] ?? "bg-ball-dot text-ink-faint",
          )}
        >
          {mark === "." ? "" : mark}
        </span>
      ))}
    </span>
  );
}

/** Legend, shown once per page rather than beside every strip. */
export function BallStripLegend({ className }: { className?: string }) {
  const items: Array<[string, string]> = [
    [".", "dot"],
    ["1", "runs off the bat"],
    ["4", "four"],
    ["6", "six"],
    ["W", "out"],
    ["+", "extras only"],
  ];
  return (
    <span className={cn("flex flex-wrap items-center gap-x-3 gap-y-1.5", className)}>
      {items.map(([mark, label]) => (
        <span key={mark} className="flex items-center gap-1.5 text-2xs text-ink-faint">
          <span
            aria-hidden
            className={cn(
              "num inline-flex h-4 w-4 items-center justify-center rounded-full text-[0.5625rem]",
              STYLES[mark],
            )}
          >
            {mark === "." ? "" : mark}
          </span>
          {label}
        </span>
      ))}
    </span>
  );
}
