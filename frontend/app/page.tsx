import { Suspense } from "react";
import { api, ApiError } from "@/lib/api";
import { filterQuery, type RawParams } from "@/lib/search-params";
import { Section } from "@/components/layout/page-header";
import { ErrorState, NoDataState } from "@/components/ui/states";
import { Skeleton } from "@/components/ui/skeleton";
import { FilterBar } from "@/features/filters/filter-bar";
import { HeroSearch } from "@/features/overview/hero-search";
import { FeaturedInningsCard } from "@/features/overview/featured-innings";
import { StarPlayers } from "@/features/overview/star-players";
import { PitchMotif } from "@/components/ui/pitch-motif";
import { InsightsPanel } from "@/features/overview/insights";
import { Leaderboards } from "@/features/overview/leaderboards";
import { OverviewCharts } from "@/features/overview/charts";
import { num } from "@/lib/format";
import type { OverviewPayload, PlayerDirectory, SeasonMeta } from "@/types";

export const metadata = { title: "Overview" };

export default async function OverviewPage({ searchParams }: { searchParams: RawParams }) {
  let data: OverviewPayload;
  let seasons: SeasonMeta[];
  // The directory is used rather than the leaderboard for the star row: it
  // carries each player's franchise, which is what makes the cards theirs.
  let topBatters: PlayerDirectory;
  let topBowlers: PlayerDirectory;
  try {
    [data, seasons, topBatters, topBowlers] = await Promise.all([
      api<OverviewPayload>("/api/overview", { ...filterQuery(searchParams), limit: 10 }),
      api<SeasonMeta[]>("/api/meta/seasons"),
      api<PlayerDirectory>("/api/players", { ...filterQuery(searchParams), sort: "runs", limit: 8 }),
      api<PlayerDirectory>("/api/players", { ...filterQuery(searchParams), sort: "wickets", limit: 8 }),
    ]);
  } catch (err) {
    const e = err as ApiError;
    return (
      <Section>
        {e.status === 503 ? (
          <NoDataState />
        ) : (
          <ErrorState title="Could not load the overview" detail={e.message} />
        )}
      </Section>
    );
  }

  const s = data.summary;
  // Familiar names make better examples than a random sample: these are the
  // players most people arrive looking for.
  const suggestions = [
    ...data.leaderboards.most_runs.slice(0, 3),
    ...data.leaderboards.most_wickets.slice(0, 2),
  ]
    .filter((p) => p.player_id)
    .map((p) => ({ id: p.player_id as string, name: p.player_name as string }));

  return (
    <>
      <div className="relative overflow-hidden border-b border-line bg-surface-sunken">
        {/* Atmosphere only. In the brand orange this needs to sit far further
            back than it did in amber, or it reads as stray marks rather than
            texture. */}
        <PitchMotif className="absolute -right-16 -top-6 hidden h-[300px] w-[400px] text-ink-faint/25 lg:block" />
        <div className="relative mx-auto grid max-w-[1600px] gap-10 px-4 pb-10 pt-10 lg:grid-cols-[minmax(0,1fr)_380px] lg:gap-14 lg:px-6 lg:pb-14 lg:pt-16">
          <div className="min-w-0">
            <h1 className="font-display text-3xl font-bold leading-[1.1] tracking-tight text-ink lg:text-[3.25rem]">
              Every ball of the IPL, since 2008
            </h1>
            <p className="mt-4 max-w-xl text-sm leading-relaxed text-ink-muted lg:text-base">
              Look up any player to see how they actually score: when in the innings, under
              what pressure, and against the bowlers who trouble them.
            </p>
            <div className="mt-7 max-w-xl">
              <HeroSearch suggestions={suggestions} />
            </div>
            <p className="mt-8 max-w-xl text-xs leading-relaxed text-ink-faint">
              <span className="num">{num(s.matches)}</span> matches and{" "}
              <span className="num">{num(s.deliveries)}</span> deliveries from{" "}
              <span className="num">{s.season_range[0]}</span> to{" "}
              <span className="num">{s.season_range[1]}</span>, covering{" "}
              <span className="num">{num(s.players)}</span> players at{" "}
              <span className="num">{s.venues}</span> grounds. Nothing here is typed in by hand.
            </p>

            {data.featured_innings ? (
              <div className="mt-7">
                <FeaturedInningsCard innings={data.featured_innings} />
              </div>
            ) : null}
          </div>

          {/* The fan-facing half: real findings to read before deciding what to
              search for, and the ball notation the rest of the site uses. */}
          <aside className="min-w-0 lg:border-l lg:border-line lg:pl-10">
            <InsightsPanel insights={data.insights} />
          </aside>
        </div>
      </div>

      <Section className="space-y-7">
        <div>
          <h2 className="font-display text-xl font-semibold tracking-tight text-ink">
            Stars of the league
          </h2>
          <p className="mt-1 text-xs text-ink-muted">
            Tap any card for the full ball-by-ball record.
          </p>
          <div className="mt-4">
            <StarPlayers batters={topBatters.rows} bowlers={topBowlers.rows} />
          </div>
        </div>

        <Suspense fallback={<Skeleton className="h-96" />}>
          <Leaderboards boards={data.leaderboards} />
        </Suspense>

      </Section>

      <div className="border-t border-line">
        <Section className="space-y-4">
          <div className="max-w-xl">
            <h2 className="font-display text-xl font-semibold tracking-tight text-ink">
              How the league has changed
            </h2>
            <p className="mt-1.5 text-xs leading-relaxed text-ink-muted">
              Filter by season, phase or innings to narrow every figure below. The filters carry
              into the player and team pages too.
            </p>
          </div>
          <FilterBar seasons={seasons} className="rounded-lg border" />
          <OverviewCharts trends={data.trends} distribution={data.distribution} />
        </Section>
      </div>
    </>
  );
}
