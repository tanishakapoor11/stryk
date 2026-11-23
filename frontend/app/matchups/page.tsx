import { api, apiOrNull, ApiError } from "@/lib/api";
import { filterQuery, describeFilters, one, type RawParams } from "@/lib/search-params";
import { PageHeader, Section } from "@/components/layout/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/card";
import { Stat, StatRow } from "@/components/ui/stat";
import { EmptyState, ErrorState, NoDataState } from "@/components/ui/states";
import { FilterBar } from "@/features/filters/filter-bar";
import { PlayerPicker, SelectedChip } from "@/features/compare/player-picker";
import { AnalysisTabs } from "@/features/players/analysis-tabs";
import { ReliabilityBanner } from "@/features/matchups/reliability";
import { VersusHeader } from "@/features/matchups/versus-header";
import {
  DismissalLog,
  HeadToHead,
  MatchupPhases,
  MatchupSeasons,
  OpponentList,
} from "@/features/matchups/matchup-view";
import { MethodNotes } from "@/features/players/method-notes";
import { dec, num, pct } from "@/lib/format";
import type { Matchup, MatchupOpponent, MetricMeta, PlayerProfile, SeasonMeta } from "@/types";

export const metadata = { title: "Match-up Analysis" };

export default async function MatchupsPage({ searchParams }: { searchParams: RawParams }) {
  const batterId = one(searchParams, "batter");
  const bowlerId = one(searchParams, "bowler");
  const filters = filterQuery(searchParams);

  let seasons: SeasonMeta[];
  let meta: MetricMeta;
  let matchup: Matchup | null = null;
  let batter: PlayerProfile | null = null;
  let bowler: PlayerProfile | null = null;
  let opponents: MatchupOpponent[] = [];

  try {
    [seasons, meta] = await Promise.all([
      api<SeasonMeta[]>("/api/meta/seasons"),
      api<MetricMeta>("/api/meta/metrics"),
    ]);

    if (batterId && bowlerId) {
      [matchup, batter, bowler] = await Promise.all([
        apiOrNull<Matchup>("/api/matchup", { ...filters, batter: batterId, bowler: bowlerId }),
        apiOrNull<PlayerProfile>(`/api/players/${batterId}`),
        apiOrNull<PlayerProfile>(`/api/players/${bowlerId}`),
      ]);
    } else if (batterId || bowlerId) {
      const id = (batterId ?? bowlerId)!;
      const role = batterId ? "batter" : "bowler";
      const [profile, list] = await Promise.all([
        apiOrNull<PlayerProfile>(`/api/players/${id}`),
        api<MatchupOpponent[]>(`/api/players/${id}/matchups`, {
          ...filters,
          as_role: role,
          limit: 20,
        }).catch(() => [] as MatchupOpponent[]),
      ]);
      if (batterId) batter = profile;
      else bowler = profile;
      opponents = list;
    }
  } catch (err) {
    const e = err as ApiError;
    return (
      <Section>
        {e.status === 503 ? <NoDataState /> : <ErrorState title="Could not load the match-up" detail={e.message} />}
      </Section>
    );
  }

  const title =
    batter && bowler
      ? `${batter.player.name} vs ${bowler.player.name}`
      : "Match-up Analysis";

  return (
    <>
      <PageHeader
        title={title}
        subtitle="Ball-by-ball head-to-head between one batter and one bowler. T20 match-up samples are small by nature — the sample size is shown before the statistics, and a handful of deliveries is never treated as a trend."
        crumbs={[{ label: "Stryk", href: "/" }, { label: "Match-ups" }]}
        meta={<span className="text-2xs text-ink-faint">{describeFilters(searchParams)}</span>}
      />
      <FilterBar seasons={seasons} />

      <Section className="space-y-4">
        <Panel>
          <PanelHeader
            title="Select the match-up"
            description="Choose a batter and a bowler. Pick only one and you get their most-faced opponents instead, as a starting point."
          />
          <PanelBody className="grid gap-4 sm:grid-cols-2 lg:max-w-2xl">
            <div>
              <PlayerPicker param="batter" mode="set" label="Batter" placeholder="Search batter…" />
              {batter ? (
                <div className="mt-2">
                  <SelectedChip param="batter" id={batter.player.id} name={batter.player.name} />
                </div>
              ) : null}
            </div>
            <div>
              <PlayerPicker param="bowler" mode="set" label="Bowler" placeholder="Search bowler…" />
              {bowler ? (
                <div className="mt-2">
                  <SelectedChip param="bowler" id={bowler.player.id} name={bowler.player.name} />
                </div>
              ) : null}
            </div>
          </PanelBody>
        </Panel>

        {!batterId && !bowlerId ? (
          <Panel>
            <EmptyState
              title="No match-up selected"
              detail="Search for a batter, a bowler, or both. Season, phase and innings filters narrow the sample — and will usually shrink it below what can be read."
            />
          </Panel>
        ) : null}

        {(batterId || bowlerId) && !matchup && opponents !== null && !(batterId && bowlerId) ? (
          <Panel>
            <PanelHeader
              title="Most-faced opponents"
              description="The opponents this player has the largest ball-by-ball sample against. Click one to open the full head-to-head."
            />
            <OpponentList
              opponents={opponents}
              selfId={(batterId ?? bowlerId)!}
              selfRole={batterId ? "batter" : "bowler"}
            />
          </Panel>
        ) : null}

        {batterId && bowlerId && !matchup ? (
          <Panel>
            <ErrorState
              title="One of those players could not be found"
              detail="Check the ids in the URL, or search for both players again."
            />
          </Panel>
        ) : null}

        {matchup ? (
          <>
            <ReliabilityBanner matchup={matchup} />

            {batter && bowler ? (
              <VersusHeader batter={batter} bowler={bowler} matchup={matchup} />
            ) : null}

            <Panel className="rounded-lg">
              <PanelHeader
                title="The rest of the record"
                description="Every legal and illegal delivery this bowler has sent down to this batter under the current filters."
              />
              <StatRow className="lg:grid-cols-4">
                <Stat label="Innings" value={num(matchup.sample.innings)} sub={`${matchup.sample.matches} matches`} />
                <Stat
                  label="Credited to the bowler"
                  value={num(matchup.summary.bowler_dismissals)}
                  sub={`of ${num(matchup.summary.dismissals)} dismissals`}
                  hint="Run-outs and similar end the batter's innings but are not the bowler's wicket."
                />
                <Stat
                  label="Boundary %"
                  value={pct(matchup.summary.boundary_pct)}
                  sub={`${num(matchup.summary.fours)}×4 · ${num(matchup.summary.sixes)}×6`}
                />
                <Stat
                  label="Balls per dismissal"
                  value={dec(matchup.summary.balls_per_dismissal)}
                  hint="How long the batter survived per dismissal in this match-up."
                />
              </StatRow>
            </Panel>

            <Panel>
              <AnalysisTabs
                tabs={[
                  {
                    value: "baseline",
                    label: "Against baseline",
                    content: (
                      <div>
                        <PanelHeader
                          title="How this differs from the batter's normal game"
                          description="A match-up number only means something next to what the batter usually does. Green marks a difference in the batter's favour."
                        />
                        <HeadToHead m={matchup} />
                      </div>
                    ),
                  },
                  {
                    value: "phase",
                    label: "By phase",
                    content: (
                      <div>
                        <PanelHeader
                          title="Phase split"
                          description="Powerplay 1–6, middle 7–15, death 16–20. Ball counts under 12 are tinted: they cannot support a conclusion."
                        />
                        <MatchupPhases m={matchup} />
                      </div>
                    ),
                  },
                  {
                    value: "season",
                    label: "By season",
                    content: (
                      <div>
                        <PanelHeader
                          title="Season split"
                          description="Both players change across a decade. Where the balls are spread thin, read the total rather than the year."
                        />
                        <MatchupSeasons m={matchup} />
                      </div>
                    ),
                  },
                  {
                    value: "dismissals",
                    label: "Dismissals",
                    content: (
                      <div>
                        <PanelHeader
                          title="Every dismissal in this match-up"
                          description="Including dismissals not credited to the bowler, which are marked as such."
                        />
                        <DismissalLog m={matchup} />
                      </div>
                    ),
                  },
                ]}
              />
            </Panel>

            <MethodNotes
              metrics={meta.metrics}
              qualification={meta.qualification}
              notes={
                <>
                  <p>
                    {String(matchup.notes.dismissals ?? "")} {String(matchup.notes.bowler_dismissals ?? "")}
                  </p>
                  <p className="mt-2">
                    Stryk does not publish &ldquo;versus left-arm pace&rdquo; or similar style
                    splits for the IPL: Cricsheet ball-by-ball files carry no bowling style or
                    bowling arm, and inferring one would be invention rather than analysis. Named
                    bowler match-ups are offered in their place.
                  </p>
                </>
              }
            />
          </>
        ) : null}
      </Section>
    </>
  );
}
