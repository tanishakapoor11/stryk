import * as React from "react";
import Link from "next/link";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { dec, num, pct, EMPTY, figures } from "@/lib/format";
import { cn } from "@/lib/utils";
import { PlayerAvatar } from "@/components/ui/player-identity";
import { photoFor } from "@/lib/photos";
import type { PlayerProfile } from "@/types";

/**
 * A metric row knows three things: how to read its value off a profile, how to
 * print it, and which direction is better. "Better" is used only to tint the
 * leading cell — the page never ranks players overall, because no single
 * metric does that honestly.
 */
export interface MetricRow {
  label: string;
  hint?: string;
  get: (p: PlayerProfile) => number | null | undefined;
  format: (v: number | null | undefined) => string;
  better?: "high" | "low";
  /** Below this many balls the cell is shown but never marked as leading. */
  minBalls?: (p: PlayerProfile) => number;
}

const n = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : null);

export const BATTING_ROWS: MetricRow[] = [
  { label: "Innings", get: (p) => p.batting?.innings, format: (v) => num(v) },
  { label: "Runs", get: (p) => p.batting?.runs, format: (v) => num(v), better: "high" },
  { label: "Balls faced", get: (p) => p.batting?.balls, format: (v) => num(v) },
  {
    label: "Average",
    hint: "Runs ÷ dismissals. Not-outs are excluded from the denominator.",
    get: (p) => n(p.batting?.average),
    format: (v) => dec(v),
    better: "high",
  },
  {
    label: "Strike rate",
    hint: "Runs ÷ balls faced × 100. Wides are not counted as balls faced.",
    get: (p) => n(p.batting?.strike_rate),
    format: (v) => dec(v),
    better: "high",
  },
  { label: "Highest score", get: (p) => p.batting?.highest_score, format: (v) => num(v), better: "high" },
  { label: "Fifties", get: (p) => p.batting?.fifties, format: (v) => num(v), better: "high" },
  { label: "Hundreds", get: (p) => p.batting?.hundreds, format: (v) => num(v), better: "high" },
  {
    label: "Boundary %",
    hint: "Share of balls faced hit for four or six.",
    get: (p) => n(p.batting?.boundary_pct),
    format: (v) => pct(v),
    better: "high",
  },
  {
    label: "Dot %",
    hint: "Share of balls faced that yielded no run off the bat.",
    get: (p) => n(p.batting?.dot_pct),
    format: (v) => pct(v),
    better: "low",
  },
  {
    label: "Boundary run %",
    hint: "Share of the player's runs that came in fours and sixes — high values indicate dependence on boundaries rather than strike rotation.",
    get: (p) => n(p.batting?.boundary_run_pct),
    format: (v) => pct(v),
  },
];

export const BOWLING_ROWS: MetricRow[] = [
  { label: "Innings", get: (p) => p.bowling?.innings, format: (v) => num(v) },
  { label: "Balls bowled", get: (p) => p.bowling?.balls, format: (v) => num(v) },
  { label: "Wickets", get: (p) => p.bowling?.wickets, format: (v) => num(v), better: "high" },
  {
    label: "Economy",
    hint: "Runs conceded ÷ overs. Byes and leg-byes are not charged to the bowler.",
    get: (p) => n(p.bowling?.economy),
    format: (v) => dec(v),
    better: "low",
  },
  {
    label: "Average",
    hint: "Runs conceded ÷ wickets credited to the bowler.",
    get: (p) => n(p.bowling?.average),
    format: (v) => dec(v),
    better: "low",
  },
  {
    label: "Strike rate",
    hint: "Legal balls bowled ÷ wickets.",
    get: (p) => n(p.bowling?.strike_rate),
    format: (v) => dec(v),
    better: "low",
  },
  {
    label: "Dot %",
    hint: "Share of legal deliveries that conceded nothing.",
    get: (p) => n(p.bowling?.dot_pct),
    format: (v) => pct(v),
    better: "high",
  },
  // Both of these read two numbers out of one profile, so the table renders
  // them by label rather than through `get`.
  { label: "Best figures", get: () => null, format: () => EMPTY },
  { label: "4w / 5w hauls", get: () => null, format: () => EMPTY },
];

