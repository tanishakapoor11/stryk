"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, Check, Minus, Plus } from "lucide-react";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PlayerAvatar } from "@/components/ui/player-identity";
import { Button } from "@/components/ui/button";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { EmptyState } from "@/components/ui/states";
import { Stat, StatRow } from "@/components/ui/stat";
import { dec, num } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AuctionCandidate, AuctionPool } from "@/types";

/**
 * Hypothetical squad builder.
 *
 * The selection lives in the URL (`squad=id,id,…`) so a squad is a link.
 * Budget arithmetic is only offered when real auction prices have been loaded:
 * with no price source, a budget bar would be a number pretending to be a
 * constraint.
 */
export function SquadBuilder({
  pool,
  photos = {},
}: {
  pool: AuctionPool;
  photos?: Record<string, string>;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const squadIds = React.useMemo(
    () => (params.get("squad") ?? "").split(",").filter(Boolean),
    [params],
  );
  const size = Number(params.get("size") ?? 11) || 11;

  const byId = React.useMemo(
    () => new Map(pool.rows.map((r) => [r.player_id, r])),
    [pool.rows],
  );
  // A squad id that is not in the current pool page is kept in the URL but
  // cannot be costed, so it is reported rather than silently dropped.
  const picked = squadIds.map((id) => byId.get(id)).filter(Boolean) as AuctionCandidate[];
  const unresolved = squadIds.length - picked.length;

  const setParam = (key: string, value: string | null) => {
    const sp = new URLSearchParams(Array.from(params.entries()));
    if (value === null || value === "") sp.delete(key);
    else sp.set(key, value);
    router.push(`${pathname}?${sp.toString()}`, { scroll: false });
  };

  const toggle = (id: string) => {
    const next = squadIds.includes(id)
      ? squadIds.filter((x) => x !== id)
      : [...squadIds, id];
    setParam("squad", next.join(","));
  };

  const roleCounts = picked.reduce<Record<string, number>>((acc, p) => {
    const r = p.role ?? "Unclassified";
    acc[r] = (acc[r] ?? 0) + 1;
    return acc;
  }, {});

  const battingImpact = picked.reduce((a, p) => a + (p.batting_impact ?? 0), 0);
  const bowlingImpact = picked.reduce((a, p) => a + (p.bowling_impact ?? 0), 0);
  const spend = pool.prices_available
    ? picked.reduce((a, p) => a + (p.price_inr ?? 0), 0)
    : null;

  return (
    <div className="space-y-4">
      <Panel>
        <PanelHeader
          title="Squad requirements"
          description="Set the squad size and the minimum players you want in each role, then add candidates from the pool below."
          action={
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-1.5 text-2xs text-ink-muted">
                Squad size
                <input
                  type="number"
                  min={1}
                  max={25}
                  value={size}
                  onChange={(e) => setParam("size", e.target.value)}
                  className="num h-7 w-14 rounded border border-line-strong bg-surface-raised px-1.5 text-xs text-ink outline-none focus:border-accent/60"
                />
              </label>
              {squadIds.length ? (
                <Button variant="ghost" onClick={() => setParam("squad", null)}>
                  Clear squad
                </Button>
              ) : null}
            </div>
          }
        />
        <StatRow className={cn("lg:grid-cols-5")}>
          <Stat
            label="Selected"
            value={`${picked.length}/${size}`}
            tone={picked.length === size ? "accent" : "default"}
            sub={picked.length > size ? "over the squad size" : undefined}
          />
          {pool.requirements.map((req) => {
            const have = roleCounts[req.role] ?? 0;
            return (
              <Stat
                key={req.role}
                label={req.role}
                value={`${have}/${req.minimum}`}
                tone={have >= req.minimum ? "accent" : "muted"}
                sub={req.note}
              />
            );
          })}
          <Stat
            label="Squad impact"
            value={`${battingImpact >= 0 ? "+" : ""}${dec(battingImpact, 0)}`}
            sub={`${bowlingImpact >= 0 ? "+" : ""}${dec(bowlingImpact, 0)} runs saved with the ball`}
            hint="The sum of each selected player's runs above the league rate, and of the runs they saved while bowling. It is a total, so a squad of long careers will out-score a squad of short ones."
          />
        </StatRow>
      </Panel>

      {!pool.prices_available ? (
        <div className="flex items-start gap-2.5 border border-signal-warn/30 bg-signal-warn/5 px-4 py-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-signal-warn" aria-hidden />
          <div className="min-w-0">
            <p className="text-xs font-medium text-signal-warn">
              Budget and price comparison are disabled — no auction price data is loaded
            </p>
            <p className="mt-0.5 text-xs leading-relaxed text-ink-muted">{pool.price_note}</p>
            <p className="mt-1 break-all text-2xs text-ink-faint">
              Expected at <code className="text-accent">{pool.price_file}</code> with columns{" "}
              <code className="text-accent">player_name,season,price_inr,team,source</code>. Once
              that file exists, budget tracking and value-per-rupee comparison switch on here.
            </p>
          </div>
        </div>
      ) : (
        <BudgetBar spend={spend ?? 0} params={params} setParam={setParam} />
      )}

      <Panel>
        <PanelHeader
          title={`Selected squad (${picked.length})`}
          description={
            unresolved
              ? `${unresolved} selected player(s) are outside the current pool filters and are not counted below.`
              : "Remove a player with the minus button. The squad is stored in the URL, so this is a shareable link."
          }
        />
        {picked.length ? (
          <CandidateTable
            rows={picked}
            pool={pool}
            selected={new Set(squadIds)}
            onToggle={toggle}
            photos={photos}
          />
        ) : (
          <EmptyState
            title="No players selected yet"
            detail="Add candidates from the pool below to start building a squad."
            className="py-10"
          />
        )}
      </Panel>
    </div>
  );
}

function BudgetBar({
  spend,
  params,
  setParam,
}: {
  spend: number;
  params: URLSearchParams;
  setParam: (k: string, v: string | null) => void;
}) {
  const budget = Number(params.get("budget") ?? 100) || 100;
  const spentCr = spend / 10_000_000;
  const pctUsed = Math.min((spentCr / budget) * 100, 100);
  const over = spentCr > budget;
  return (
    <Panel>
      <PanelHeader
        title="Budget"
        description="Prices are the operator-supplied historical auction figures, not estimates."
        action={
          <label className="flex items-center gap-1.5 text-2xs text-ink-muted">
            Budget (₹ crore)
            <input
              type="number"
              min={1}
              value={budget}
              onChange={(e) => setParam("budget", e.target.value)}
              className="num h-7 w-20 rounded border border-line-strong bg-surface-raised px-1.5 text-xs text-ink outline-none focus:border-accent/60"
            />
          </label>
        }
      />
      <PanelBody className="space-y-2">
        <div className="h-1.5 w-full overflow-hidden rounded bg-surface-raised">
          <div
            className={cn("h-full transition-all", over ? "bg-signal-down" : "bg-accent")}
            style={{ width: `${pctUsed}%` }}
          />
        </div>
        <p className={cn("num text-xs", over ? "text-signal-down" : "text-ink-muted")}>
          ₹{spentCr.toFixed(2)} cr committed of ₹{budget} cr
          {over ? " — over budget" : ` · ₹${(budget - spentCr).toFixed(2)} cr remaining`}
        </p>
      </PanelBody>
    </Panel>
  );
}

export function CandidateTable({
  rows,
  pool,
  selected,
  onToggle,
  photos = {},
}: {
  rows: AuctionCandidate[];
  pool: AuctionPool;
  selected: Set<string>;
  onToggle: (id: string) => void;
  photos?: Record<string, string>;
}) {
  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            <Th className="w-8" />
            <Th>Player</Th>
            <Th>Role</Th>
            <Th numeric>Mat</Th>
            <Th numeric>Runs</Th>
            <Th numeric>SR</Th>
            <Th numeric>Bat impact</Th>
            <Th numeric>per match</Th>
            <Th numeric>Wkts</Th>
            <Th numeric>Econ</Th>
            <Th numeric>Runs saved</Th>
            <Th numeric>per match</Th>
            {pool.prices_available ? <Th numeric>Price</Th> : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const isIn = selected.has(r.player_id);
            return (
              <Tr key={r.player_id}>
                <Td>
                  <button
                    type="button"
                    onClick={() => onToggle(r.player_id)}
                    aria-label={isIn ? `Remove ${r.name}` : `Add ${r.name}`}
                    className={cn(
                      "flex h-5 w-5 items-center justify-center rounded border transition-colors",
                      isIn
                        ? "border-accent bg-accent/15 text-accent"
                        : "border-line-strong text-ink-faint hover:border-accent/50 hover:text-accent",
                    )}
                  >
                    {isIn ? <Minus className="h-3 w-3" /> : <Plus className="h-3 w-3" />}
                  </button>
                </Td>
                <Td>
                  <span className="flex items-center gap-2.5">
                    <PlayerAvatar
                      name={r.name}
                      team={r.team_name}
                      size="sm"
                      photoSrc={photos[r.player_id]}
                    />
                    <span className="min-w-0">
                      <a
                        href={`/players/${r.player_id}`}
                        className="block truncate font-display text-sm font-semibold text-ink transition-colors hover:text-accent"
                      >
                        {r.name}
                      </a>
                      {r.team_name ? (
                        <span className="block truncate text-2xs text-ink-faint">
                          {r.team_name}
                        </span>
                      ) : null}
                    </span>
                  </span>
                </Td>
                <Td>
                  <Badge tone={r.role === "All-rounder" ? "accent" : "default"}>
                    {r.role ?? "—"}
                  </Badge>
                </Td>
                <Td numeric className="text-ink-muted">{num(r.matches)}</Td>
                <Td numeric>{num(r.runs)}</Td>
                <Td numeric>{dec(r.strike_rate)}</Td>
                <Td numeric className={cn("font-medium", impactTone(r.batting_impact))}>
                  {signedDec(r.batting_impact, 0)}
                </Td>
                <Td numeric className={impactTone(r.batting_impact_per_match)}>
                  {signedDec(r.batting_impact_per_match, 1)}
                </Td>
                <Td numeric>{num(r.wickets)}</Td>
                <Td numeric>{dec(r.economy)}</Td>
                <Td numeric className={cn("font-medium", impactTone(r.bowling_impact))}>
                  {signedDec(r.bowling_impact, 0)}
                </Td>
                <Td numeric className={impactTone(r.bowling_impact_per_match)}>
                  {signedDec(r.bowling_impact_per_match, 1)}
                </Td>
                {pool.prices_available ? (
                  <Td numeric className="text-ink-muted">
                    {r.price_inr == null
                      ? "—"
                      : `₹${(r.price_inr / 10_000_000).toFixed(2)} cr`}
                  </Td>
                ) : null}
              </Tr>
            );
          })}
        </tbody>
      </Table>
    </TableWrap>
  );
}

