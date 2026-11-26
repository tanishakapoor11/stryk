import { api, ApiError } from "@/lib/api";
import { filterQuery, describeFilters, many, type RawParams } from "@/lib/search-params";
import { PageHeader, Section } from "@/components/layout/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/card";
import { EmptyState, ErrorState, NoDataState } from "@/components/ui/states";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { FilterBar } from "@/features/filters/filter-bar";
import { PlayerPicker, SelectedChip } from "@/features/compare/player-picker";
import {
  BATTING_ROWS,
  BOWLING_ROWS,
  ComparisonTable,
} from "@/features/compare/comparison";
import {
  CompareRadar,
  CompareSeasons,
  ComparePhases,
} from "@/features/compare/compare-charts";
// SERIES comes from the plain token module: a server component may not reach
// into a "use client" module's exports, only pass the imported name through.
import { SERIES } from "@/components/charts/theme";
import { AnalysisTabs } from "@/features/players/analysis-tabs";
import { Contenders } from "@/features/compare/contenders";
import { CompetitionSwitcher } from "@/components/competitions/competition-switcher";
import { dec, num, pct } from "@/lib/format";
import type { EntityCompetition, PlayerProfile, Scope, SeasonMeta } from "@/types";

export const metadata = { title: "Player Comparison" };

interface ComparePayload {
  players: PlayerProfile[];
  filters: Record<string, unknown>;
  scope?: Scope;
  /** Competitions every selected player has played in. Empty = no overlap. */
  competitions: EntityCompetition[];
}

