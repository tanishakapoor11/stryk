import { Database } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { COVERAGE_EXPLAINER, COVERAGE_TONE } from "@/lib/competitions";
import { cn } from "@/lib/utils";
import type { CoverageStatus } from "@/types";

/**
 * How much of a competition, season or match STRYK actually holds.
 *
 * Shown wherever a statistic could otherwise be mistaken for a complete
 * record: a reader should never have to guess whether a blank means zero, not
 * applicable, or simply not imported.
 */
export function CoverageBadge({
  status,
  label,
  className,
}: {
  status: CoverageStatus;
  label: string;
  className?: string;
}) {
  return (
    <Badge tone={COVERAGE_TONE[status]} className={className} title={COVERAGE_EXPLAINER[status]}>
      <Database className="h-2.5 w-2.5" aria-hidden />
      {label}
    </Badge>
  );
}

/** The same information as a sentence, for panels that have the room. */
export function CoverageNote({
  status,
  detail,
  className,
}: {
  status: CoverageStatus;
  detail?: string | null;
  className?: string;
}) {
  return (
    <p className={cn("text-xs leading-relaxed text-ink-muted", className)}>
      {detail ?? COVERAGE_EXPLAINER[status]}
    </p>
  );
}
