import Link from "next/link";
import { notFound } from "next/navigation";
import { api, apiOrNull, ApiError } from "@/lib/api";
import { filterQuery, type RawParams } from "@/lib/search-params";
import { Hint } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { Section } from "@/components/layout/page-header";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ErrorState, EmptyState, NoDataState } from "@/components/ui/states";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { FilterBar } from "@/features/filters/filter-bar";
import { AnalysisTabs } from "@/features/players/analysis-tabs";
import {
  BattingSplitTable,
  BowlingSplitTable,
  textLabel,
} from "@/features/players/stat-tables";
import {
  DismissalChart,
  PhaseChart,
  SeasonBattingChart,
  SeasonBowlingChart,
} from "@/features/players/profile-charts";
import { MethodNotes } from "@/features/players/method-notes";
import { PlayerCard } from "@/features/players/player-card";
import { ScoringRing } from "@/components/charts/scoring-ring";
import { OverStrip } from "@/components/charts/over-strip";
import { teamColor } from "@/lib/teams";
import { BallStrip, BallStripLegend } from "@/components/ui/ball-strip";
import { dec, num, pct, shortDate, figures } from "@/lib/format";
import type { MatchupOpponent, PlayerProfile, SeasonMeta } from "@/types";

const PHASE_LABEL: Record<string, string> = {
  powerplay: "Powerplay (1–6)",
  middle: "Middle (7–15)",
  death: "Death (16–20)",
};

export async function generateMetadata({ params }: { params: { id: string } }) {
  // notFound() must be raised here rather than in the page body: Next commits
  // the response status once generateMetadata resolves, so an unknown id would
  // otherwise render the not-found page under a 200.
  let profile: PlayerProfile | null;
  try {
    profile = await apiOrNull<PlayerProfile>(`/api/players/${params.id}`);
  } catch {
    // The API being unreachable is not a missing player: let the page render
    // its own error state rather than claiming the player does not exist.
    return { title: "Player" };
  }
  if (!profile) notFound();
  return { title: profile.player.name };
}

