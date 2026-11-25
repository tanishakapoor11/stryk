import Link from "next/link";
import { notFound } from "next/navigation";
import { JsonLd, pageMeta, SITE_URL } from "@/lib/seo";
import { ArrowRight, CalendarX } from "lucide-react";
import { apiOrNull, ApiError } from "@/lib/api";
import { PageHeader, Section } from "@/components/layout/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { CoverageBadge, CoverageNote } from "@/components/competitions/coverage-badge";
import { ResultsList } from "@/components/competitions/results-list";
import { Leaderboards } from "@/features/overview/leaderboards";
import {
  describeCompetition,
  GENDER_LABEL,
  SEASON_STATUS_LABEL,
  seasonSlug,
  TYPE_LABEL,
} from "@/lib/competitions";
import { num, shortDate } from "@/lib/format";
import { teamColor } from "@/lib/teams";
import type { CompetitionDetail, CompetitionType } from "@/types";

const TYPE_HUB: Record<CompetitionType, { href: string; label: string } | null> = {
  INTERNATIONAL: { href: "/international", label: "International" },
  ICC_TOURNAMENT: { href: "/tournaments", label: "Tournaments" },
  DOMESTIC: { href: "/domestic", label: "Domestic" },
  FRANCHISE_LEAGUE: { href: "/leagues", label: "Leagues" },
  REGIONAL: null,
  OTHER: null,
};

export async function generateMetadata({ params }: { params: { slug: string } }) {
  // notFound() must be raised here, not in the page body: Next commits the
  // status once generateMetadata resolves (see app/players/[id]/page.tsx).
  let c: CompetitionDetail | null;
  try {
    c = await apiOrNull<CompetitionDetail>(`/api/competitions/${params.slug}`);
  } catch {
    return { title: "Competition" };
  }
  if (!c) notFound();
  const cov = c.coverage;
  return pageMeta({
    title: c.name,
    description:
      `${c.name}: seasons, tables, results and ball-by-ball statistics`
      + (cov?.first_match && cov?.last_match
          ? ` from ${cov.first_match.slice(0, 4)} to ${cov.last_match.slice(0, 4)}`
          : "")
      + (cov?.matches ? `, computed from ${cov.matches} matches.` : "."),
    path: `/competitions/${params.slug}`,
  });
}

