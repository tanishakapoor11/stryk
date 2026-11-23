import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { filterQuery, describeFilters, one, type RawParams } from "@/lib/search-params";
import { PageHeader, Section } from "@/components/layout/page-header";
import { Panel, PanelHeader } from "@/components/ui/card";
import { ErrorState, NoDataState } from "@/components/ui/states";
import { FilterBar } from "@/features/filters/filter-bar";
import { SearchBox } from "@/features/players/search-box";
import { DirectoryTable, Pager, withParam } from "@/features/players/directory";
import { cn } from "@/lib/utils";
import type { PlayerDirectory, SeasonMeta, TeamSummary } from "@/types";

export const metadata = { title: "Player Intelligence" };

const ROLES = ["Batter", "Bowler", "All-rounder"];
const PAGE_SIZE = 50;

export default async function PlayersPage({ searchParams }: { searchParams: RawParams }) {
  const role = one(searchParams, "role");
  const sort = one(searchParams, "sort") ?? "runs";
  const order = one(searchParams, "order") ?? (sort === "name" || sort === "economy" ? "asc" : "desc");
  const offset = Number(one(searchParams, "offset") ?? 0) || 0;

  let data: PlayerDirectory;
  let seasons: SeasonMeta[];
  let teams: TeamSummary[];
  try {
    [data, seasons, teams] = await Promise.all([
      api<PlayerDirectory>("/api/players", {
        ...filterQuery(searchParams),
        q: one(searchParams, "q"),
        role,
        sort,
        order,
        limit: PAGE_SIZE,
        offset,
      }),
      api<SeasonMeta[]>("/api/meta/seasons"),
      api<TeamSummary[]>("/api/meta/teams"),
    ]);
  } catch (err) {
    const e = err as ApiError;
    return (
      <Section>
        {e.status === 503 ? <NoDataState /> : <ErrorState title="Could not load players" detail={e.message} />}
      </Section>
    );
  }

  return (
    <>
      <PageHeader
        title="Player Intelligence"
        subtitle="Every player who has faced or bowled a delivery in the indexed IPL matches. Averages are blank, not zero, where a player has never been dismissed or has never bowled."
        crumbs={[{ label: "Stryk", href: "/" }, { label: "Players" }]}
        meta={<span className="text-2xs text-ink-faint">{describeFilters(searchParams)}</span>}
      />
      <FilterBar seasons={seasons} teams={teams} show={["season", "team", "phase", "innings"]} />

      <Section>
        <Panel>
          <PanelHeader
            title="Directory"
            description="Search by name, narrow by role, then sort any column. The URL carries every choice, so an analysis is a link."
            action={
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1">
                  <RoleChip params={searchParams} value={null} active={!role}>
                    All
                  </RoleChip>
                  {ROLES.map((r) => (
                    <RoleChip key={r} params={searchParams} value={r} active={role === r}>
                      {r}
                    </RoleChip>
                  ))}
                </div>
                <SearchBox className="w-52" />
              </div>
            }
          />
          <DirectoryTable data={data} params={searchParams} />
          <Pager data={data} params={searchParams} />
        </Panel>
      </Section>
    </>
  );
}

function RoleChip({
  params,
  value,
  active,
  children,
}: {
  params: RawParams;
  value: string | null;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={withParam(params, { role: value, offset: null })}
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
