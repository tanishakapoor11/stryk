import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { filterQuery, describeFilters, one, type RawParams } from "@/lib/search-params";
import { PageHeader, Section } from "@/components/layout/page-header";
import { Panel, PanelHeader } from "@/components/ui/card";
import { ErrorState, NoDataState } from "@/components/ui/states";
import { FilterBar } from "@/features/filters/filter-bar";
import { SearchBox } from "@/features/players/search-box";
import { withParam } from "@/features/players/directory";
import { SquadBuilder, PoolTable } from "@/features/auction/squad-builder";
import { MethodNotes } from "@/features/players/method-notes";
import { photoFor } from "@/lib/photos";
import { cn } from "@/lib/utils";
import type { AuctionPool, SeasonMeta } from "@/types";

export const metadata = { title: "Auction Intelligence" };

const ROLES = ["Batter", "Bowler", "All-rounder"];
const SORTS = [
  { key: "batting_impact", label: "Batting impact" },
  { key: "batting_impact_per_match", label: "Batting / match" },
  { key: "bowling_impact", label: "Runs saved" },
  { key: "bowling_impact_per_match", label: "Runs saved / match" },
  { key: "wickets", label: "Wickets" },
  { key: "strike_rate", label: "Strike rate" },
  { key: "economy", label: "Economy" },
];

export default async function AuctionPage({ searchParams }: { searchParams: RawParams }) {
  const role = one(searchParams, "role");
  const sort = one(searchParams, "sort") ?? "batting_impact";

  let pool: AuctionPool;
  let seasons: SeasonMeta[];
  try {
    [pool, seasons] = await Promise.all([
      api<AuctionPool>("/api/auction/pool", {
        ...filterQuery(searchParams),
        q: one(searchParams, "q"),
        role,
        sort,
        limit: 60,
      }),
      api<SeasonMeta[]>("/api/meta/seasons"),
    ]);
  } catch (err) {
    const e = err as ApiError;
    return (
      <Section>
        {e.status === 503 ? <NoDataState /> : <ErrorState title="Could not load the auction pool" detail={e.message} />}
      </Section>
    );
  }

  // Resolved here because the squad builder runs on the client.
  const photos = Object.fromEntries(
    pool.rows
      .map((r) => [r.player_id, photoFor(r.player_id)?.src])
      .filter((entry): entry is [string, string] => Boolean(entry[1])),
  );

  return (
    <>
      <PageHeader
        title="Auction Intelligence"
        subtitle="Candidate evaluation and hypothetical squad construction. Impact is measured against what the league scored off the same deliveries in the same phases — it is a measure of contribution, never a valuation or a price."
        crumbs={[{ label: "Stryk", href: "/" }, { label: "Auction" }]}
        meta={
          <span className="text-2xs text-ink-faint">
            {describeFilters(searchParams)} · {pool.total} qualifying candidates
          </span>
        }
      />
      <FilterBar seasons={seasons} show={["season", "phase", "innings"]} />

      <Section className="space-y-4">
        <SquadBuilder pool={pool} photos={photos} />

        <Panel>
          <PanelHeader
            title="Candidate pool"
            description="Narrow the pool by season above to evaluate a player's recent form rather than their whole career — a 2010 contribution does not buy a 2026 squad anything."
            action={
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex items-center gap-1">
                  <Chip params={searchParams} k="role" value={null} active={!role}>
                    All roles
                  </Chip>
                  {ROLES.map((r) => (
                    <Chip key={r} params={searchParams} k="role" value={r} active={role === r}>
                      {r}
                    </Chip>
                  ))}
                </div>
                <div className="flex items-center gap-1">
                  {SORTS.map((s) => (
                    <Chip
                      key={s.key}
                      params={searchParams}
                      k="sort"
                      value={s.key}
                      active={sort === s.key}
                    >
                      {s.label}
                    </Chip>
                  ))}
                </div>
                <SearchBox className="w-44" placeholder="Search pool…" />
              </div>
            }
          />
          <PoolTable pool={pool} photos={photos} />
        </Panel>

        <MethodNotes
          metrics={pool.method}
          qualification={pool.qualification}
          notes={
            <>
              <p>{pool.price_note}</p>
              <p className="mt-2">
                Impact is a <em>total</em>, so it rewards longevity: use the per-match column, or
                filter to recent seasons, when comparing a ten-year career against a two-year one.
                Neither column is a ranking — a bowler who saves runs and a batter who scores them
                are not on the same scale, and Stryk does not combine them into a single number,
                because doing so needs an assumption about what a wicket is worth that the data
                cannot supply.
              </p>
              <p className="mt-2">
                Overseas-player limits are not enforced: nationality is absent from Cricsheet
                ball-by-ball files, as noted on every{" "}
                <Link href="/teams" className="text-accent hover:underline">
                  team page
                </Link>
                .
              </p>
            </>
          }
        />
      </Section>
    </>
  );
}

function Chip({
  params,
  k,
  value,
  active,
  children,
}: {
  params: RawParams;
  k: string;
  value: string | null;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={withParam(params, { [k]: value })}
      scroll={false}
      className={cn(
        "rounded border px-1.5 py-0.5 text-2xs transition-colors",
        active
          ? "border-accent/60 bg-accent/15 text-accent"
          : "border-line-strong text-ink-muted hover:border-accent/40 hover:text-ink",
      )}
    >
      {children}
    </Link>
  );
}
