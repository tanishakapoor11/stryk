import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { one, type RawParams } from "@/lib/search-params";
import { Section } from "@/components/layout/page-header";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { ErrorState, NoDataState } from "@/components/ui/states";
import { TeamCard } from "@/features/teams/team-card";
import { pageMeta } from "@/lib/seo";
import { cn } from "@/lib/utils";
import type { CompetitionCard, CompetitionType, GlobalSummary, TeamSummary } from "@/types";

export const metadata = pageMeta({
  title: "Team Intelligence",
  description:
    "Squad depth, batting order and where each side wins and loses overs, in any competition "
    + "STRYK holds ball-by-ball: franchise leagues, international cricket and domestic competitions.",
  path: "/teams",
});

/** How many competitions the picker offers before "all competitions". */
const FEATURED = 16;

/**
 * What a "team" is depends on the competition. The IPL has franchises; men's
 * Test cricket has nations; the County Championship has counties. A page that
 * says "franchise" everywhere reads as wrong the moment it leaves the IPL.
 */
const NOUN: Record<CompetitionType, { plural: string; current: string; former: string }> = {
  FRANCHISE_LEAGUE: { plural: "franchises", current: "Current franchises", former: "No longer playing" },
  INTERNATIONAL: { plural: "nations", current: "Currently playing", former: "No longer in the record" },
  ICC_TOURNAMENT: { plural: "nations", current: "Currently playing", former: "No longer in the record" },
  DOMESTIC: { plural: "sides", current: "Current sides", former: "No longer playing" },
  REGIONAL: { plural: "nations", current: "Currently playing", former: "No longer in the record" },
  OTHER: { plural: "teams", current: "Currently playing", former: "No longer playing" },
};

export default async function TeamsPage({ searchParams }: { searchParams: RawParams }) {
  // Absent means the API's default competition, which keeps every pre-existing
  // /teams link meaning what it did when STRYK was IPL-only.
  const slug = one(searchParams, "competition") ?? "ipl";

  let teams: TeamSummary[];
  let summary: GlobalSummary;
  try {
    [teams, summary] = await Promise.all([
      api<TeamSummary[]>("/api/meta/teams", { competition: [slug] }),
      api<GlobalSummary>("/api/summary", { recent: 1 }),
    ]);
  } catch (err) {
    const e = err as ApiError;
    return (
      <Section>
        {e.status === 503 ? <NoDataState /> : <ErrorState title="Could not load teams" detail={e.message} />}
      </Section>
    );
  }

  const withData: CompetitionCard[] = summary.with_data ?? [];
  const current = withData.find((c) => c.slug === slug) ?? withData[0];
  // Same set as the home page, plus whichever competition is open, so a link
  // to one outside the top set still shows as the current choice.
  const options = withData.slice(0, FEATURED);
  if (current && !options.some((c) => c.slug === current.slug)) options.push(current);

  const noun = NOUN[current?.type ?? "OTHER"];
  const active = teams.filter((t) => t.active);
  const former = teams.filter((t) => !t.active);

  return (
    <>
      <div className="border-b border-line bg-surface-sunken">
        <div className="mx-auto max-w-[1600px] px-4 pb-8 pt-5 lg:px-6">
          <Breadcrumbs items={[{ label: "Stryk", href: "/" }, { label: "Teams" }]} />
          <h1 className="mt-3 font-display text-3xl font-bold tracking-tight text-ink lg:text-4xl">
            Pick a side
          </h1>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-ink-muted">
            Squad depth, batting order, and where each side actually wins and loses overs.
            A rename is tracked as an alias, so a team&apos;s record stays continuous.
          </p>
          {options.length > 1 ? (
            <nav aria-label="Competition" className="mt-4 flex flex-wrap gap-1.5">
              {options.map((o) => (
                <Link
                  key={o.slug}
                  href={`/teams?competition=${o.slug}`}
                  aria-current={o.slug === current?.slug ? "page" : undefined}
                  className={cn(
                    "rounded border px-2 py-1 text-2xs transition-colors",
                    o.slug === current?.slug
                      ? "border-accent/50 bg-accent/10 text-accent"
                      : "border-line-strong text-ink-muted hover:text-ink",
                  )}
                >
                  {o.short_name ?? o.name}
                </Link>
              ))}
              <Link
                href="/competitions"
                className="rounded border border-line-strong px-2 py-1 text-2xs text-ink-muted hover:text-ink"
              >
                All {summary.competitions?.catalogued ?? ""} competitions
              </Link>
            </nav>
          ) : null}
        </div>
      </div>

      <Section className="space-y-8">
        {current ? (
          <p className="text-xs text-ink-muted">
            {teams.length} {noun.plural} in the{" "}
            <Link href={`/competitions/${current.slug}`} className="text-ink underline hover:text-accent">
              {current.name}
            </Link>
            . Records are never pooled across competitions.
          </p>
        ) : null}

        {teams.length === 0 ? (
          <NoDataState />
        ) : (
          <>
            <div>
              <h2 className="font-display text-base font-semibold tracking-tight text-ink">
                {noun.current}
              </h2>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {active.map((t) => (
                  <TeamCard key={t.id} team={t} competition={current?.slug} />
                ))}
              </div>
            </div>

            {former.length ? (
              <div>
                <h2 className="font-display text-base font-semibold tracking-tight text-ink">
                  {noun.former}
                </h2>
                <p className="mt-1 text-xs text-ink-muted">
                  No match in the most recent indexed season.
                </p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {former.map((t) => (
                    <TeamCard key={t.id} team={t} competition={current?.slug} />
                  ))}
                </div>
              </div>
            ) : null}
          </>
        )}
      </Section>
    </>
  );
}
