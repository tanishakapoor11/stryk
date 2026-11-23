import * as React from "react";
import { AlertTriangle, CheckCircle2, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Matchup } from "@/types";

/**
 * Sample size is the headline, not a footnote.
 *
 * Head-to-head records in T20 are small by construction — a batter rarely
 * faces one bowler more than a few overs across a career — so the banner sits
 * above the numbers rather than beneath them.
 */
const TONE = {
  none: {
    icon: AlertTriangle,
    cls: "border-signal-down/30 bg-signal-down/5 text-signal-down",
    label: "No deliveries",
  },
  insufficient: {
    icon: AlertTriangle,
    cls: "border-signal-down/30 bg-signal-down/5 text-signal-down",
    label: "Sample too small",
  },
  indicative: {
    icon: Info,
    cls: "border-signal-warn/30 bg-signal-warn/5 text-signal-warn",
    label: "Indicative only",
  },
  readable: {
    icon: CheckCircle2,
    cls: "border-accent/30 bg-accent/5 text-accent",
    label: "Readable sample",
  },
} as const;

export function ReliabilityBanner({ matchup }: { matchup: Matchup }) {
  const tone = TONE[matchup.reliability.level] ?? TONE.indicative;
  const Icon = tone.icon;
  return (
    <div className={cn("flex items-start gap-2.5 border px-4 py-3", tone.cls)}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="min-w-0">
        <p className="text-xs font-medium">{tone.label}</p>
        <p className="mt-0.5 text-xs leading-relaxed text-ink-muted">
          {matchup.reliability.message}
        </p>
        <p className="mt-1 text-2xs text-ink-faint">
          {matchup.sample.balls} balls across {matchup.sample.innings} innings in{" "}
          {matchup.sample.matches} matches. A head-to-head is read as evidence only at{" "}
          {String((matchup.notes.thresholds as any)?.reliable_balls ?? 30)}+ balls.
        </p>
      </div>
    </div>
  );
}
