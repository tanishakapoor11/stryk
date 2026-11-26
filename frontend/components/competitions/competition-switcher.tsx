import Link from "next/link";
import { GENDER_LABEL } from "@/lib/competitions";
import { cn } from "@/lib/utils";
import type { EntityCompetition } from "@/types";

/**
 * Which competition a profile is showing, and the others the player or team
 * has a record in. Records are never pooled across competitions, so switching
 * is explicit rather than hidden behind an "all cricket" total.
 */
export function CompetitionSwitcher({
  options,
  current,
  basePath,
  label = "Showing",
  singleAsText = true,
}: {
  options: EntityCompetition[];
  current: string | undefined;
  /** May already carry a query string; the competition is appended to it. */
  basePath: string;
  label?: string;
  /**
   * A profile with one competition states it in a sentence — a toggle with
   * nothing to toggle to is noise. Where the single option is itself the
   * finding, as on the comparison page, pass false to keep the chip.
   */
  singleAsText?: boolean;
}) {
  if (options.length < 2 && singleAsText) {
    const only = options[0];
    return only ? (
      <p className="text-2xs text-ink-faint">
        Record from the{" "}
        <Link href={`/competitions/${only.slug}`} className="text-ink-muted underline hover:text-accent">
          {only.name}
        </Link>{" "}
        ({only.matches} matches, {GENDER_LABEL[only.gender].toLowerCase()}&apos;s {only.format}).
      </p>
    ) : null;
  }
  return (
    <nav aria-label="Competition" className="flex flex-wrap items-center gap-1.5">
      <span className="label-xs mr-1">{label}</span>
      {options.map((o) => {
        const active = o.slug === current;
        return (
          <Link
            key={o.slug}
            href={`${basePath}${basePath.includes("?") ? "&" : "?"}competition=${o.slug}`}
            aria-current={active ? "page" : undefined}
            className={cn(
              "rounded border px-2 py-1 text-2xs transition-colors",
              active
                ? "border-accent/50 bg-accent/10 text-accent"
                : "border-line-strong text-ink-muted hover:text-ink",
            )}
            title={`${o.name}: ${o.matches} matches, ${o.first_match.slice(0, 4)}–${o.last_match.slice(0, 4)}`}
          >
            {o.short_name ?? o.name} <span className="num text-ink-faint">{o.matches}</span>
          </Link>
        );
      })}
    </nav>
  );
}
