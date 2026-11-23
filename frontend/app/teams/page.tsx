import { api, ApiError } from "@/lib/api";
import { Section } from "@/components/layout/page-header";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { ErrorState, NoDataState } from "@/components/ui/states";
import { TeamCard } from "@/features/teams/team-card";
import type { TeamSummary } from "@/types";

export const metadata = { title: "Team Intelligence" };

export default async function TeamsPage() {
  let teams: TeamSummary[];
  try {
    teams = await api<TeamSummary[]>("/api/meta/teams");
  } catch (err) {
    const e = err as ApiError;
    return (
      <Section>
        {e.status === 503 ? <NoDataState /> : <ErrorState title="Could not load teams" detail={e.message} />}
      </Section>
    );
  }

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
            Squad depth, batting order, and where each franchise actually wins and loses overs.
            A rename is tracked as an alias, so a club&apos;s record stays continuous.
          </p>
        </div>
      </div>

      <Section className="space-y-8">
        <div>
          <h2 className="font-display text-base font-semibold tracking-tight text-ink">
            Current franchises
          </h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {active.map((t) => (
              <TeamCard key={t.id} team={t} />
            ))}
          </div>
        </div>

        {former.length ? (
          <div>
            <h2 className="font-display text-base font-semibold tracking-tight text-ink">
              No longer playing
            </h2>
            <p className="mt-1 text-xs text-ink-muted">
              Franchises with no match in the most recent indexed season.
            </p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {former.map((t) => (
                <TeamCard key={t.id} team={t} />
              ))}
            </div>
          </div>
        ) : null}
      </Section>
    </>
  );
}
