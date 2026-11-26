import Link from "next/link";
import { notFound } from "next/navigation";
import { JsonLd, pageMeta, scopeName, SITE_URL } from "@/lib/seo";
import { AlertTriangle } from "lucide-react";
import { api, apiOrNull, ApiError } from "@/lib/api";
import { CompetitionSwitcher } from "@/components/competitions/competition-switcher";
import { filterQuery, describeFilters, type RawParams } from "@/lib/search-params";
import { Section } from "@/components/layout/page-header";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { teamIdentity, teamVars } from "@/lib/teams";
import { teamLogo } from "@/lib/photos";
import { TeamCrest } from "@/components/ui/team-crest";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/card";
import { Stat, StatRow } from "@/components/ui/stat";
import { Badge } from "@/components/ui/badge";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { EmptyState, ErrorState, NoDataState } from "@/components/ui/states";
import { FilterBar } from "@/features/filters/filter-bar";
import { AnalysisTabs } from "@/features/players/analysis-tabs";
import {
  BattingDepthChart,
  RoleMix,
  SeasonRecordChart,
  TeamBalance,
} from "@/features/teams/team-charts";
import { dec, num } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { SeasonMeta, TeamProfile } from "@/types";

const PHASE_LABEL: Record<string, string> = {
  powerplay: "Powerplay (1–6)",
  middle: "Middle (7–15)",
  death: "Death (16–20)",
};

export async function generateMetadata({ params }: { params: { id: string } }) {
  // See the note in app/players/[id]/page.tsx: the 404 status has to be raised
  // before generateMetadata resolves, or Next commits a 200.
  let team: TeamProfile | null;
  try {
    team = await apiOrNull<TeamProfile>(`/api/teams/${params.id}`);
  } catch {
    return { title: "Team" };
  }
  if (!team) notFound();
  const t = team.team;
  const where = scopeName(team.scope?.competitions, team.competitions);
  const years = team.by_season?.map((r) => r.season) ?? [];
  const span = years.length ? `, ${Math.min(...years)}\u2013${Math.max(...years)}` : "";
  return pageMeta({
    title: t.name,
    description:
      `${t.name}'s ball-by-ball record${where ? ` in ${where}` : ""}: `
      + `results, players and how they score and concede across ${team.record?.played ?? 0} matches${span}.`,
    path: `/teams/${params.id}`,
  });
}