function leaderIndex(players: PlayerProfile[], row: MetricRow): number | null {
  if (!row.better) return null;
  const values = players.map(row.get).map((v) => (typeof v === "number" ? v : null));
  const defined = values.filter((v): v is number => v !== null);
  if (defined.length < 2) return null;
  const best = row.better === "high" ? Math.max(...defined) : Math.min(...defined);
  // A tie has no leader to highlight.
  if (values.filter((v) => v === best).length > 1) return null;
  return values.indexOf(best);
}

export interface MetricSection {
  title: string;
  /** Shown beside the title in the band, for anything the rows cannot say. */
  hint?: string;
  rows: MetricRow[];
}

/**
 * One table, every player a column, batting and bowling as banded sections of
 * it. Two side-by-side tables read as one box per player — the names sit in
 * each box's header, so the discipline heading above them looks like a label
 * for a person. A single table cannot be misread that way: the names appear
 * once, at the top, and every row underneath plainly spans all of them.
 */
export function ComparisonTable({
  players,
  sections,
  colors,
}: {
  players: PlayerProfile[];
  sections: MetricSection[];
  colors: string[];
}) {
  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            {/* The label column takes the slack so the player columns stay
                narrow and adjacent — two values a metric apart are meant to be
                read against each other, not across the page. */}
            <Th className="w-full">Metric</Th>
            {players.map((p, i) => (
              <Th key={p.player.id} numeric className="w-40">
                <span
                  // The name wears its chart colour, so a line in the graphs
                  // below can be traced back to a column up here.
                  className="inline-flex items-center gap-2 border-b-2 pb-1"
                  style={{ borderColor: colors[i] }}
                >
                  <PlayerAvatar
                    name={p.player.name}
                    team={p.player.teams[0]?.team_name}
                    size="sm"
                    photoSrc={photoFor(p.player.id)?.src}
                  />
                  <Link
                    href={`/players/${p.player.id}`}
                    className="font-display text-xs font-semibold text-ink hover:text-accent"
                  >
                    {p.player.name}
                  </Link>
                </span>
              </Th>
            ))}
          </tr>
        </thead>
        {sections.map((section) => (
          <tbody key={section.title}>
            <tr>
              <th
                scope="colgroup"
                colSpan={players.length + 1}
                className="border-y border-l-2 border-line-strong border-l-accent bg-surface-sunken px-3 py-2.5 text-left"
              >
                <span className="font-display text-sm font-semibold uppercase tracking-[0.14em] text-ink">
                  {section.title}
                </span>
                {section.hint ? (
                  <span className="ml-2.5 text-2xs font-normal normal-case tracking-normal text-ink-faint">
                    {section.hint}
                  </span>
                ) : null}
              </th>
            </tr>
            {section.rows.map((row) => {
              const lead = leaderIndex(players, row);
              return (
                <Tr key={row.label}>
                  <Td className="text-ink-muted" title={row.hint}>
                    {row.label}
                  </Td>
                  {players.map((p, i) => {
                    const special =
                      row.label === "4w / 5w hauls"
                        ? `${num(p.bowling?.four_wicket_hauls)} / ${num(p.bowling?.five_wicket_hauls)}`
                        : row.label === "Best figures"
                          ? figures(p.bowling?.best_wickets, p.bowling?.best_runs)
                          : null;
                    return (
                      <Td
                        key={p.player.id}
                        numeric
                        className={cn(lead === i && "font-medium text-accent")}
                      >
                        {special ?? row.format(row.get(p))}
                      </Td>
                    );
                  })}
                </Tr>
              );
            })}
          </tbody>
        ))}
      </Table>
    </TableWrap>
  );
}
