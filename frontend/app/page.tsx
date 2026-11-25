import Link from "next/link";
import { Suspense } from "react";
import { ArrowRight } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { filterQuery, one, type RawParams } from "@/lib/search-params";
import { Section } from "@/components/layout/page-header";
import { Panel, PanelHeader } from "@/components/ui/card";
import { ErrorState, NoDataState } from "@/components/ui/states";
import { Skeleton } from "@/components/ui/skeleton";
import { PitchMotif } from "@/components/ui/pitch-motif";
import { FilterBar } from "@/features/filters/filter-bar";
import { HeroSearch } from "@/features/overview/hero-search";
import { FeaturedInningsCard } from "@/features/overview/featured-innings";
import { StarPlayers } from "@/features/overview/star-players";
import { PartialCoverageNote } from "@/features/overview/partial-coverage";
import { InsightsPanel } from "@/features/overview/insights";
import { Leaderboards } from "@/features/overview/leaderboards";
import { OverviewCharts } from "@/features/overview/charts";
import { CompetitionCard } from "@/components/competitions/competition-card";
import { ResultsList } from "@/components/competitions/results-list";
import { num } from "@/lib/format";
import { cn } from "@/lib/utils";
import type {
  CompetitionType,
  GlobalSummary,
  OverviewPayload,
  PlayerDirectory,
  SeasonMeta,
} from "@/types";

export const metadata = { title: "Cricket intelligence" };

/** Where cricket is played, each with how much of it STRYK holds. */
const HUBS: { href: string; label: string; detail: string; type?: CompetitionType; women?: true }[] = [
  { href: "/leagues", label: "Franchise leagues", detail: "IPL, BBL, PSL, SA20, CPL and more", type: "FRANCHISE_LEAGUE" },
  { href: "/tournaments", label: "ICC tournaments", detail: "World Cups, men's and women's", type: "ICC_TOURNAMENT" },
  { href: "/women", label: "Women's cricket", detail: "WPL, WBBL, The Hundred, World Cups", women: true },
  { href: "/international", label: "International", detail: "Tests, ODIs and T20Is", type: "INTERNATIONAL" },
  { href: "/domestic", label: "Domestic", detail: "County, Shield, Ranji and more", type: "DOMESTIC" },
];

function compactNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  return num(n);
}

/**
 * Home: how much cricket STRYK holds, where to explore it, and a spotlight on
 * one competition at a time. Totals here count matches and deliveries; they
 * never add one competition's statistics to another's.
 */
