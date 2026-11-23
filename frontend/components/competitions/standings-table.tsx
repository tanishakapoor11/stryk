import { AlertTriangle } from "lucide-react";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { teamColor } from "@/lib/teams";
import { cn } from "@/lib/utils";
import type { Standings } from "@/types";

const TIE_BREAKER_LABEL: Record<string, string> = {
  points: "points",
  wins: "wins",
  net_run_rate: "net run rate",
  wickets_per_ball: "wickets per ball bowled",
};

function signed(v: number | null): string {
  if (v === null || v === undefined) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(3)}`;
}

/**
 * A points table computed under the competition's own rules.
 *
 * The table says where its rules come from and when it is incomplete; it is
 * never presented as the official table when the source is missing matches.
 */
export function StandingsTable({ standings }: { standings: Standings }) {
  if (!standings.available) {
    return <p className="px-4 py-6 text-xs leading-relaxed text-ink-muted">{standings.reason}</p>;
  }
  const ps = standings.points_system;
  const showTied = standings.groups.some((g) => g.rows.some((r) => r.tied));
  const showDrawn = standings.groups.some((g) => g.rows.some((r) => r.drawn));
  return (
    <div>
      {standings.warnings.map((w) => (
        <div
          key={w}
          role="note"
          className="flex gap-2 border-b border-signal-warn/30 bg-signal-warn/5 px-4 py-2.5 text-xs leading-relaxed text-ink-muted"
        >
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-signal-warn" aria-hidden />
          <span>{w}</span>
        </div>
      ))}
      {standings.groups.map((g) => (
        <div key={g.group ?? "table"}>
          {g.group ? <p className="label-xs px-4 pt-3">Group {g.group}</p> : null}
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <Th className="w-10">#</Th>
                  <Th>Team</Th>
                  <Th numeric>P</Th>
                  <Th numeric>W</Th>
                  <Th numeric>L</Th>
                  {showTied ? <Th numeric>T</Th> : null}
                  {showDrawn ? <Th numeric>D</Th> : null}
                  <Th numeric>NR</Th>
                  <Th numeric>Pts</Th>
                  <Th numeric>NRR</Th>
                  <Th numeric className="hidden md:table-cell">For</Th>
                  <Th numeric className="hidden md:table-cell">Against</Th>
                </tr>
              </thead>
              <tbody>
                {g.rows.map((r) => (
                  <Tr key={r.team_id}>
                    <Td className="num text-ink-faint">{r.position}</Td>
                    <Td>
                      <span className="flex items-center gap-2">
                        <span
                          className="h-2.5 w-1 shrink-0 rounded-sm"
                          style={{ backgroundColor: teamColor(r.name) }}
                          aria-hidden
                        />
                        <a href={`/teams/${r.team_id}`} className="hover:text-accent">
                          {r.name}
                        </a>
                        {r.reached_knockouts ? (
                          <Badge tone="accent" title="Played in the knockout stage this season">
                            Knockouts
                          </Badge>
                        ) : null}
                      </span>
                    </Td>
                    <Td numeric>{r.played}</Td>
                    <Td numeric>{r.won}</Td>
                    <Td numeric>{r.lost}</Td>
                    {showTied ? <Td numeric>{r.tied}</Td> : null}
                    {showDrawn ? <Td numeric>{r.drawn}</Td> : null}
                    <Td numeric>{r.no_result}</Td>
                    <Td numeric className="font-semibold">
                      {r.points}
                    </Td>
                    <Td
                      numeric
                      className={cn(
                        r.net_run_rate !== null && r.net_run_rate > 0 && "text-signal-up",
                        r.net_run_rate !== null && r.net_run_rate < 0 && "text-signal-down",
                      )}
                    >
                      {signed(r.net_run_rate)}
                    </Td>
                    <Td numeric className="hidden text-ink-muted md:table-cell">
                      {r.runs_for}/{r.overs_for ?? "—"}
                    </Td>
                    <Td numeric className="hidden text-ink-muted md:table-cell">
                      {r.runs_against}/{r.overs_against ?? "—"}
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        </div>
      ))}
      <div className="space-y-1 border-t border-line px-4 py-3 text-2xs leading-relaxed text-ink-faint">
        <p>
          {ps.name}: win {ps.points.win}, no result {ps.points.no_result}
          {ps.tie_resolution === "super_over"
            ? ", ties settled by super over"
            : `, tie ${ps.points.tie}`}
          . Level teams separated by {ps.tie_breakers.slice(1).map((t) => TIE_BREAKER_LABEL[t] ?? t).join(", then ")}.
          Computed from {standings.matches_counted} league matches in the data.
        </p>
        {ps.sources?.length ? (
          <p>
            Rules checked {ps.verified_on ?? ""} against{" "}
            {ps.sources.map((s, i) => (
              <span key={s}>
                {i ? ", " : ""}
                <a href={s} target="_blank" rel="noreferrer" className="underline hover:text-accent">
                  {new URL(s).hostname.replace(/^www\./, "")}
                </a>
              </span>
            ))}
            .
          </p>
        ) : null}
      </div>
    </div>
  );
}
