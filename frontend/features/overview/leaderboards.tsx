"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { Panel, PanelHeader } from "@/components/ui/card";
import { PlayerName } from "@/components/ui/player-identity";
import { dec, num, pct, shortDate } from "@/lib/format";
import type { OverviewPayload } from "@/types";

type Boards = OverviewPayload["leaderboards"];

function PlayerCell({ id, name }: { id?: string; name?: string }) {
  if (!id || !name) return <>{name ?? "—"}</>;
  return <PlayerName id={id} name={name} size="sm" />;
}

export function Leaderboards({ boards }: { boards: Boards }) {
  if (!boards?.most_runs) return null;
  return (
    <Panel>
      <PanelHeader
        title="Leaderboards"
        description="Rate statistics carry a minimum qualification so a 40-ball cameo cannot top a career list."
      />
      <Tabs defaultValue="runs">
        <TabsList className="px-2">
          <TabsTrigger value="runs">Runs</TabsTrigger>
          <TabsTrigger value="wickets">Wickets</TabsTrigger>
          <TabsTrigger value="scores">Top scores</TabsTrigger>
          <TabsTrigger value="figures">Best figures</TabsTrigger>
          <TabsTrigger value="sr">Strike rate</TabsTrigger>
          <TabsTrigger value="econ">Economy</TabsTrigger>
          <TabsTrigger value="avg">Average</TabsTrigger>
        </TabsList>

        <TabsContent value="runs">
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <Th>Player</Th>
                  <Th numeric>Inns</Th>
                  <Th numeric>Runs</Th>
                  <Th numeric>Avg</Th>
                  <Th numeric>SR</Th>
                  <Th numeric>50s</Th>
                  <Th numeric>100s</Th>
                </tr>
              </thead>
              <tbody>
                {boards.most_runs.map((r: any) => (
                  <Tr key={r.player_id}>
                    <Td><PlayerCell id={r.player_id} name={r.player_name} /></Td>
                    <Td numeric>{num(r.innings)}</Td>
                    <Td numeric className="text-accent">{num(r.runs)}</Td>
                    <Td numeric>{dec(r.average)}</Td>
                    <Td numeric>{dec(r.strike_rate)}</Td>
                    <Td numeric>{num(r.fifties)}</Td>
                    <Td numeric>{num(r.hundreds)}</Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        </TabsContent>

        <TabsContent value="wickets">
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <Th>Player</Th>
                  <Th numeric>Overs</Th>
                  <Th numeric>Wkts</Th>
                  <Th numeric>Avg</Th>
                  <Th numeric>Econ</Th>
                  <Th numeric>SR</Th>
                  <Th numeric>4w</Th>
                </tr>
              </thead>
              <tbody>
                {boards.most_wickets.map((r: any) => (
                  <Tr key={r.player_id}>
                    <Td><PlayerCell id={r.player_id} name={r.player_name} /></Td>
                    <Td numeric>{r.overs}</Td>
                    <Td numeric className="text-accent">{num(r.wickets)}</Td>
                    <Td numeric>{dec(r.average)}</Td>
                    <Td numeric>{dec(r.economy)}</Td>
                    <Td numeric>{dec(r.strike_rate, 1)}</Td>
                    <Td numeric>{num(r.four_wicket_hauls)}</Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        </TabsContent>

        <TabsContent value="scores">
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <Th>Player</Th>
                  <Th numeric>Score</Th>
                  <Th numeric>Balls</Th>
                  <Th numeric>SR</Th>
                  <Th>Against</Th>
                  <Th>Date</Th>
                </tr>
              </thead>
              <tbody>
                {boards.highest_scores.map((r: any, i: number) => (
                  <Tr key={`${r.player_id}-${i}`}>
                    <Td><PlayerCell id={r.player_id} name={r.player_name} /></Td>
                    <Td numeric className="text-accent">
                      {num(r.runs)}{r.out ? "" : "*"}
                    </Td>
                    <Td numeric>{num(r.balls)}</Td>
                    <Td numeric>{dec((r.runs / r.balls) * 100)}</Td>
                    <Td className="text-ink-muted">{r.opposition}</Td>
                    <Td className="text-ink-muted">{shortDate(r.date)}</Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        </TabsContent>

        <TabsContent value="figures">
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <Th>Player</Th>
                  <Th numeric>Figures</Th>
                  <Th numeric>Overs</Th>
                  <Th>Against</Th>
                  <Th numeric>Season</Th>
                </tr>
              </thead>
              <tbody>
                {boards.best_figures.map((r: any, i: number) => (
                  <Tr key={`${r.player_id}-${i}`}>
                    <Td><PlayerCell id={r.player_id} name={r.player_name} /></Td>
                    <Td numeric className="text-accent">{r.figures}</Td>
                    <Td numeric>{r.overs}</Td>
                    <Td className="text-ink-muted">{r.opposition}</Td>
                    <Td numeric className="text-ink-muted">{r.season}</Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        </TabsContent>

        <TabsContent value="sr">
          <QualifiedTable
            board={boards.best_strike_rate}
            columns={[
              { key: "strike_rate", label: "SR", accent: true, format: (v) => dec(v) },
              { key: "runs", label: "Runs", format: (v) => num(v) },
              { key: "balls", label: "Balls", format: (v) => num(v) },
              { key: "boundary_pct", label: "Bdry %", format: (v) => pct(v) },
            ]}
          />
        </TabsContent>
        <TabsContent value="econ">
          <QualifiedTable
            board={boards.best_economy}
            columns={[
              { key: "economy", label: "Econ", accent: true, format: (v) => dec(v) },
              { key: "wickets", label: "Wkts", format: (v) => num(v) },
              { key: "overs", label: "Overs", format: (v) => String(v) },
              { key: "dot_pct", label: "Dot %", format: (v) => pct(v) },
            ]}
          />
        </TabsContent>
        <TabsContent value="avg">
          <QualifiedTable
            board={boards.best_average}
            columns={[
              { key: "average", label: "Avg", accent: true, format: (v) => dec(v) },
              { key: "runs", label: "Runs", format: (v) => num(v) },
              { key: "innings", label: "Inns", format: (v) => num(v) },
              { key: "not_outs", label: "NO", format: (v) => num(v) },
            ]}
          />
        </TabsContent>
      </Tabs>
    </Panel>
  );
}

function QualifiedTable({
  board,
  columns,
}: {
  board: { qualification: string; rows: any[] };
  columns: { key: string; label: string; accent?: boolean; format: (v: any) => string }[];
}) {
  return (
    <>
      <p className="border-b border-line px-4 py-2 text-2xs text-ink-faint">
        Qualification: {board.qualification}
      </p>
      <TableWrap>
        <Table>
          <thead>
            <tr>
              <Th>Player</Th>
              {columns.map((c) => (
                <Th key={c.key} numeric>{c.label}</Th>
              ))}
            </tr>
          </thead>
          <tbody>
            {board.rows.map((r: any) => (
              <Tr key={r.player_id}>
                <Td><PlayerCell id={r.player_id} name={r.player_name} /></Td>
                {columns.map((c) => (
                  <Td key={c.key} numeric className={c.accent ? "text-accent" : undefined}>
                    {c.format(r[c.key])}
                  </Td>
                ))}
              </Tr>
            ))}
          </tbody>
        </Table>
      </TableWrap>
    </>
  );
}