function impactTone(v: number | null | undefined) {
  if (typeof v !== "number") return "text-ink-faint";
  return v > 0 ? "text-accent" : v < 0 ? "text-signal-down" : "text-ink-muted";
}

function signedDec(v: number | null | undefined, digits: number) {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(digits)}`;
}

export { Check };

/** The pool list, wired to the same `squad` query parameter as the builder. */
export function PoolTable({
  pool,
  photos = {},
}: {
  pool: AuctionPool;
  photos?: Record<string, string>;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const squadIds = (params.get("squad") ?? "").split(",").filter(Boolean);

  const toggle = (id: string) => {
    const next = squadIds.includes(id) ? squadIds.filter((x) => x !== id) : [...squadIds, id];
    const sp = new URLSearchParams(Array.from(params.entries()));
    if (next.length) sp.set("squad", next.join(","));
    else sp.delete("squad");
    router.push(`${pathname}?${sp.toString()}`, { scroll: false });
  };

  if (!pool.rows.length) {
    return (
      <EmptyState
        title="No candidates match these filters"
        detail={`A player needs at least ${pool.qualification.min_balls_faced} balls faced or ${pool.qualification.min_balls_bowled} balls bowled under the current filters to appear in the pool.`}
      />
    );
  }

  return (
    <CandidateTable
      rows={pool.rows}
      pool={pool}
      selected={new Set(squadIds)}
      onToggle={toggle}
      photos={photos}
    />
  );
}
