import * as React from "react";
import Link from "next/link";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { EmptyState } from "@/components/ui/states";
import { dec, num, pct, figures } from "@/lib/format";
import type { BattingLine, BowlingLine } from "@/types";

/**
 * One batting table and one bowling table, reused for every split in the app
 * (phase, season, venue, opposition, innings type). The caller supplies the
 * label column; the statistic columns are identical everywhere so a reader
 * learns the layout once.
 */
export interface SplitColumn<T> {
  header: string;
  render: (row: T) => React.ReactNode;
}

export function BattingSplitTable<T extends Partial<BattingLine>>({
  rows,
  label,
  empty = "No batting in this split.",
  dense,
}: {
  rows: T[];
  label: SplitColumn<T>;
  empty?: string;
  dense?: boolean;
}) {
  if (!rows.length) return <EmptyState title={empty} className="py-8" />;
  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            <Th>{label.header}</Th>
            <Th numeric>Inns</Th>
            <Th numeric>Runs</Th>
            <Th numeric>Balls</Th>
            <Th numeric>Avg</Th>
            <Th numeric>SR</Th>
            {dense ? null : (
              <>
                <Th numeric>HS</Th>
                <Th numeric>4s</Th>
                <Th numeric>6s</Th>
                <Th numeric>50/100</Th>
              </>
            )}
            <Th numeric>Bdry%</Th>
            <Th numeric>Dot%</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <Tr key={i}>
              <Td className="max-w-[220px] truncate">{label.render(r)}</Td>
              <Td numeric>{num(r.innings)}</Td>
              <Td numeric className="font-medium">{num(r.runs)}</Td>
              <Td numeric className="text-ink-muted">{num(r.balls)}</Td>
              <Td numeric>{dec(r.average)}</Td>
              <Td numeric>{dec(r.strike_rate)}</Td>
              {dense ? null : (
                <>
                  <Td numeric>
                    {num(r.highest_score)}
                    {r.highest_not_out ? "*" : ""}
                  </Td>
                  <Td numeric className="text-ink-muted">{num(r.fours)}</Td>
                  <Td numeric className="text-ink-muted">{num(r.sixes)}</Td>
                  <Td numeric className="text-ink-muted">
                    {num(r.fifties)}/{num(r.hundreds)}
                  </Td>
                </>
              )}
              <Td numeric className="text-ink-muted">{pct(r.boundary_pct)}</Td>
              <Td numeric className="text-ink-muted">{pct(r.dot_pct)}</Td>
            </Tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  );
}

export function BowlingSplitTable<T extends Partial<BowlingLine>>({
  rows,
  label,
  empty = "No bowling in this split.",
  dense,
}: {
  rows: T[];
  label: SplitColumn<T>;
  empty?: string;
  dense?: boolean;
}) {
  if (!rows.length) return <EmptyState title={empty} className="py-8" />;
  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            <Th>{label.header}</Th>
            <Th numeric>Inns</Th>
            <Th numeric>Overs</Th>
            <Th numeric>Runs</Th>
            <Th numeric>Wkts</Th>
            <Th numeric>Econ</Th>
            <Th numeric>Avg</Th>
            <Th numeric>SR</Th>
            {dense ? null : (
              <>
                <Th numeric>Best</Th>
                <Th numeric>4w/5w</Th>
              </>
            )}
            <Th numeric>Dot%</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <Tr key={i}>
              <Td className="max-w-[220px] truncate">{label.render(r)}</Td>
              <Td numeric>{num(r.innings)}</Td>
              <Td numeric className="text-ink-muted">{r.overs ?? "—"}</Td>
              <Td numeric className="text-ink-muted">{num(r.runs)}</Td>
              <Td numeric className="font-medium">{num(r.wickets)}</Td>
              <Td numeric>{dec(r.economy)}</Td>
              <Td numeric>{dec(r.average)}</Td>
              <Td numeric>{dec(r.strike_rate)}</Td>
              {dense ? null : (
                <>
                  <Td numeric>{figures(r.best_wickets, r.best_runs)}</Td>
                  <Td numeric className="text-ink-muted">
                    {num(r.four_wicket_hauls)}/{num(r.five_wicket_hauls)}
                  </Td>
                </>
              )}
              <Td numeric className="text-ink-muted">{pct(r.dot_pct)}</Td>
            </Tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  );
}

/** Plain text label column factory for the common "string key" case. */
export const textLabel = <T,>(header: string, key: keyof T): SplitColumn<T> => ({
  header,
  render: (row) => <span>{String(row[key] ?? "—")}</span>,
});

export const playerLinkLabel = <T extends { player_id?: string; player_name?: string }>(
  header = "Player",
): SplitColumn<T> => ({
  header,
  render: (row) =>
    row.player_id ? (
      <Link href={`/players/${row.player_id}`} className="text-ink hover:text-accent">
        {row.player_name}
      </Link>
    ) : (
      <span>{row.player_name ?? "—"}</span>
    ),
});