export default async function TeamPage({
  params,
  searchParams,
}: {
  params: { id: string };
  searchParams: RawParams;
}) {
  let profile: TeamProfile | null;
  let seasons: SeasonMeta[];
  try {
    profile = await apiOrNull<TeamProfile>(`/api/teams/${params.id}`, filterQuery(searchParams));
    // Seasons of the competition this profile shows (the team's busiest unless the URL names one).
    seasons = await api<SeasonMeta[]>("/api/meta/seasons", { competition: profile?.scope?.competitions });
  } catch (err) {
    const e = err as ApiError;
    return (
      <Section>
        {e.status === 503 ? <NoDataState /> : <ErrorState title="Could not load this team" detail={e.message} />}
      </Section>
    );
  }
  if (!profile) notFound();

  const identity = teamIdentity(profile.team.name, profile.team.short_name);
  const chase = profile.innings_type.chasing;
  const set = profile.innings_type.setting;

  return (
    <>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "SportsTeam",
          name: profile.team.name,
          ...(profile.team.short_name ? { alternateName: profile.team.short_name } : {}),
          sport: "Cricket",
          url: `${SITE_URL}/teams/${params.id}`,
        }}
      />
      <div
        style={teamVars(profile.team.name)}
        className="relative overflow-hidden border-b border-line bg-surface-sunken"
      >
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(70% 120% at 12% 0%, color-mix(in srgb, var(--team) 24%, transparent) 0%, transparent 62%)",
          }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-[3px]"
          style={{ background: "linear-gradient(90deg, var(--team), var(--team-2), transparent)" }}
        />
        <div className="relative mx-auto max-w-[1600px] px-4 pb-7 pt-5 lg:px-6">
          <Breadcrumbs
            items={[
              { label: "Stryk", href: "/" },
              { label: "Teams", href: "/teams" },
              { label: identity.short || profile.team.name },
            ]}
          />
          <div className="mt-3 flex flex-wrap items-end gap-x-6 gap-y-4">
            <TeamCrest
              team={profile.team.name}
              size={84}
              logoSrc={teamLogo(profile.team.name, identity.short)}
              flag={profile.team.flag}
              short={profile.team.short_name}
              className="shrink-0"
            />
            <div className="min-w-0">
              <h1 className="font-display text-3xl font-bold leading-none tracking-tight text-ink lg:text-4xl">
                {profile.team.name}
              </h1>
              {identity.tagline ? (
                <p className="mt-1.5 text-sm italic" style={{ color: "var(--team)" }}>
                  {identity.tagline}
                </p>
              ) : null}
              <p className="mt-1.5 text-xs text-ink-faint">
                {profile.team.aliases.length
                  ? `Record includes matches played as ${profile.team.aliases.join(", ")}. `
                  : ""}
                Showing {describeFilters(searchParams)}.
              </p>
              {profile.competitions?.length ? (
                <div className="mt-2">
                  <CompetitionSwitcher
                    options={profile.competitions}
                    current={profile.scope?.competitions[0]}
                    basePath={`/teams/${params.id}`}
                  />
                </div>
              ) : null}
            </div>
            <div className="ml-auto flex gap-5">
              {[
                { label: "Played", value: num(profile.record.played) },
                { label: "Won", value: num(profile.record.won) },
                { label: "Win %", value: dec(profile.record.win_pct, 1) },
              ].map((stat) => (
                <div key={stat.label}>
                  <div className="text-2xs text-ink-faint">{stat.label}</div>
                  <div
                    className="num mt-0.5 font-display text-2xl font-bold leading-none"
                    style={{ color: stat.label === "Win %" ? "var(--team)" : undefined }}
                  >
                    {stat.value}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      <FilterBar seasons={seasons} show={["season", "phase", "innings"]} />

      <Section className="space-y-4">
        <div className="grid min-w-0 gap-4 lg:grid-cols-[1fr_1.1fr] [&>*]:min-w-0">
          <Panel>
            <PanelHeader
              title="Team balance"
              description="Phase strength against the league under the same filters — where this squad actually wins and loses matches."
            />
            <TeamBalance profile={profile} />
          </Panel>
          <Panel>
            <PanelHeader title="Season record" description="Wins and losses by season, with the resulting win rate." />
            <PanelBody>
              <SeasonRecordChart profile={profile} />
            </PanelBody>
          </Panel>
        </div>

        <Panel>
          <AnalysisTabs
            tabs={[
              {
                value: "phases",
                label: "Phase performance",
                content: (
                  <PanelBody className="space-y-5">
                    <p className="text-xs leading-relaxed text-ink-muted">
                      Each phase is shown next to the league&apos;s rate for the same phase and the
                      same filters, so a low death-overs rate can be read as a weakness rather than
                      as a feature of T20.
                    </p>
                    <div className="grid min-w-0 gap-5 lg:grid-cols-2 [&>*]:min-w-0">
                      <PhaseTable rows={profile.phase_profile.batting} kind="batting" />
                      <PhaseTable rows={profile.phase_profile.bowling} kind="bowling" />
                    </div>
                  </PanelBody>
                ),
              },
              {
                value: "depth",
                label: "Batting depth",
                content: (
                  <PanelBody className="space-y-5">
                    <p className="text-xs leading-relaxed text-ink-muted">
                      {String(profile.data_notes.batting_position_note ?? "")}
                    </p>
                    <BattingDepthChart profile={profile} />
                    <TableWrap>
                      <Table>
                        <thead>
                          <tr>
                            <Th>Position</Th>
                            <Th numeric>Innings</Th>
                            <Th numeric>Runs</Th>
                            <Th numeric>Runs per innings</Th>
                            <Th numeric>Average</Th>
                            <Th numeric>Strike rate</Th>
                          </tr>
                        </thead>
                        <tbody>
                          {profile.batting_depth.map((d) => (
                            <Tr key={d.position}>
                              <Td>#{d.position}</Td>
                              <Td numeric className="text-ink-muted">{num(d.innings)}</Td>
                              <Td numeric className="font-medium">{num(d.runs)}</Td>
                              <Td numeric>{dec(d.runs_per_innings, 1)}</Td>
                              <Td numeric>{dec(d.average)}</Td>
                              <Td numeric>{dec(d.strike_rate)}</Td>
                            </Tr>
                          ))}
                        </tbody>
                      </Table>
                    </TableWrap>
                  </PanelBody>
                ),
              },
              {
                value: "squad",
                label: "Squad",
                content: (
                  <PanelBody className="space-y-5">
                    <div className="grid min-w-0 gap-5 lg:grid-cols-[260px_1fr] [&>*]:min-w-0">
                      <div>
                        <p className="label-xs mb-2">Role mix</p>
                        <RoleMix distribution={profile.squad.role_distribution} />
                        <p className="mt-2 text-2xs leading-relaxed text-ink-faint">
                          Roles are inferred from workload, not from an official designation: a
                          player with 300+ balls faced and 300+ balls bowled is an all-rounder,
                          otherwise whichever discipline they have done more of.
                        </p>
                      </div>
                      <div>
                        <p className="label-xs mb-2">Players used ({profile.squad.players.length})</p>
                        <SquadTable profile={profile} />
                      </div>
                    </div>
                  </PanelBody>
                ),
              },
              {
                value: "innings",
                label: "Chasing vs setting",
                content: (
                  <PanelBody className="space-y-4">
                    <div className="grid gap-4 sm:grid-cols-2">
                      <InningsCard title="Batting first" data={set} />
                      <InningsCard title="Chasing" data={chase} />
                    </div>
                    <p className="text-2xs leading-relaxed text-ink-faint">
                      Win counts here are the matches in which the team batted in that position, so
                      the two add up to the team&apos;s overall record.
                    </p>
                  </PanelBody>
                ),
              },
            ]}
          />
        </Panel>

        {profile.data_notes.overseas_data_available === false ? (
          <div className="flex items-start gap-2.5 border border-signal-warn/30 bg-signal-warn/5 px-4 py-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-signal-warn" aria-hidden />
            <div>
              <p className="text-xs font-medium text-signal-warn">
                Overseas composition is not available
              </p>
              <p className="mt-0.5 text-xs leading-relaxed text-ink-muted">
                {String(profile.data_notes.overseas_note ?? "")}
              </p>
            </div>
          </div>
        ) : null}
      </Section>
    </>
  );
}

function PhaseTable({
  rows,
  kind,
}: {
  rows: TeamProfile["phase_profile"]["batting"];
  kind: "batting" | "bowling";
}) {
  if (!rows.length) return <EmptyState title="No deliveries in this split" className="py-8" />;
  const goodWhenAbove = kind === "batting";
  return (
    <div>
      <p className="label-xs mb-2">{kind === "batting" ? "With the bat" : "With the ball"}</p>
      <TableWrap>
        <Table>
          <thead>
            <tr>
              <Th>Phase</Th>
              <Th numeric>Runs</Th>
              <Th numeric>Balls</Th>
              <Th numeric>Run rate</Th>
              <Th numeric>League</Th>
              <Th numeric>vs league</Th>
              <Th numeric>Balls per wkt</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => {
              const diff =
                p.run_rate && p.league_run_rate ? p.run_rate - p.league_run_rate : null;
              const good = diff === null ? null : goodWhenAbove ? diff > 0 : diff < 0;
              return (
                <Tr key={p.phase}>
                  <Td>{PHASE_LABEL[p.phase] ?? p.phase}</Td>
                  <Td numeric className="text-ink-muted">{num(p.runs)}</Td>
                  <Td numeric className="text-ink-muted">{num(p.balls)}</Td>
                  <Td numeric className="font-medium">{dec(p.run_rate)}</Td>
                  <Td numeric className="text-ink-muted">{dec(p.league_run_rate)}</Td>
                  <Td
                    numeric
                    className={cn(good === null ? "" : good ? "text-accent" : "text-signal-down")}
                  >
                    {diff === null ? "—" : `${diff > 0 ? "+" : ""}${diff.toFixed(2)}`}
                  </Td>
                  <Td numeric>{dec(p.balls_per_wicket, 1)}</Td>
                </Tr>
              );
            })}
          </tbody>
        </Table>
      </TableWrap>
    </div>
  );
}

