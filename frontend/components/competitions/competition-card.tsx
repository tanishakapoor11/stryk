import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { CoverageBadge } from "./coverage-badge";
import { GENDER_LABEL, SEASON_STATUS_LABEL, TYPE_LABEL } from "@/lib/competitions";
import { num } from "@/lib/format";
import type { CompetitionCard as Card } from "@/types";

/** One competition in a directory grid. Every card links to the same reusable page. */
export function CompetitionCard({ competition: c }: { competition: Card }) {
  const hasData = c.coverage.matches > 0;
  return (
    <Link
      href={`/competitions/${c.slug}`}
      className="group flex flex-col gap-3 border border-line bg-surface p-4 shadow-raise transition-colors hover:border-accent/40 focus-visible:border-accent focus-visible:outline-none"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="label-xs truncate">
            {c.country ? (
              <>
                {c.country.flag ? <span aria-hidden>{c.country.flag} </span> : null}
                {c.country.name}
              </>
            ) : (
              "International"
            )}
          </p>
          <h3 className="mt-1 font-display text-base font-semibold leading-snug tracking-tight text-ink group-hover:text-accent">
            {c.name}
          </h3>
        </div>
        {c.short_name && c.short_name !== c.name ? (
          <span className="num shrink-0 rounded border border-line-strong px-1.5 py-0.5 text-2xs text-ink-muted">
            {c.short_name}
          </span>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-1.5">
        <Badge>{TYPE_LABEL[c.type]}</Badge>
        <Badge tone={c.gender === "WOMEN" ? "info" : "default"}>{GENDER_LABEL[c.gender]}</Badge>
        {c.formats.map((f) => (
          <Badge key={f}>{f}</Badge>
        ))}
        {!c.is_active ? <Badge tone="warn">No longer played</Badge> : null}
        {!c.is_catalogued ? <Badge tone="warn">Uncatalogued</Badge> : null}
      </div>

      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
        <CoverageBadge status={c.coverage.status} label={c.coverage.label} />
        {hasData && c.latest_season ? (
          <span className="text-2xs text-ink-faint">
            <span className="num">{num(c.coverage.matches)}</span> matches · latest{" "}
            <span className="num">{c.latest_season.name}</span> (
            {SEASON_STATUS_LABEL[c.latest_season.status].toLowerCase()})
          </span>
        ) : (
          <span className="text-2xs text-ink-faint">No matches imported</span>
        )}
      </div>
    </Link>
  );
}