export default async function PlayerPage({
  params,
  searchParams,
}: {
  params: { id: string };
  searchParams: RawParams;
}) {
  let p: PlayerProfile | null;
  let seasons: SeasonMeta[];
  let topBowlers: MatchupOpponent[] = [];
  try {
    [p, seasons, topBowlers] = await Promise.all([
      apiOrNull<PlayerProfile>(`/api/players/${params.id}`, filterQuery(searchParams)),
      api<SeasonMeta[]>("/api/meta/seasons"),
      api<MatchupOpponent[]>(`/api/players/${params.id}/matchups`, {
        ...filterQuery(searchParams),
        as_role: "batter",
        limit: 10,
      }).catch(() => []),
    ]);
  } catch (err) {
    const e = err as ApiError;
    return (
      <Section>
        {e.status === 503 ? <NoDataState /> : <ErrorState title="Could not load this player" detail={e.message} />}
      </Section>
    );
  }
  if (!p) notFound();

  const bat = p.batting;
  const bowl = p.bowling;
  const hasBat = (bat?.balls ?? 0) > 0;
  const hasBowl = (bowl?.balls ?? 0) > 0;
  // An over strip needs at least one over with enough balls to carry a rate.
  const ratedBatting = p.by_over?.some((o) => o.strike_rate !== null) ?? false;
  const ratedBowling = p.by_over?.some((o) => o.economy !== null) ?? false;

  return (
    <>
      <div className="border-b border-line bg-surface-sunken">
        <div className="mx-auto max-w-[1600px] px-4 pb-6 pt-5 lg:px-6">
          <Breadcrumbs
            items={[
              { label: "Stryk", href: "/" },
              { label: "Players", href: "/players" },
              { label: p.player.name },
            ]}
          />
          <div className="mt-3">
            <PlayerCard profile={p} />
          </div>
        </div>
      </div>
      <FilterBar seasons={seasons} />

      <Section className="space-y-4">
        {!hasBat && !hasBowl ? (
          <Panel>
            <EmptyState
              title="No deliveries under these filters"
              detail="This player did not bat or bowl in any match matching the current season, phase or innings filters."
            />
          </Panel>
        ) : null}

        {p.scoring_shape || ratedBatting || ratedBowling ? (
          <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)] [&>*]:min-w-0">
            {p.scoring_shape ? (
              <Panel className="rounded-lg">
                <PanelHeader
                  title="How the runs are made"
                  description="Outer ring is the share of balls; inner ring is the share of runs those balls produced."
                />
                <PanelBody>
                  <ScoringRing shape={p.scoring_shape} />
                </PanelBody>
              </Panel>
            ) : null}
            {ratedBatting || ratedBowling ? (
            <Panel className="rounded-lg">
              <PanelHeader
                title="Over by over"
                description="Where in the innings this player operates, and how well."
              />
              <PanelBody className="space-y-5">
                {ratedBatting ? (
                  <div>
                    <p className="label-xs mb-2">With the bat</p>
                    <OverStrip
                      overs={p.by_over ?? []}
                      mode="batting"
                      teamColor={teamColor(p.player.teams[0]?.team_name)}
                    />
                  </div>
                ) : null}
                {ratedBowling ? (
                  <div>
                    <p className="label-xs mb-2">With the ball</p>
                    <OverStrip
                      overs={p.by_over ?? []}
                      mode="bowling"
                      teamColor={teamColor(p.player.teams[0]?.team_name)}
                    />
                  </div>
                ) : null}
              </PanelBody>
            </Panel>
            ) : null}
          </div>
        ) : null}

        {/* The card above carries the headline figures; this is the full line,
            including the fields the card leaves out, each with its formula. */}
        <Panel className="rounded-lg">
          <PanelHeader
            title="The full career line"
            description="Every figure under the current filters, with its definition. A blank is a statistic that is undefined for this player, never a zero."
          />
          <div className="grid min-w-0 divide-y divide-line lg:grid-cols-2 lg:divide-x lg:divide-y-0 [&>*]:min-w-0">
            {hasBat && bat ? (
              <LineTable
                title="Batting"
                note="Not-outs are excluded from the average's denominator. Strike rate counts only balls actually faced: wides are not charged to the batter."
                rows={[
                  { label: "Innings", value: num(bat.innings), sub: `${num(bat.not_outs)} not out` },
                  { label: "Runs", value: num(bat.runs), accent: true },
                  { label: "Balls faced", value: num(bat.balls), hint: "Excludes wides; includes no-balls." },
                  { label: "Average", value: dec(bat.average), hint: "Runs ÷ dismissals." },
                  { label: "Strike rate", value: dec(bat.strike_rate), hint: "Runs ÷ balls faced × 100." },
                  { label: "Highest score", value: `${num(bat.highest_score)}${bat.highest_not_out ? "*" : ""}` },
                  { label: "Fifties / hundreds", value: `${num(bat.fifties)} / ${num(bat.hundreds)}` },
                  { label: "Fours / sixes", value: `${num(bat.fours)} / ${num(bat.sixes)}` },
                  { label: "Boundary %", value: pct(bat.boundary_pct), hint: "Share of balls faced hit for four or six." },
                  { label: "Dot %", value: pct(bat.dot_pct), hint: "Share of balls faced that produced no run off the bat." },
                  { label: "Boundary run %", value: pct(bat.boundary_run_pct), hint: "Share of this player's runs that came in boundaries." },
                ]}
              />
            ) : null}
            {hasBowl && bowl ? (
              <LineTable
                title="Bowling"
                note="Runs conceded exclude byes and leg-byes, which are not charged to the bowler. Wickets exclude run-outs and other dismissals not credited to the bowler."
                rows={[
                  { label: "Innings", value: num(bowl.innings) },
                  { label: "Overs", value: bowl.overs, hint: "Legal balls ÷ 6, shown as overs.balls." },
                  { label: "Runs conceded", value: num(bowl.runs) },
                  { label: "Wickets", value: num(bowl.wickets), accent: true },
                  { label: "Economy", value: dec(bowl.economy), hint: "Runs conceded ÷ overs." },
                  { label: "Average", value: dec(bowl.average), hint: "Runs conceded ÷ wickets." },
                  { label: "Strike rate", value: dec(bowl.strike_rate), hint: "Legal balls bowled ÷ wickets." },
                  { label: "Best figures", value: figures(bowl.best_wickets, bowl.best_runs) },
                  { label: "4w / 5w hauls", value: `${num(bowl.four_wicket_hauls)} / ${num(bowl.five_wicket_hauls)}` },
                  { label: "Dot %", value: pct(bowl.dot_pct), hint: "Share of legal deliveries conceding nothing." },
                  { label: "Wides / no-balls", value: `${num(bowl.wides)} / ${num(bowl.noballs)}` },
                ]}
              />
            ) : null}
          </div>
        </Panel>

        <Panel>
          <AnalysisTabs
            tabs={[
              {
                value: "phase",
                label: "Phases",
                content: (
                  <PanelBody className="space-y-5">
                    <p className="text-xs leading-relaxed text-ink-muted">
                      Phases are fixed by over number: powerplay is overs 1–6, middle 7–15, death
                      16–20. An innings shortened by rain simply contributes fewer deliveries to the
                      later phases — it is not padded.
                    </p>
                    <PhaseChart batting={p.batting_by_phase} bowling={p.bowling_by_phase} />
                    {hasBat ? (
                      <div>
                        <p className="label-xs mb-2">Batting</p>
                        <BattingSplitTable
                          rows={p.batting_by_phase.filter((r) => (r.balls ?? 0) > 0)}
                          label={{ header: "Phase", render: (r) => PHASE_LABEL[r.phase] ?? r.phase }}
                        />
                      </div>
                    ) : null}
                    {hasBowl ? (
                      <div>
                        <p className="label-xs mb-2">Bowling</p>
                        <BowlingSplitTable
                          rows={p.bowling_by_phase.filter((r) => (r.balls ?? 0) > 0)}
                          label={{ header: "Phase", render: (r) => PHASE_LABEL[r.phase] ?? r.phase }}
                        />
                      </div>
                    ) : null}
                  </PanelBody>
                ),
              },
              {
                value: "season",
                label: "Seasons",
                content: (
                  <div className="divide-y divide-line">
                    {hasBat && p.batting_by_season.length ? (
                      <div>
                        <SeasonBattingChart rows={p.batting_by_season} />
                        <PanelBody className="pt-0">
                          <BattingSplitTable
                            rows={p.batting_by_season}
                            label={textLabel("Season", "season")}
                          />
                        </PanelBody>
                      </div>
                    ) : null}
                    {hasBowl && p.bowling_by_season.length ? (
                      <div>
                        <SeasonBowlingChart rows={p.bowling_by_season} />
                        <PanelBody className="pt-0">
                          <BowlingSplitTable
                            rows={p.bowling_by_season}
                            label={textLabel("Season", "season")}
                          />
                        </PanelBody>
                      </div>
                    ) : null}
                  </div>
                ),
              },
              {
                value: "innings",
                label: "Chasing vs setting",
                content: (
                  <PanelBody className="space-y-5">
                    <p className="text-xs leading-relaxed text-ink-muted">
                      Batting second is a different problem from batting first: the target is known
                      and the required rate moves. These are the same career splits, separated by
                      which innings the player was in.
                    </p>
                    {hasBat ? (
                      <div>
                        <p className="label-xs mb-2">Batting</p>
                        <BattingSplitTable
                          rows={[
                            ...p.batting_by_innings_type.setting.map((r) => ({ ...r, kind: "Batting first" })),
                            ...p.batting_by_innings_type.chasing.map((r) => ({ ...r, kind: "Chasing" })),
                          ].filter((r) => (r.balls ?? 0) > 0)}
                          label={{ header: "Situation", render: (r: any) => r.kind }}
                        />
                      </div>
                    ) : null}
                    {hasBowl ? (
                      <div>
                        <p className="label-xs mb-2">Bowling</p>
                        <BowlingSplitTable
                          rows={[
                            ...p.bowling_by_innings_type.first_innings.map((r) => ({ ...r, kind: "Bowling first" })),
                            ...p.bowling_by_innings_type.defending.map((r) => ({ ...r, kind: "Defending a total" })),
                          ].filter((r) => (r.balls ?? 0) > 0)}
                          label={{ header: "Situation", render: (r: any) => r.kind }}
                        />
                      </div>
                    ) : null}
                  </PanelBody>
                ),
              },
              {
                value: "venue",
                label: "Venues",
                content: (
                  <PanelBody className="space-y-5">
                    {hasBat && p.batting_by_venue.length ? (
                      <div>
                        <p className="label-xs mb-2">Batting by venue</p>
                        <BattingSplitTable rows={p.batting_by_venue} label={textLabel("Venue", "venue")} dense />
                      </div>
                    ) : null}
                    {hasBowl && p.bowling_by_venue.length ? (
                      <div>
                        <p className="label-xs mb-2">Bowling by venue</p>
                        <BowlingSplitTable rows={p.bowling_by_venue} label={textLabel("Venue", "venue")} dense />
                      </div>
                    ) : null}
                  </PanelBody>
                ),
              },
              {
                value: "opposition",
                label: "Opposition",
                content: (
                  <PanelBody className="space-y-5">
                    {hasBat && p.batting_by_opposition.length ? (
                      <div>
                        <p className="label-xs mb-2">Batting by opposition</p>
                        <BattingSplitTable
                          rows={p.batting_by_opposition}
                          label={textLabel("Opposition", "opposition")}
                          dense
                        />
                      </div>
                    ) : null}
                    {hasBowl && p.bowling_by_opposition.length ? (
                      <div>
                        <p className="label-xs mb-2">Bowling by opposition</p>
                        <BowlingSplitTable
                          rows={p.bowling_by_opposition}
                          label={textLabel("Opposition", "opposition")}
                          dense
                        />
                      </div>
                    ) : null}
                  </PanelBody>
                ),
              },
              {
                value: "form",
                label: "Recent form",
                content: (
                  <PanelBody className="grid min-w-0 gap-5 lg:grid-cols-2 [&>*]:min-w-0">
                    {p.recent_innings.length ? (
                      <div>
                        <p className="label-xs mb-2">Last innings with the bat</p>
                        <BallStripLegend className="mb-3" />
                        <ul className="space-y-2">
                          {p.recent_innings.map((i, idx) => (
                            <li
                              key={idx}
                              className="rounded-lg border border-line bg-surface-sunken px-3 py-2.5"
                            >
                              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                                <span className="text-sm text-ink">
                                  <span className="num font-semibold">
                                    {num(i.runs)}
                                    {i.out ? "" : "*"}
                                  </span>
                                  <span className="num text-ink-muted"> off {num(i.balls)}</span>
                                  <span className="text-ink-faint"> v {i.opposition}</span>
                                </span>
                                <span className="num text-2xs text-ink-faint">
                                  {shortDate(i.date)} · {dec(i.strike_rate)} SR
                                </span>
                              </div>
                              {i.sequence?.length ? (
                                <BallStrip sequence={i.sequence} className="mt-2" />
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {p.recent_spells.length ? (
                      <div>
                        <p className="label-xs mb-2">Last spells with the ball</p>
                        <TableWrap>
                          <Table>
                            <thead>
                              <tr>
                                <Th>Date</Th>
                                <Th>Opposition</Th>
                                <Th numeric>Overs</Th>
                                <Th numeric>Figures</Th>
                                <Th numeric>Econ</Th>
                              </tr>
                            </thead>
                            <tbody>
                              {p.recent_spells.map((s, idx) => (
                                <Tr key={idx}>
                                  <Td className="text-ink-muted">{shortDate(s.date)}</Td>
                                  <Td className="max-w-[180px] truncate">{s.opposition}</Td>
                                  <Td numeric className="text-ink-muted">{s.overs}</Td>
                                  <Td numeric className="font-medium">{figures(s.wickets, s.runs)}</Td>
                                  <Td numeric>{dec(s.economy)}</Td>
                                </Tr>
                              ))}
                            </tbody>
                          </Table>
                        </TableWrap>
                      </div>
                    ) : null}
                  </PanelBody>
                ),
              },
              {
                value: "dismissals",
                label: "Dismissals & match-ups",
                content: (
                  <PanelBody className="grid min-w-0 gap-6 lg:grid-cols-2 [&>*]:min-w-0">
                    <div>
                      <p className="label-xs mb-2">How this batter gets out</p>
                      {Object.keys(p.dismissal_patterns).length ? (
                        <DismissalChart patterns={p.dismissal_patterns} />
                      ) : (
                        <EmptyState title="No dismissals recorded under these filters" className="py-8" />
                      )}
                    </div>
                    <div>
                      <p className="label-xs mb-2">Most-faced bowlers</p>
                      {topBowlers.length ? (
                        <TableWrap>
                          <Table>
                            <thead>
                              <tr>
                                <Th>Bowler</Th>
                                <Th numeric>Balls</Th>
                                <Th numeric>Runs</Th>
                                <Th numeric>Outs</Th>
                                <Th numeric>SR</Th>
                                <Th>Sample</Th>
                              </tr>
                            </thead>
                            <tbody>
                              {topBowlers.map((o) => (
                                <Tr key={o.opponent_id}>
                                  <Td>
                                    <Link
                                      href={`/matchups?batter=${p!.player.id}&bowler=${o.opponent_id}`}
                                      className="text-ink hover:text-accent"
                                    >
                                      {o.opponent_name}
                                    </Link>
                                  </Td>
                                  <Td numeric className="text-ink-muted">{num(o.balls)}</Td>
                                  <Td numeric>{num(o.runs)}</Td>
                                  <Td numeric>{num(o.dismissals)}</Td>
                                  <Td numeric>{dec(o.strike_rate)}</Td>
                                  <Td>
                                    <Badge tone={o.reliability === "readable" ? "accent" : "warn"}>
                                      {o.reliability}
                                    </Badge>
                                  </Td>
                                </Tr>
                              ))}
                            </tbody>
                          </Table>
                        </TableWrap>
                      ) : (
                        <EmptyState title="No repeated match-ups under these filters" className="py-8" />
                      )}
                    </div>
                  </PanelBody>
                ),
              },
            ]}
          />
        </Panel>

        <MethodNotes
          metrics={p.data_notes.metrics}
          qualification={p.data_notes.qualification}
          notes={p.data_notes.bowling_style_note}
        />
      </Section>
    </>
  );
}

/** A compact label/value list: the full statistical line without the giant
 *  numerals, which the player card already owns. */
function LineTable({
  title,
  note,
  rows,
}: {
  title: string;
  note: string;
  rows: Array<{ label: string; value: React.ReactNode; sub?: string; hint?: string; accent?: boolean }>;
}) {
  return (
    <div className="p-4">
      <h3 className="font-display text-sm font-semibold text-ink">{title}</h3>
      <p className="mt-1 text-2xs leading-relaxed text-ink-faint">{note}</p>
      <dl className="mt-3 space-y-0">
        {rows.map((r) => (
          <div
            key={r.label}
            className="flex items-baseline justify-between gap-3 border-b border-line/50 py-1.5 last:border-0"
          >
            <dt className="flex items-center gap-1 text-xs text-ink-muted">
              {r.label}
              {r.hint ? <Hint text={r.hint} /> : null}
            </dt>
            <dd
              className={cn(
                "num text-sm",
                r.accent ? "font-semibold text-accent" : "text-ink",
              )}
            >
              {r.value}
              {r.sub ? <span className="ml-2 text-2xs text-ink-faint">{r.sub}</span> : null}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