function SquadTable({ profile }: { profile: TeamProfile }) {
  const players = [...profile.squad.players].sort((a, b) => b.matches - a.matches).slice(0, 40);
  return (
    <TableWrap className="max-h-[520px] overflow-y-auto">
      <Table>
        <thead className="sticky top-0 bg-surface">
          <tr>
            <Th>Player</Th>
            <Th>Role</Th>
            <Th numeric>Mat</Th>
            <Th numeric>Pos</Th>
            <Th numeric>Runs</Th>
            <Th numeric>Avg</Th>
            <Th numeric>SR</Th>
            <Th numeric>Wkts</Th>
            <Th numeric>Econ</Th>
          </tr>
        </thead>
        <tbody>
          {players.map((p) => (
            <Tr key={p.player_id}>
              <Td>
                <Link
                  href={`/players/${p.player_id}`}
                  className="text-ink transition-colors hover:text-accent"
                >
                  {p.name}
                </Link>
              </Td>
              <Td>
                <Badge tone={p.role === "All-rounder" ? "accent" : "default"}>{p.role ?? "—"}</Badge>
              </Td>
              <Td numeric className="text-ink-muted">{num(p.matches)}</Td>
              <Td numeric className="text-ink-muted">{p.batting_position ?? "—"}</Td>
              <Td numeric className="font-medium">{num(p.runs)}</Td>
              <Td numeric>{dec(p.batting_average)}</Td>
              <Td numeric>{dec(p.strike_rate)}</Td>
              <Td numeric className="font-medium">{num(p.wickets)}</Td>
              <Td numeric>{dec(p.economy)}</Td>
            </Tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  );
}

function InningsCard({
  title,
  data,
}: {
  title: string;
  data?: TeamProfile["innings_type"][string];
}) {
  if (!data) return <EmptyState title={`No ${title.toLowerCase()} innings`} className="py-8" />;
  return (
    <div className="border border-line">
      <PanelHeader title={title} />
      <StatRow className="grid-cols-2 lg:grid-cols-2">
        <Stat label="Innings" value={num(data.innings)} sub={`${num(data.wins)} won`} />
        <Stat label="Run rate" value={dec(data.run_rate)} tone="accent" />
        <Stat label="Runs" value={num(data.runs)} sub={`${num(data.balls)} balls`} />
        <Stat
          label="Wickets lost"
          value={num(data.wickets_lost)}
          sub={`${dec(data.wickets_lost / Math.max(data.innings, 1), 1)} per innings`}
        />
      </StatRow>
    </div>
  );
}
