import * as React from "react";
import Link from "next/link";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { EmptyState } from "@/components/ui/states";
import { Badge } from "@/components/ui/badge";
import { dec, num, pct, shortDate, signed } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Matchup } from "@/types";

const PHASE_LABEL: Record<string, string> = {
  powerplay: "Powerplay (1–6)",
  middle: "Middle (7–15)",
  death: "Death (16–20)",
};

/**
 * The match-up numbers are meaningless without the two baselines beside them:
 * a 110 strike rate is a success for the bowler against a 150 batter and a
 * failure against a 95 one. Every headline row therefore carries the batter's
 * overall figure and the delta.
 */
export function HeadToHead({ m }: { m: Matchup }) {
  const s = m.summary;
  const bat = m.baseline.batter;
  const bowl = m.baseline.bowler;

  const rows = [
    {
      label: "Strike rate",
      value: dec(s.strike_rate),
      baseline: dec(bat?.strike_rate),
      delta: delta(s.strike_rate, bat?.strike_rate),
      better: "high" as const,
      hint: "Runs off this bowler ÷ balls faced from them × 100.",
    },
    {
      label: "Dot %",
      value: pct(s.dot_pct),
      baseline: pct(bat?.dot_pct),
      delta: delta(s.dot_pct, bat?.dot_pct),
      better: "low" as const,
      hint: "Share of these deliveries that produced no run off the bat.",
    },
    {
      label: "Boundary %",
      value: pct(s.boundary_pct),
      baseline: pct(bat?.boundary_pct),
      delta: delta(s.boundary_pct, bat?.boundary_pct),
      better: "high" as const,
      hint: "Share of these deliveries hit for four or six.",
    },
    {
      label: "Balls per dismissal",
      value: dec(s.balls_per_dismissal),
      baseline: dec(bowl?.strike_rate),
      delta: null,
      better: "high" as const,
      hint: "Balls the batter survived per dismissal in this match-up, against the bowler's career balls-per-wicket.",
    },
  ];

  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            <Th>Metric</Th>
            <Th numeric>In this match-up</Th>
            <Th numeric>Batter&apos;s overall</Th>
            <Th numeric>Difference</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <Tr key={r.label}>
              <Td className="text-ink-muted" title={r.hint}>
                {r.label}
              </Td>
              <Td numeric className="font-medium">{r.value}</Td>
              <Td numeric className="text-ink-muted">{r.baseline}</Td>
              <Td
                numeric
                className={cn(
                  r.delta === null
                    ? "text-ink-faint"
                    : (r.better === "high") === r.delta > 0
                      ? "text-accent"
                      : "text-signal-down",
                )}
              >
                {r.delta === null ? "—" : signed(r.delta)}
              </Td>
            </Tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  );
}

function delta(a: number | null | undefined, b: number | null | undefined) {
  if (typeof a !== "number" || typeof b !== "number") return null;
  return a - b;
}

