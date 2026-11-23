"use client";

import * as React from "react";
import { Pause, Play, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Replay an innings ball by ball.
 *
 * The strip is a finished scorecard; this lets you watch it happen, with the
 * score climbing as the balls land. It is the nearest this data gets to being
 * a match, and it costs nothing but a timer.
 *
 * Every ball is rendered from the start and the strip is readable whether or
 * not anyone presses play: the balls ahead of the cursor are dimmed rather
 * than hidden, so the innings is never hostage to the animation.
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

const runsOf = (mark: string) => (/^[1-6]$/.test(mark) ? Number(mark) : 0);

export function InningsReplay({
  sequence,
  accent,
  className,
}: {
  sequence: string[];
  /** Franchise colour for the score, so the replay matches the page. */
  accent?: string;
  className?: string;
}) {
  const [cursor, setCursor] = React.useState(sequence.length);
  const [playing, setPlaying] = React.useState(false);

  React.useEffect(() => {
    if (!playing) return;
    if (cursor >= sequence.length) {
      setPlaying(false);
      return;
    }
    const id = setTimeout(() => setCursor((c) => c + 1), 190);
    return () => clearTimeout(id);
  }, [playing, cursor, sequence.length]);

  const start = () => {
    if (cursor >= sequence.length) setCursor(0);
    setPlaying(true);
  };

  const shown = sequence.slice(0, cursor);
  const runs = shown.reduce((a, m) => a + runsOf(m), 0);
  const wickets = shown.filter((m) => m === "W").length;
  const complete = cursor >= sequence.length;

  return (
    <div className={cn("", className)}>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => (playing ? setPlaying(false) : start())}
          className="inline-flex items-center gap-1.5 rounded-full border border-line-strong bg-surface-raised px-3 py-1.5 text-2xs text-ink transition-colors hover:border-accent/60 hover:text-accent"
        >
          {playing ? (
            <>
              <Pause className="h-3 w-3" aria-hidden /> Pause
            </>
          ) : (
            <>
              <Play className="h-3 w-3" aria-hidden /> {complete ? "Replay the innings" : "Resume"}
            </>
          )}
        </button>
        {cursor < sequence.length || playing ? (
          <button
            type="button"
            onClick={() => {
              setPlaying(false);
              setCursor(sequence.length);
            }}
            className="inline-flex items-center gap-1.5 text-2xs text-ink-faint transition-colors hover:text-ink"
          >
            <RotateCcw className="h-3 w-3" aria-hidden /> Show all
          </button>
        ) : null}

        <span className="num ml-auto text-sm" aria-live="polite">
          <span className="font-display text-xl font-bold" style={{ color: accent }}>
            {runs}
            {wickets ? `-${wickets}` : ""}
          </span>
          <span className="ml-1.5 text-2xs text-ink-faint">
            off {shown.length} {shown.length === 1 ? "ball" : "balls"}
          </span>
        </span>
      </div>

      <span className="flex flex-wrap items-center gap-1">
        {sequence.map((mark, i) => {
          const revealed = i < cursor;
          return (
            <span
              key={i}
              aria-hidden
              className={cn(
                "num inline-flex h-5 w-5 items-center justify-center rounded-full text-[0.625rem] font-medium transition-all duration-200",
                STYLES[mark] ?? "bg-ball-dot text-ink-faint",
                revealed ? "opacity-100" : "scale-90 opacity-25",
                playing && i === cursor - 1 && "scale-125",
              )}
            >
              {mark === "." ? "" : mark}
            </span>
          );
        })}
      </span>
    </div>
  );
}