export default async function HomePage({ searchParams }: { searchParams: RawParams }) {
  let summary: GlobalSummary;
  try {
    summary = await api<GlobalSummary>("/api/summary", { recent: 8 });
  } catch (err) {
    const e = err as ApiError;
    return (
      <Section>
        {e.status === 503 ? <NoDataState /> : <ErrorState title="Could not load STRYK" detail={e.message} />}
      </Section>
    );
  }
  if (summary.matches === 0) {
    return (
      <Section>
        <NoDataState />
      </Section>
    );
  }

  const withData = summary.with_data;
  // The home page shows the headline competitions, not all 130-odd: the rest
  // are a click away in the directory, which is ordered the same way.
  const FEATURED = 16;
  const women = withData.filter((c) => c.gender === "WOMEN");
  const spotlightSlug = one(searchParams, "competition") ?? "ipl";
  const spotlight = withData.find((c) => c.slug === spotlightSlug) ?? withData[0];
  // The switcher offers the same competitions as the grid, plus whichever one
  // is open: a link to a competition outside the top set must still show it as
  // the current choice rather than silently dropping out of its own nav.
  const spotlightOptions = withData.slice(0, FEATURED);
  if (spotlight && !spotlightOptions.some((c) => c.slug === spotlight.slug)) {
    spotlightOptions.push(spotlight);
  }
  const firstYear = summary.first_match?.slice(0, 4);
  const lastYear = summary.last_match?.slice(0, 4);
  const womensMatches = summary.matches_by_gender.WOMEN ?? 0;

  return (
    <>
      <div className="relative overflow-hidden border-b border-line bg-surface-sunken">
        <PitchMotif className="absolute -right-16 -top-6 hidden h-[300px] w-[400px] text-ink-faint/25 lg:block" />
        <div className="relative mx-auto grid max-w-[1600px] gap-10 px-4 pb-10 pt-10 lg:grid-cols-[minmax(0,1fr)_400px] lg:gap-14 lg:px-6 lg:pb-14 lg:pt-16">
          <div className="min-w-0">
            <p className="label-xs">Cricket intelligence</p>
            <h1 className="mt-2 font-display text-3xl font-bold leading-[1.1] tracking-tight text-ink lg:text-[3.25rem]">
              Every ball, across the game&apos;s leagues and World Cups
            </h1>
            <p className="mt-4 max-w-xl text-sm leading-relaxed text-ink-muted lg:text-base">
              Look up any player, team or competition and see what the ball-by-ball record actually
              says. Men&apos;s and women&apos;s cricket, franchise and international, each kept as its own
              record, never pooled.
            </p>
            <div className="mt-7 max-w-xl">
              <HeroSearch
                suggestions={(summary.suggestions ?? []).map((p) => ({ id: p.id, name: p.name, team: null }))}
              />
            </div>
            <dl className="mt-8 grid max-w-xl grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
              {[
                ["Competitions", `${summary.competitions.with_data}`],
                ["Matches", num(summary.matches)],
                ["Deliveries", compactNumber(summary.deliveries)],
                ["Players", num(summary.players)],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt className="label-xs">{label}</dt>
                  <dd className="num mt-1 font-display text-2xl font-semibold text-ink">{value}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-4 max-w-xl text-xs leading-relaxed text-ink-faint">
              {firstYear}–{lastYear}, {num(womensMatches)} of them women&apos;s matches. Every
              statistic is computed from deliveries; nothing is typed in by hand. {summary.competitions.catalogued - summary.competitions.with_data} more
              competitions are catalogued with their data status shown.
            </p>
          </div>

          <aside className="min-w-0 lg:border-l lg:border-line lg:pl-10" aria-label="Explore">
            <p className="label-xs">Explore</p>
            <ul className="mt-3 divide-y divide-line/60 border-y border-line/60">
              {HUBS.map((hub) => {
                const counts = hub.women
                  ? {
                      with_data: summary.competitions.women_with_data,
                      catalogued: summary.competitions.women_catalogued,
                    }
                  : hub.type
                    ? summary.competitions.by_type[hub.type]
                    : undefined;
                return (
                  <li key={hub.href}>
                    <Link
                      href={hub.href}
                      className="group flex items-center justify-between gap-3 py-3 hover:text-accent"
                    >
                      <span className="min-w-0">
                        <span className="block text-sm font-medium text-ink group-hover:text-accent">
                          {hub.label}
                        </span>
                        <span className="block truncate text-2xs text-ink-faint">{hub.detail}</span>
                      </span>
                      <span className="flex shrink-0 items-center gap-2 text-2xs text-ink-faint">
                        {counts ? (
                          <span className="num">
                            {counts.with_data}
                            {typeof counts.catalogued === "number" ? ` of ${counts.catalogued}` : ""} with data
                          </span>
                        ) : null}
                        <ArrowRight className="h-3 w-3" aria-hidden />
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </aside>
        </div>
      </div>

      <Section className="space-y-10">
        <div>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="font-display text-xl font-semibold tracking-tight text-ink">
                Competitions with ball-by-ball data
              </h2>
              <p className="mt-1 text-xs text-ink-muted">
                The {Math.min(FEATURED, withData.length)} most followed, of {withData.length} with data.
              </p>
            </div>
            <Link href="/competitions" className="flex items-center gap-1 text-xs text-accent hover:underline">
              All {summary.competitions.catalogued} competitions <ArrowRight className="h-3 w-3" aria-hidden />
            </Link>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {withData.slice(0, FEATURED).map((c) => (
              <CompetitionCard key={c.slug} competition={c} />
            ))}
          </div>
        </div>
      </Section>

      {spotlight ? (
        <Suspense fallback={<Section><Skeleton className="h-96" /></Section>}>
          <Spotlight
            slug={spotlight.slug}
            name={spotlight.name}
            options={spotlightOptions.map((c) => ({ slug: c.slug, label: c.short_name ?? c.name }))}
            searchParams={searchParams}
          />
        </Suspense>
      ) : null}

      <Section className="space-y-10">
        {women.length ? (
          <div>
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="font-display text-xl font-semibold tracking-tight text-ink">Women&apos;s cricket</h2>
                <p className="mt-1 text-xs text-ink-muted">
                  {women.length} competitions, {num(womensMatches)} matches, analysed exactly as the men&apos;s game is.
                </p>
              </div>
              <Link href="/women" className="flex items-center gap-1 text-xs text-accent hover:underline">
                Women&apos;s cricket hub <ArrowRight className="h-3 w-3" aria-hidden />
              </Link>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {women.map((c) => (
                <Link
                  key={c.slug}
                  href={`/competitions/${c.slug}`}
                  className="rounded border border-signal-info/30 bg-signal-info/5 px-3 py-2 text-xs text-ink hover:border-signal-info/60"
                >
                  {c.name}
                  <span className="num ml-2 text-2xs text-ink-faint">{num(c.coverage.matches)} matches</span>
                </Link>
              ))}
            </div>
          </div>
        ) : null}

        <Panel>
          <PanelHeader title="Latest results" description="The most recent matches in the data, from every competition." />
          <ResultsList matches={summary.latest_results} />
        </Panel>
      </Section>
    </>
  );
}

/**
 * The analytical overview, for one competition at a time. This is the page
 * STRYK's home used to be, now one spotlight among many.
 */
async function Spotlight({
  slug,
  name,
  options,
  searchParams,
}: {
  slug: string;
  name: string;
  options: { slug: string; label: string }[];
  searchParams: RawParams;
}) {
  const params = { ...filterQuery(searchParams), competition: [slug] };
  let data: OverviewPayload;
  let seasons: SeasonMeta[];
  let topBatters: PlayerDirectory;
  let topBowlers: PlayerDirectory;
  try {
    [data, seasons, topBatters, topBowlers] = await Promise.all([
      api<OverviewPayload>("/api/overview", { ...params, limit: 10 }),
      api<SeasonMeta[]>("/api/meta/seasons", { competition: [slug] }),
      api<PlayerDirectory>("/api/players", { ...params, sort: "runs", limit: 8 }),
      api<PlayerDirectory>("/api/players", { ...params, sort: "wickets", limit: 8 }),
    ]);
  } catch (err) {
    return (
      <Section>
        <ErrorState title={`Could not load the ${name} spotlight`} detail={(err as ApiError).message} />
      </Section>
    );
  }
  const s = data.summary;
  // Cumulative lists are a real all-time order only where STRYK holds every
  // season the competition has played; where it does not they are withheld.
  const coverage = data.coverage;
  const cumulativeIsHonest = coverage?.complete !== false;

  return (
    <div id="spotlight" className="scroll-mt-16 border-t border-line bg-surface-sunken/40">
      <Section className="space-y-7">
        <div className="space-y-3">
          <p className="label-xs">Competition spotlight</p>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="font-display text-2xl font-bold tracking-tight text-ink">{name}</h2>
              <p className="mt-1 text-xs text-ink-muted">
                <span className="num">{num(s.matches)}</span> matches,{" "}
                <span className="num">{s.season_range[0]}</span>–<span className="num">{s.season_range[1]}</span>,{" "}
                <span className="num">{num(s.players)}</span> players.
              </p>
            </div>
            <Link href={`/competitions/${slug}`} className="flex items-center gap-1 text-xs text-accent hover:underline">
              Seasons, results and tables <ArrowRight className="h-3 w-3" aria-hidden />
            </Link>
          </div>
          <nav aria-label="Spotlight competition" className="flex flex-wrap gap-1.5">
            {options.map((o) => (
              <Link
                key={o.slug}
                href={`/?competition=${o.slug}#spotlight`}
                scroll={false}
                aria-current={o.slug === slug ? "page" : undefined}
                className={cn(
                  "rounded border px-2 py-1 text-2xs transition-colors",
                  o.slug === slug
                    ? "border-accent/50 bg-accent/10 text-accent"
                    : "border-line-strong text-ink-muted hover:text-ink",
                )}
              >
                {o.label}
              </Link>
            ))}
          </nav>
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
          <div className="min-w-0 space-y-6">
            {cumulativeIsHonest ? (
              <div>
                <h3 className="font-display text-base font-semibold tracking-tight text-ink">Stars of the competition</h3>
                <p className="mt-1 text-xs text-ink-muted">Tap any card for the full ball-by-ball record.</p>
                <div className="mt-3">
                  <StarPlayers
                    batters={topBatters.rows}
                    bowlers={topBowlers.rows}
                    seasonRange={s.season_range}
                    complete={coverage?.complete === true}
                  />
                </div>
              </div>
            ) : (
              <PartialCoverageNote name={name} coverage={coverage!} />
            )}
            {data.featured_innings ? <FeaturedInningsCard innings={data.featured_innings} /> : null}
          </div>
          <aside className="min-w-0">
            <InsightsPanel insights={data.insights} />
          </aside>
        </div>

        {cumulativeIsHonest ? <Leaderboards boards={data.leaderboards} /> : null}

        <div className="space-y-4">
          <div className="max-w-xl">
            <h3 className="font-display text-base font-semibold tracking-tight text-ink">
              How the {name} has changed
            </h3>
            <p className="mt-1.5 text-xs leading-relaxed text-ink-muted">
              Filter by season, phase or innings to narrow every figure below.
            </p>
          </div>
          <FilterBar seasons={seasons} className="rounded-lg border" />
          <OverviewCharts trends={data.trends} distribution={data.distribution} />
        </div>
      </Section>
    </div>
  );
}
