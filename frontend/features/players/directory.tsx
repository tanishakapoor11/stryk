import * as React from "react";
import Link from "next/link";
import { ArrowDown, ArrowUp } from "lucide-react";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { PlayerName } from "@/components/ui/player-identity";
import { photoFor } from "@/lib/photos";
import { EmptyState } from "@/components/ui/states";
import { dec, num, pct } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { PlayerDirectory } from "@/types";
import type { RawParams } from "@/lib/search-params";

const COLUMNS: Array<{ key: string; label: string; sortable?: boolean; hint?: string }> = [
  { key: "name", label: "Player", sortable: true },
  { key: "role", label: "Role" },
  { key: "matches", label: "Mat", sortable: true },
  { key: "runs", label: "Runs", sortable: true },
  { key: "average", label: "Bat avg", sortable: true },
  { key: "strike_rate", label: "SR", sortable: true },
  { key: "highest_score", label: "HS" },
  { key: "fifties", label: "50/100" },
  { key: "boundary_pct", label: "Bdry%" },
  { key: "wickets", label: "Wkts", sortable: true },
  { key: "overs", label: "Overs" },
  { key: "economy", label: "Econ", sortable: true },
  { key: "bowling_average", label: "Bowl avg", sortable: true },
];

/** Build a URL that preserves every filter and changes only one key. */
function withParam(params: RawParams, changes: Record<string, string | number | null>) {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined) continue;
    (Array.isArray(v) ? v : [v]).forEach((x) => sp.append(k, x));
  }
  for (const [k, v] of Object.entries(changes)) {
    sp.delete(k);
    if (v !== null) sp.set(k, String(v));
  }
  const q = sp.toString();
  return q ? `?${q}` : "";
}

function SortHeader({
  col,
  params,
  active,
  order,
}: {
  col: { key: string; label: string; sortable?: boolean };
  params: RawParams;
  active: boolean;
  order: string;
}) {
  const numeric = col.key !== "name" && col.key !== "role";
  if (!col.sortable) return <Th numeric={numeric}>{col.label}</Th>;
  // Clicking the active column flips direction; a new column starts descending
  // except for name, where ascending is the useful default.
  const nextOrder = active ? (order === "desc" ? "asc" : "desc") : col.key === "name" ? "asc" : "desc";
  return (
    <Th numeric={numeric}>
      <Link
        href={withParam(params, { sort: col.key, order: nextOrder, offset: null })}
        scroll={false}
        className={cn(
          "inline-flex items-center gap-0.5 transition-colors hover:text-ink",
          active && "text-accent",
        )}
      >
        {col.label}
        {active ? (
          order === "desc" ? (
            <ArrowDown className="h-3 w-3" aria-hidden />
          ) : (
            <ArrowUp className="h-3 w-3" aria-hidden />
          )
        ) : null}
      </Link>
    </Th>
  );
}

export function DirectoryTable({
  data,
  params,
}: {
  data: PlayerDirectory;
  params: RawParams;
}) {
  if (!data.rows.length) {
    return (
      <EmptyState
        title="No players match these filters"
        detail="Try clearing the season or role filter, or searching for a different name."
      />
    );
  }
  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            {COLUMNS.map((c) => (
              <SortHeader
                key={c.key}
                col={c}
                params={params}
                active={data.sort === c.key}
                order={data.order}
              />
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r) => (
            <Tr key={r.player_id}>
              <Td>
                <PlayerName
                  id={r.player_id}
                  name={r.name}
                  photoSrc={photoFor(r.player_id)?.src}
                  scorecardName={r.scorecard_name}
                  team={r.team_name}
                  sub={
                    r.scorecard_name && r.scorecard_name !== r.name
                      ? `${r.scorecard_name}${r.team_name ? ` · ${r.team_name}` : ""}`
                      : r.team_name
                  }
                />
              </Td>
              <Td>
                <Badge tone={r.role === "All-rounder" ? "accent" : "default"}>{r.role ?? "—"}</Badge>
              </Td>
              <Td numeric className="text-ink-muted">{num(r.matches)}</Td>
              <Td numeric className="font-medium">{num(r.runs)}</Td>
              <Td numeric>{dec(r.batting_average)}</Td>
              <Td numeric>{dec(r.strike_rate)}</Td>
              <Td numeric className="text-ink-muted">{num(r.highest_score)}</Td>
              <Td numeric className="text-ink-muted">
                {num(r.fifties)}/{num(r.hundreds)}
              </Td>
              <Td numeric className="text-ink-muted">{pct(r.boundary_pct)}</Td>
              <Td numeric className="font-medium">{num(r.wickets)}</Td>
              <Td numeric className="text-ink-muted">{r.overs ?? "—"}</Td>
              <Td numeric>{dec(r.economy)}</Td>
              <Td numeric>{dec(r.bowling_average)}</Td>
            </Tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  );
}

export function Pager({ data, params }: { data: PlayerDirectory; params: RawParams }) {
  const from = data.offset + 1;
  const to = Math.min(data.offset + data.limit, data.total);
  const prev = Math.max(0, data.offset - data.limit);
  const next = data.offset + data.limit;
  return (
    <div className="flex items-center justify-between border-t border-line px-4 py-2.5 text-2xs text-ink-muted">
      <span className="num">
        {data.total ? `${from}–${to}` : "0"} of {num(data.total)} players
      </span>
      <div className="flex items-center gap-2">
        <PagerLink href={withParam(params, { offset: prev })} disabled={data.offset === 0}>
          Previous
        </PagerLink>
        <PagerLink href={withParam(params, { offset: next })} disabled={next >= data.total}>
          Next
        </PagerLink>
      </div>
    </div>
  );
}

function PagerLink({
  href,
  disabled,
  children,
}: {
  href: string;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  if (disabled) return <span className="cursor-default text-ink-faint opacity-50">{children}</span>;
  return (
    <Link href={href} scroll={false} className="transition-colors hover:text-accent">
      {children}
    </Link>
  );
}

export { withParam };