export function MatchupPhases({ m }: { m: Matchup }) {
  if (!m.by_phase.length) return <EmptyState title="No phase breakdown available" className="py-8" />;
  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            <Th>Phase</Th>
            <Th numeric>Balls</Th>
            <Th numeric>Runs</Th>
            <Th numeric>Dismissals</Th>
            <Th numeric>SR</Th>
            <Th numeric>Dot%</Th>
          </tr>
        </thead>
        <tbody>
          {m.by_phase.map((p) => (
            <Tr key={p.phase}>
              <Td>{PHASE_LABEL[p.phase] ?? p.phase}</Td>
              <Td numeric className={cn(p.balls < 12 && "text-signal-warn")}>{num(p.balls)}</Td>
              <Td numeric className="font-medium">{num(p.runs)}</Td>
              <Td numeric>{num(p.dismissals)}</Td>
              <Td numeric>{dec(p.strike_rate)}</Td>
              <Td numeric className="text-ink-muted">{pct(p.dot_pct)}</Td>
            </Tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  );
}

export function MatchupSeasons({ m }: { m: Matchup }) {
  if (!m.by_season.length) return <EmptyState title="No seasons in this match-up" className="py-8" />;
  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            <Th>Season</Th>
            <Th numeric>Balls</Th>
            <Th numeric>Runs</Th>
            <Th numeric>Dismissals</Th>
            <Th numeric>SR</Th>
          </tr>
        </thead>
        <tbody>
          {m.by_season.map((s) => (
            <Tr key={s.season}>
              <Td>{s.season}</Td>
              <Td numeric className={cn(s.balls < 12 && "text-signal-warn")}>{num(s.balls)}</Td>
              <Td numeric className="font-medium">{num(s.runs)}</Td>
              <Td numeric>{num(s.dismissals)}</Td>
              <Td numeric>{dec(s.strike_rate)}</Td>
            </Tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  );
}

export function DismissalLog({ m }: { m: Matchup }) {
  if (!m.dismissal_log.length) {
    return (
      <EmptyState
        title="The bowler has never dismissed this batter"
        detail="Under the current filters there is no dismissal to inspect. That is a fact about the sample, not evidence that the batter is immune."
        className="py-8"
      />
    );
  }
  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            <Th>Date</Th>
            <Th>Season</Th>
            <Th>Dismissal</Th>
            <Th>Phase</Th>
            <Th numeric>Over</Th>
            <Th>Credited to bowler</Th>
          </tr>
        </thead>
        <tbody>
          {m.dismissal_log.map((d, i) => (
            <Tr key={i}>
              <Td className="text-ink-muted">{shortDate(d.date)}</Td>
              <Td>{d.season}</Td>
              <Td className="capitalize">{d.kind}</Td>
              <Td className="text-ink-muted">{PHASE_LABEL[d.phase] ?? d.phase}</Td>
              <Td numeric>{d.over + 1}</Td>
              <Td>
                <Badge tone={d.credited_to_bowler ? "accent" : "default"}>
                  {d.credited_to_bowler ? "Yes" : "No — run out or similar"}
                </Badge>
              </Td>
            </Tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  );
}

/** Frequent-opponent list used when only one side of the match-up is chosen. */
export function OpponentList({
  opponents,
  selfId,
  selfRole,
}: {
  opponents: Array<{
    opponent_id: string;
    opponent_name: string;
    balls: number;
    runs: number;
    dismissals: number;
    strike_rate: number | null;
    average: number | null;
    reliability: string;
  }>;
  selfId: string;
  selfRole: "batter" | "bowler";
}) {
  if (!opponents.length) {
    return <EmptyState title="No repeated opponents under these filters" className="py-8" />;
  }
  const otherParam = selfRole === "batter" ? "bowler" : "batter";
  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            <Th>{selfRole === "batter" ? "Bowler" : "Batter"}</Th>
            <Th numeric>Balls</Th>
            <Th numeric>Runs</Th>
            <Th numeric>Dismissals</Th>
            <Th numeric>SR</Th>
            <Th numeric>Avg</Th>
            <Th>Sample</Th>
          </tr>
        </thead>
        <tbody>
          {opponents.map((o) => (
            <Tr key={o.opponent_id}>
              <Td>
                <Link
                  href={`/matchups?${selfRole}=${selfId}&${otherParam}=${o.opponent_id}`}
                  className="text-ink transition-colors hover:text-accent"
                >
                  {o.opponent_name}
                </Link>
              </Td>
              <Td numeric className="text-ink-muted">{num(o.balls)}</Td>
              <Td numeric className="font-medium">{num(o.runs)}</Td>
              <Td numeric>{num(o.dismissals)}</Td>
              <Td numeric>{dec(o.strike_rate)}</Td>
              <Td numeric>{dec(o.average)}</Td>
              <Td>
                <Badge
                  tone={
                    o.reliability === "readable"
                      ? "accent"
                      : o.reliability === "indicative"
                        ? "warn"
                        : "danger"
                  }
                >
                  {o.reliability}
                </Badge>
              </Td>
            </Tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  );
}
