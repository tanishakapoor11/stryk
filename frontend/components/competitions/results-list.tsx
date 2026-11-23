import { Badge } from "@/components/ui/badge";
import { shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { MatchRow } from "@/types";

/** Completed matches, newest first. Winner in full ink, loser muted. */
export function ResultsList({ matches, className }: { matches: MatchRow[]; className?: string }) {
  if (!matches.length) {
    return <p className="px-4 py-6 text-xs text-ink-muted">No completed matches in the data.</p>;
  }
  return (
    <ul className={cn("divide-y divide-line/60", className)}>
      {matches.map((m) => {
        const side = (t: MatchRow["team1"]) => (
          <span
            className={cn(
              "truncate",
              m.winner_id === t.id ? "font-medium text-ink" : "text-ink-muted",
            )}
            title={t.name}
          >
            {t.short_name ?? t.name}
          </span>
        );
        return (
          <li key={m.id} className="grid gap-1 px-4 py-2.5 sm:grid-cols-[88px_minmax(0,1fr)_auto] sm:items-center sm:gap-4">
            <span className="num text-2xs text-ink-faint">{shortDate(m.date)}</span>
            <div className="min-w-0">
              <p className="flex min-w-0 items-center gap-1.5 text-sm">
                {side(m.team1)}
                <span className="text-2xs text-ink-faint">v</span>
                {side(m.team2)}
              </p>
              <p className="truncate text-xs text-ink-muted">
                {m.result}
                {m.venue ? <span className="text-ink-faint"> · {m.venue.city ?? m.venue.name}</span> : null}
              </p>
            </div>
            <div className="flex gap-1.5">
              {m.competition ? (
                <a
                  href={`/competitions/${m.competition.slug}`}
                  className="rounded border border-line-strong px-1.5 py-0.5 text-2xs text-ink-muted hover:text-accent"
                  title={m.competition.name}
                >
                  {m.competition.short_name ?? m.competition.name}
                </a>
              ) : null}
              {m.stage && m.stage_type !== "league" ? (
                <Badge tone={m.stage_type === "knockout" ? "accent" : "default"}>{m.stage}</Badge>
              ) : m.match_number ? (
                <span className="num text-2xs text-ink-faint">Match {m.match_number}</span>
              ) : null}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