export default async function ComparePage({ searchParams }: { searchParams: RawParams }) {
  const ids = many(searchParams, "player").slice(0, 4);

  let seasons: SeasonMeta[];
  let data: ComparePayload | null = null;
  try {
    if (ids.length) {
      data = await api<ComparePayload>("/api/compare", {
        ...filterQuery(searchParams),
        player: ids,
      });
    }
    // Seasons come second because the comparison chooses the competition when
    // the URL does not, and 2008-2026 is the IPL's calendar, not cricket's.
    seasons = await api<SeasonMeta[]>("/api/meta/seasons", {
      competition: data?.scope?.competitions,
    });
  } catch (err) {
    const e = err as ApiError;
    return (
      <Section>
        {e.status === 503 ? <NoDataState /> : <ErrorState title="Could not load the comparison" detail={e.message} />}
      </Section>
    );
  }

  const players = data?.players ?? [];
  const colors = players.map((_, i) => SERIES[i % SERIES.length]);
  const anyBatting = players.some((p) => (p.batting?.balls ?? 0) > 0);
  const anyBowling = players.some((p) => (p.bowling?.balls ?? 0) > 0);

  return (
    <>
      <PageHeader
        title="Player Comparison"
        subtitle="Up to four players side by side on the same filtered sample. A leading value is tinted green; it is not a verdict — a higher strike rate at a lower average is a different player, not a worse one."
        crumbs={[{ label: "Stryk", href: "/" }, { label: "Compare" }]}
        meta={<span className="text-2xs text-ink-faint">{describeFilters(searchParams)}</span>}
      />
      <FilterBar seasons={seasons} />

      <Section className="space-y-4">
        <Panel>
          <PanelHeader
            title="Selection"
            description="Pick two to four players. Season, phase and innings filters below apply identically to everyone shown, so the samples stay comparable."
          />
          <PanelBody className="flex flex-wrap items-start gap-3">
            <PlayerPicker param="player" max={4} className="w-64" placeholder="Add a player…" />
            <div className="flex flex-wrap items-center gap-2 pt-0.5">
              {players.map((p, i) => (
                <SelectedChip
                  key={p.player.id}
                  param="player"
                  id={p.player.id}
                  name={p.player.name}
                  color={colors[i]}
                />
              ))}
            </div>
          </PanelBody>
          {players.length > 1 && data?.competitions.length ? (
            <PanelBody className="border-t border-line">
              <CompetitionSwitcher
                options={data.competitions}
                current={data.scope?.competitions[0]}
                // Only the players survive the switch: a season filter means
                // something different in another competition, and most of
                // these seasons do not exist in the one being moved to.
                basePath={`/compare?${ids.map((id) => `player=${id}`).join("&")}`}
                label="Common ground"
                singleAsText={false}
              />
            </PanelBody>
          ) : null}
        </Panel>

        {players.length === 0 ? (
          <Panel>
            <EmptyState
              title="No players selected"
              detail="Search for a player above to begin. You can also arrive here from any player profile using the Compare button."
            />
          </Panel>
        ) : players.length === 1 ? (
          <Panel>
            <EmptyState
              title="Add one more player"
              detail={`${players[0].player.name} is selected. A comparison needs at least two.`}
            />
          </Panel>
        ) : !data?.competitions.length ? (
          <Panel>
            <EmptyState
              title="No competition in common"
              detail={`${names(players)} have never played in the same competition. Records are never pooled across genders or formats, so there is no sample they can all be measured on — each player's own profile holds their record on its own terms.`}
            />
          </Panel>
        ) : (
          <>
            <Contenders players={players} />

            <Panel>
              <PanelHeader
                title="Head to head"
                description="One row per metric, one column per player, under the current filters. Batting and bowling are sections of the same table — every row covers everyone selected."
              />
              <ComparisonTable
                players={players}
                colors={colors}
                sections={[
                  ...(anyBatting ? [{ title: "Batting", rows: BATTING_ROWS }] : []),
                  ...(anyBowling ? [{ title: "Bowling", rows: BOWLING_ROWS }] : []),
                ]}
              />
            </Panel>

            <Panel>
              <AnalysisTabs
                tabs={[
                  {
                    value: "shape",
                    label: "Profile shape",
                    content: (
                      <div className="grid min-w-0 gap-4 lg:grid-cols-2 [&>*]:min-w-0">
                        {anyBatting ? (
                          <div className="border-r border-line">
                            <PanelHeader title="Batting profile" />
                            <CompareRadar players={players} kind="batting" />
                          </div>
                        ) : null}
                        {anyBowling ? (
                          <div>
                            <PanelHeader title="Bowling profile" />
                            <CompareRadar players={players} kind="bowling" />
                          </div>
                        ) : null}
                      </div>
                    ),
                  },
                  {
                    value: "seasons",
                    label: "Season by season",
                    content: (
                      <PanelBody className="space-y-6">
                        <p className="text-xs leading-relaxed text-ink-muted">
                          A season a player did not appear in is a gap in the line, never a zero.
                        </p>
                        {anyBatting ? (
                          <div className="space-y-4">
                            <div>
                              <p className="label-xs mb-2">Runs by season</p>
                              <CompareSeasons players={players} kind="batting" metric="runs" />
                            </div>
                            <div>
                              <p className="label-xs mb-2">Strike rate by season</p>
                              <CompareSeasons players={players} kind="batting" metric="strike_rate" />
                            </div>
                          </div>
                        ) : null}
                        {anyBowling ? (
                          <div className="space-y-4">
                            <div>
                              <p className="label-xs mb-2">Wickets by season</p>
                              <CompareSeasons players={players} kind="bowling" metric="wickets" />
                            </div>
                            <div>
                              <p className="label-xs mb-2">Economy by season</p>
                              <CompareSeasons players={players} kind="bowling" metric="economy" />
                            </div>
                          </div>
                        ) : null}
                      </PanelBody>
                    ),
                  },
                  {
                    value: "phases",
                    label: "By phase",
                    content: (
                      <PanelBody className="space-y-5">
                        <p className="text-xs leading-relaxed text-ink-muted">
                          Powerplay 1–6, middle 7–15, death 16–20. A bar is absent where the player
                          has not batted or bowled in that phase under the current filters.
                        </p>
                        {anyBatting ? (
                          <div>
                            <p className="label-xs mb-2">Batting strike rate by phase</p>
                            <ComparePhases players={players} kind="batting" metric="strike_rate" />
                          </div>
                        ) : null}
                        {anyBowling ? (
                          <div>
                            <p className="label-xs mb-2">Bowling economy by phase</p>
                            <ComparePhases players={players} kind="bowling" metric="economy" />
                          </div>
                        ) : null}
                      </PanelBody>
                    ),
                  },
                  {
                    value: "innings",
                    label: "Chasing vs setting",
                    content: (
                      <PanelBody>
                        <ChaseTable players={players} colors={colors} />
                      </PanelBody>
                    ),
                  },
                  {
                    value: "consistency",
                    label: "Consistency",
                    content: (
                      <PanelBody>
                        <ConsistencyTable players={players} colors={colors} />
                      </PanelBody>
                    ),
                  },
                ]}
              />
            </Panel>
          </>
        )}
      </Section>
    </>
  );
}

/** "A and B", "A, B and C" — the Oxford comma is not used elsewhere in the UI. */
function names(players: PlayerProfile[]): string {
  const all = players.map((p) => p.player.name);
  return all.length < 2 ? (all[0] ?? "") : `${all.slice(0, -1).join(", ")} and ${all.at(-1)}`;
}

