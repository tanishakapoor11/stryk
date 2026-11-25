import Link from "next/link";
import { notFound } from "next/navigation";
import { pageMeta } from "@/lib/seo";
import { CalendarX } from "lucide-react";
import { apiOrNull, ApiError } from "@/lib/api";
import { PageHeader, Section } from "@/components/layout/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { CoverageBadge } from "@/components/competitions/coverage-badge";
import { ResultsList } from "@/components/competitions/results-list";
import { StandingsTable } from "@/components/competitions/standings-table";
import { Leaderboards } from "@/features/overview/leaderboards";
import { GENDER_LABEL, SEASON_STATUS_LABEL, seasonSlug } from "@/lib/competitions";
import { shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { CompetitionDetail, MatchRow, Paged, SeasonDetail } from "@/types";

export async function generateMetadata({ params }: { params: { slug: string; season: string } }) {
  // Raised here so an unknown season is a real 404 (see app/players/[id]/page.tsx).
  let s: SeasonDetail | null;
  try {
    s = await apiOrNull<SeasonDetail>(`/api/competitions/${params.slug}/seasons/${params.season}`);
  } catch {
    return { title: "Season" };
  }
  if (!s) notFound();
  const name = `${s.competition.short_name ?? s.competition.name} ${s.season.name}`;
  return pageMeta({
    title: name,
    description:
      `${s.competition.name} ${s.season.name}: table, results and leading run-scorers and `
      + `wicket-takers, every figure computed from the deliveries bowled.`,
    path: `/competitions/${params.slug}/${params.season}`,
  });
}

/**
 * One page for every season of every competition. Sections appear only when
 * the season has them: no standings without a points system, no knockout
 * bracket for a pure league, no fixtures the source does not publish.
 */
export default async function SeasonPage({ params }: { params: { slug: string; season: string } }) {
  let detail: SeasonDetail | null;
  let competition: CompetitionDetail | null;
  let results: Paged<MatchRow> | null;
  try {
    [detail, competition, results] = await Promise.all([
      apiOrNull<SeasonDetail>(`/api/competitions/${params.slug}/seasons/${params.season}`),
      apiOrNull<CompetitionDetail>(`/api/competitions/${params.slug}`),
      apiOrNull<Paged<MatchRow>>(`/api/competitions/${params.slug}/seasons/${params.season}/results`, {
        limit: 500,
      }),
    ]);
  } catch (err) {
    return (
      <Section>
        <ErrorState title="Could not load this season" detail={(err as ApiError).message} />
      </Section>
    );
  }
  if (!detail || !competition || !results) notFound();
  const { season: s, competition: c } = detail;
  const seasons = competition.seasons;
  const index = seasons.findIndex((x) => x.id === s.id);
  const newer = index > 0 ? seasons[index - 1] : null;
  const older = index >= 0 && index < seasons.length - 1 ? seasons[index + 1] : null;
  const hasKnockouts = detail.knockouts.length > 0;

  return (
    <>
      <PageHeader
        crumbs={[
          { label: "Stryk", href: "/" },
          { label: c.short_name ?? c.name, href: `/competitions/${c.slug}` },
          { label: s.name },
        ]}
        title={`${c.name} ${s.name}`}
        subtitle={`${s.start_date ? shortDate(s.start_date) : ""} – ${s.end_date ? shortDate(s.end_date) : ""} · ${
          s.matches
        } matches in the data`}
        meta={
          <>
            <Badge tone={s.status === "completed" ? "default" : "info"}>{SEASON_STATUS_LABEL[s.status]}</Badge>
            {s.format ? <Badge>{s.format}</Badge> : <Badge tone="warn">Mixed formats</Badge>}
            <Badge tone={c.gender === "WOMEN" ? "info" : "default"}>{GENDER_LABEL[c.gender]}</Badge>
            <CoverageBadge status={detail.coverage.status} label={detail.coverage.label} />
          </>
        }
        actions={
          <nav aria-label="Other seasons" className="flex items-center gap-2 text-xs">
            {older ? (
              <Link href={`/competitions/${c.slug}/${seasonSlug(older.name)}`} className="text-ink-muted hover:text-accent">
                ← {older.name}
              </Link>
            ) : null}
            {newer ? (
              <Link href={`/competitions/${c.slug}/${seasonSlug(newer.name)}`} className="text-ink-muted hover:text-accent">
                {newer.name} →
              </Link>
            ) : null}
          </nav>
        }
      />

      <Section className="space-y-5">
        {detail.stages.length > 1 ? (
          <div className="flex flex-wrap gap-1.5" aria-label="Stages">
            {detail.stages.map((st) => (
              <span
                key={st.id}
                className={cn(
                  "rounded border px-2 py-1 text-2xs",
                  st.type === "knockout" ? "border-accent/40 text-accent" : "border-line-strong text-ink-muted",
                )}
              >
                {st.name} <span className="num text-ink-faint">{st.matches}</span>
              </span>
            ))}
          </div>
        ) : null}

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
          <div className="min-w-0 space-y-5">
            <Panel>
              <PanelHeader
                title="Standings"
                description="Computed from results under this competition's own points rules."
              />
              <StandingsTable standings={detail.standings} />
            </Panel>

            {hasKnockouts ? (
              <Panel>
                <PanelHeader title="Knockouts" description="Playoff and knockout matches, latest first." />
                <ResultsList matches={detail.knockouts} />
              </Panel>
            ) : null}

            {detail.leaders ? (
              <div>
                <h2 className="mb-2 font-display text-base font-semibold tracking-tight text-ink">Season leaders</h2>
                <Leaderboards boards={detail.leaders} />
              </div>
            ) : null}
          </div>

          <aside className="min-w-0 space-y-5">
            <Panel>
              <PanelHeader title="Results" description={`${results.total} matches`} />
              <div className="max-h-[720px] overflow-auto">
                <ResultsList matches={results.items} />
              </div>
            </Panel>
            <Panel>
              <PanelHeader title="Fixtures" />
              <PanelBody>
                <EmptyState icon={CalendarX} title="No fixtures available" detail={detail.fixtures.reason} className="py-4" />
              </PanelBody>
            </Panel>
          </aside>
        </div>
      </Section>
    </>
  );
}