/** One page for every competition, configured by its metadata and data coverage. */
export default async function CompetitionPage({ params }: { params: { slug: string } }) {
  let c: CompetitionDetail | null;
  try {
    c = await apiOrNull<CompetitionDetail>(`/api/competitions/${params.slug}`);
  } catch (err) {
    return (
      <Section>
        <ErrorState title="Could not load this competition" detail={(err as ApiError).message} />
      </Section>
    );
  }
  if (!c) notFound();

  const hub = TYPE_HUB[c.type];
  const hasData = c.coverage.matches > 0;
  const current = c.current_season;

  return (
    <>
      <PageHeader
        crumbs={[
          { label: "Stryk", href: "/" },
          hub ?? { label: "Competitions", href: "/competitions" },
          { label: c.short_name ?? c.name },
        ]}
        title={c.name}
        subtitle={describeCompetition(c)}
        meta={
          <>
            <CoverageBadge status={c.coverage.status} label={c.coverage.label} />
            <Badge>{TYPE_LABEL[c.type]}</Badge>
            <Badge tone={c.gender === "WOMEN" ? "info" : "default"}>{GENDER_LABEL[c.gender]}</Badge>
            {c.formats.map((f) => (
              <Badge key={f}>{f}</Badge>
            ))}
            {!c.is_active ? <Badge tone="warn">No longer played</Badge> : null}
            {c.country ? (
              <span className="text-2xs text-ink-faint">
                {c.country.flag ? `${c.country.flag} ` : ""}
                {c.country.name}
              </span>
            ) : null}
          </>
        }
      />

      <Section className="space-y-5">
        {!hasData ? (
          <Panel>
            <PanelHeader title="No match data in STRYK" />
            <PanelBody className="space-y-3">
              <CoverageNote status={c.coverage.status} detail={c.coverage.detail} />
              {c.coverage.sources.length ? (
                <ul className="space-y-1.5 text-xs text-ink-muted">
                  {c.coverage.sources.map((s) => (
                    <li key={s.dataset}>
                      <a href={s.url} className="underline hover:text-accent" target="_blank" rel="noreferrer">
                        {s.source}: {s.name}
                      </a>{" "}
                      — {s.published_matches !== null ? `${num(s.published_matches)} matches published` : "count unknown"}
                      {s.gender_filter ? ` (all genders; this competition is the ${GENDER_LABEL[s.gender_filter].toLowerCase()}'s part)` : ""}
                      {s.checked_on ? `, checked ${s.checked_on}` : ""}.
                      <span className="block text-2xs text-ink-faint">
                        Import with{" "}
                        <code className="text-accent">
                          python scripts/fetch_cricsheet.py {s.dataset} &amp;&amp; python scripts/ingest.py --dataset {s.dataset}
                        </code>
                      </span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </PanelBody>
          </Panel>
        ) : (
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
            <div className="min-w-0 space-y-5">
              {current ? (
                <Panel>
                  <PanelHeader
                    title={`${current.name} season`}
                    description={`${current.start_date ? shortDate(current.start_date) : ""} – ${
                      current.end_date ? shortDate(current.end_date) : ""
                    } · ${current.matches} matches · ${SEASON_STATUS_LABEL[current.status]}`}
                    action={
                      <Link
                        href={`/competitions/${c.slug}/${seasonSlug(current.name)}`}
                        className="flex items-center gap-1 text-xs text-accent hover:underline"
                      >
                        Season page <ArrowRight className="h-3 w-3" aria-hidden />
                      </Link>
                    }
                  />
                  <PanelBody>
                    <p className="label-xs">Teams</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {c.teams.map((t) => (
                        <Link
                          key={t.id}
                          href={`/teams/${t.id}?competition=${c!.slug}`}
                          className="flex items-center gap-1.5 rounded border border-line-strong px-2 py-1 text-xs text-ink-muted hover:text-ink"
                        >
                          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: teamColor(t.name) }} aria-hidden />
                          {t.short_name ?? t.name}
                          <span className="num text-2xs text-ink-faint">
                            {t.won}/{t.played}
                          </span>
                        </Link>
                      ))}
                    </div>
                  </PanelBody>
                </Panel>
              ) : null}

              <Panel>
                <PanelHeader title="Recent results" description="Most recent completed matches in the data." />
                <ResultsList matches={c.recent_results} />
              </Panel>

              {c.leaders && current ? (
                <div>
                  <h2 className="mb-2 font-display text-base font-semibold tracking-tight text-ink">
                    {current.name} leaders
                  </h2>
                  <Leaderboards boards={c.leaders} />
                </div>
              ) : null}
            </div>

            <aside className="min-w-0 space-y-5">
              <Panel>
                <PanelHeader title="Seasons" description={`${c.seasons.length} in the data`} />
                <ul className="max-h-[420px] divide-y divide-line/60 overflow-auto">
                  {c.seasons.map((s) => (
                    <li key={s.id}>
                      <Link
                        href={`/competitions/${c!.slug}/${seasonSlug(s.name)}`}
                        className="flex items-center justify-between gap-3 px-4 py-2 text-sm hover:bg-surface-raised"
                      >
                        <span className="num text-ink">{s.name}</span>
                        <span className="text-2xs text-ink-faint">
                          {s.matches} matches · {SEASON_STATUS_LABEL[s.status].toLowerCase()}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </Panel>

              <Panel>
                <PanelHeader title="Fixtures" />
                <PanelBody>
                  <EmptyState icon={CalendarX} title="No upcoming fixtures" detail={c.fixtures.reason} className="py-4" />
                </PanelBody>
              </Panel>

              <Panel>
                <PanelHeader title="Data coverage" />
                <PanelBody className="space-y-2">
                  <CoverageNote status={c.coverage.status} />
                  <p className="text-2xs text-ink-faint">
                    <span className="num">{num(c.coverage.matches)}</span> matches,{" "}
                    {c.coverage.first_match ? shortDate(c.coverage.first_match) : ""} to{" "}
                    {c.coverage.last_match ? shortDate(c.coverage.last_match) : ""}.
                    {c.coverage.sources.map((s) => (
                      <span key={s.dataset}>
                        {" "}
                        Source: {s.source} ({s.name}
                        {s.published_matches !== null ? `, ${num(s.published_matches)} published` : ""}).
                      </span>
                    ))}
                  </p>
                  {c.points_system ? (
                    <p className="text-2xs text-ink-faint">
                      Points table rules: {c.points_system.name} (checked {c.points_system.verified_on}).
                    </p>
                  ) : (
                    <p className="text-2xs text-ink-faint">
                      No points system is configured, so no standings are computed for this competition.
                    </p>
                  )}
                </PanelBody>
              </Panel>
            </aside>
          </div>
        )}
      </Section>
    </>
  );
}