/** Batting first vs chasing, one row per player per situation. */
function ChaseTable({ players, colors }: { players: PlayerProfile[]; colors: string[] }) {
  const rows = players.flatMap((p, i) =>
    (
      [
        ["Batting first", p.batting_by_innings_type.setting[0]],
        ["Chasing", p.batting_by_innings_type.chasing[0]],
      ] as const
    )
      .filter(([, line]) => line && (line.balls ?? 0) > 0)
      .map(([situation, line]) => ({ player: p.player.name, color: colors[i], situation, line: line! })),
  );
  if (!rows.length) return <EmptyState title="No batting innings under these filters" className="py-10" />;
  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            <Th>Player</Th>
            <Th>Situation</Th>
            <Th numeric>Inns</Th>
            <Th numeric>Runs</Th>
            <Th numeric>Avg</Th>
            <Th numeric>SR</Th>
            <Th numeric>Bdry%</Th>
            <Th numeric>Dot%</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <Tr key={i}>
              <Td>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-sm" style={{ background: r.color }} aria-hidden />
                  {r.player}
                </span>
              </Td>
              <Td className="text-ink-muted">{r.situation}</Td>
              <Td numeric>{num(r.line.innings)}</Td>
              <Td numeric className="font-medium">{num(r.line.runs)}</Td>
              <Td numeric>{dec(r.line.average)}</Td>
              <Td numeric>{dec(r.line.strike_rate)}</Td>
              <Td numeric className="text-ink-muted">{pct(r.line.boundary_pct)}</Td>
              <Td numeric className="text-ink-muted">{pct(r.line.dot_pct)}</Td>
            </Tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  );
}

/**
 * Consistency here is the spread of a player's season-by-season figures, not a
 * proprietary index: the number of qualifying seasons, the best and worst, and
 * the standard deviation across them.
 */
function spread(values: number[]) {
  if (values.length < 2) return null;
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const variance = values.reduce((a, b) => a + (b - mean) ** 2, 0) / (values.length - 1);
  return { mean, sd: Math.sqrt(variance), min: Math.min(...values), max: Math.max(...values) };
}

function ConsistencyTable({ players, colors }: { players: PlayerProfile[]; colors: string[] }) {
  const rows = players.map((p, i) => {
    // Only seasons with a real sample count: a 12-ball season is noise.
    const batSeasons = p.batting_by_season.filter((s) => (s.balls ?? 0) >= 60);
    const bowlSeasons = p.bowling_by_season.filter((s) => (s.balls ?? 0) >= 60);
    return {
      name: p.player.name,
      color: colors[i],
      batSeasons: batSeasons.length,
      runs: spread(batSeasons.map((s) => s.runs)),
      sr: spread(batSeasons.map((s) => s.strike_rate).filter((v): v is number => v != null)),
      bowlSeasons: bowlSeasons.length,
      econ: spread(bowlSeasons.map((s) => s.economy).filter((v): v is number => v != null)),
    };
  });
  return (
    <div className="space-y-3">
      <p className="text-xs leading-relaxed text-ink-muted">
        Spread across qualifying seasons — those with at least 60 balls faced or bowled. A low
        standard deviation means a player repeated the same season; it does not mean that season was
        a good one.
      </p>
      <TableWrap>
        <Table>
          <thead>
            <tr>
              <Th>Player</Th>
              <Th numeric>Qual. batting seasons</Th>
              <Th numeric>Runs per season</Th>
              <Th numeric>Runs SD</Th>
              <Th numeric>Strike rate range</Th>
              <Th numeric>SR SD</Th>
              <Th numeric>Qual. bowling seasons</Th>
              <Th numeric>Economy range</Th>
              <Th numeric>Econ SD</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <Tr key={r.name}>
                <Td>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-sm" style={{ background: r.color }} aria-hidden />
                    {r.name}
                  </span>
                </Td>
                <Td numeric>{num(r.batSeasons)}</Td>
                <Td numeric>{dec(r.runs?.mean ?? null, 0)}</Td>
                <Td numeric>{dec(r.runs?.sd ?? null, 1)}</Td>
                <Td numeric className="text-ink-muted">
                  {r.sr ? `${dec(r.sr.min, 1)}–${dec(r.sr.max, 1)}` : "—"}
                </Td>
                <Td numeric>{dec(r.sr?.sd ?? null, 1)}</Td>
                <Td numeric>{num(r.bowlSeasons)}</Td>
                <Td numeric className="text-ink-muted">
                  {r.econ ? `${dec(r.econ.min, 2)}–${dec(r.econ.max, 2)}` : "—"}
                </Td>
                <Td numeric>{dec(r.econ?.sd ?? null, 2)}</Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      </TableWrap>
    </div>
  );
}
