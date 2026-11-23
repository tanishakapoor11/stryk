import * as React from "react";
import { cn } from "@/lib/utils";
import type { PlayerHighlight } from "@/types";

/**
 * Plain-language reads on a player: a sentence before a table.
 *
 * Each one is computed from the player's own splits and carries the figure it
 * came from, so a casual reader gets the gist and a careful one can check it
 * against the numbers further down the page.
 */
export function Reads({ reads, className }: { reads: PlayerHighlight[]; className?: string }) {
  if (!reads?.length) return null;
  return (
    <div className={cn("flex flex-wrap gap-2", className)}>
      {reads.map((r, i) => (
        <span
          key={i}
          className={cn(
            "inline-flex items-baseline gap-2 rounded-lg border px-3 py-1.5",
            r.tone === "watch"
              ? "border-signal-warn/25 bg-signal-warn/5"
              : "border-signal-up/25 bg-signal-up/5",
          )}
        >
          <span className="text-[0.8125rem] font-medium text-ink">{r.text}</span>
          <span className="num text-2xs text-ink-muted">{r.figure}</span>
        </span>
      ))}
    </div>
  );
}
