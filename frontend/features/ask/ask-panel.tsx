"use client";

import * as React from "react";
import Link from "next/link";
import { AlertTriangle, CornerDownLeft, Loader2, Sparkles } from "lucide-react";
import { PlayerAvatar } from "@/components/ui/player-identity";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { dec, num, EMPTY } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AskAnswer, PlayerRow } from "@/types";

/**
 * Ask a question in English and get the leaderboard it describes.
 *
 * The question is translated into the same filters the rest of STRYK uses -
 * no statistic is computed here, and none is invented. Two things are shown
 * with every answer and must never be dropped:
 *
 * - `interpretation`, the query that actually ran, so the reader can check it;
 * - `unsupported`, every clause that no filter could express.
 *
 * Without the second, a question about left-arm spin silently returns runs
 * against everyone, which looks like an answer and is not one.
 */

/** Columns worth showing, chosen by what the question sorted on. */
const BOWLING_SORTS = new Set(["wickets", "economy", "bowling_average", "overs"]);

type Column = { key: keyof PlayerRow; label: string; format: (r: PlayerRow) => string };

const BATTING: Column[] = [
  { key: "innings", label: "Inns", format: (r) => num(r.innings) },
  { key: "runs", label: "Runs", format: (r) => num(r.runs) },
  { key: "batting_average", label: "Avg", format: (r) => dec(r.batting_average) },
  { key: "strike_rate", label: "SR", format: (r) => dec(r.strike_rate) },
  { key: "highest_score", label: "HS", format: (r) => num(r.highest_score) },
];

const BOWLING: Column[] = [
  { key: "overs", label: "Overs", format: (r) => r.overs ?? EMPTY },
  { key: "wickets", label: "Wkts", format: (r) => num(r.wickets) },
  { key: "economy", label: "Econ", format: (r) => dec(r.economy) },
  { key: "bowling_average", label: "Avg", format: (r) => dec(r.bowling_average) },
];

export function AskPanel({ examples }: { examples: string[] }) {
  const [question, setQuestion] = React.useState("");
  const [answer, setAnswer] = React.useState<AskAnswer | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);

  async function ask(q: string) {
    const trimmed = q.trim();
    if (trimmed.length < 3 || loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ q: trimmed }),
      });
      const body = await res.json();
      if (!res.ok) {
        setError(String(body?.detail ?? "That question could not be answered."));
        setAnswer(null);
      } else {
        setAnswer(body as AskAnswer);
      }
    } catch {
      setError("Could not reach STRYK. Is the backend running?");
      setAnswer(null);
    } finally {
      setLoading(false);
    }
  }

  const columns = answer && BOWLING_SORTS.has(answer.sort) ? BOWLING : BATTING;

  return (
    <div className="space-y-6">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void ask(question);
        }}
      >
        <label htmlFor="ask" className="sr-only">
          Ask a question about the ball-by-ball record
        </label>
        <div className="flex items-center gap-3 rounded-xl border border-line-strong bg-surface-raised px-4 py-3.5 shadow-lift transition-colors field-shell focus-within:border-accent/60">
          {loading ? (
            <Loader2 className="h-5 w-5 shrink-0 animate-spin text-accent" aria-hidden />
          ) : (
            <Sparkles className="h-5 w-5 shrink-0 text-ink-faint" aria-hidden />
          )}
          <input
            id="ask"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Most runs in a 180+ run chase in the IPL"
            autoComplete="off"
            className="w-full bg-transparent text-base text-ink outline-none placeholder:text-ink-faint"
          />
          <button
            type="submit"
            disabled={loading || question.trim().length < 3}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-line-strong px-2.5 py-1 text-xs text-ink-muted transition-colors hover:border-accent/50 hover:text-ink disabled:opacity-40"
          >
            Ask <CornerDownLeft className="h-3 w-3" aria-hidden />
          </button>
        </div>
      </form>

      {/* Unlike the name search, nothing happens until Enter: each question is
          a model call, so firing per keystroke would bill five calls for one
          word and answer none of them. */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-ink-faint">Try</span>
        {examples.map((e) => (
          <button
            key={e}
            type="button"
            onClick={() => {
              setQuestion(e);
              void ask(e);
            }}
            className="rounded-full border border-line-strong bg-surface px-2.5 py-1 text-xs text-ink-muted transition-colors hover:border-accent/50 hover:text-ink"
          >
            {e}
          </button>
        ))}
      </div>

      {error ? <ErrorState title="That question could not be answered" detail={error} /> : null}

      {answer ? (
        <div className="space-y-4">
          <div className="border-l-2 border-accent/50 pl-3">
            <p className="text-sm leading-relaxed text-ink-muted">{answer.interpretation}</p>
            {answer.scope?.length ? (
              <p className="mt-1 text-2xs text-ink-faint">
                Computed from{" "}
                <span className="text-ink-muted">{answer.scope.join(", ")}</span> deliveries.
              </p>
            ) : null}
          </div>

          {answer.unsupported.length > 0 ? (
            <div className="flex gap-2.5 border border-signal-down/30 bg-signal-down/5 px-3.5 py-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-signal-down" aria-hidden />
              <div className="min-w-0 text-xs leading-relaxed text-ink-muted">
                <p className="text-ink">Part of your question was not applied.</p>
                <ul className="mt-1 list-inside list-disc">
                  {answer.unsupported.map((u) => (
                    <li key={u}>{u}</li>
                  ))}
                </ul>
                <p className="mt-1.5">
                  The table below answers the rest of the question, not all of it.
                </p>
              </div>
            </div>
          ) : null}

          {answer.rows.length === 0 ? (
            <EmptyState
              title="No player matches that"
              detail="The filters were understood, but nothing in the record satisfies them."
            />
          ) : (
            <div className="overflow-x-auto border border-line">
              <table className="w-full min-w-[34rem] text-sm">
                <thead>
                  <tr className="border-b border-line text-2xs uppercase tracking-wide text-ink-faint">
                    <th className="px-3 py-2 text-left font-medium">#</th>
                    <th className="px-3 py-2 text-left font-medium">Player</th>
                    {columns.map((c) => (
                      <th
                        key={String(c.key)}
                        className={cn(
                          "px-3 py-2 text-right font-medium",
                          c.key === answer.sort ? "text-accent" : "",
                        )}
                      >
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {answer.rows.map((row, i) => (
                    <tr key={row.player_id} className="border-b border-line/60 last:border-0">
                      <td className="num px-3 py-2 text-2xs text-ink-faint">{i + 1}</td>
                      <td className="px-3 py-2">
                        <Link
                          href={`/players/${row.player_id}`}
                          className="flex items-center gap-2 text-ink hover:text-accent"
                        >
                          <PlayerAvatar name={row.name} team={row.team_name} size="sm" />
                          <span className="truncate">{row.name}</span>
                        </Link>
                      </td>
                      {columns.map((c) => (
                        <td
                          key={String(c.key)}
                          className={cn(
                            "num px-3 py-2 text-right",
                            c.key === answer.sort ? "text-ink" : "text-ink-muted",
                          )}
                        >
                          {c.format(row)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <p className="text-2xs text-ink-faint">
            {num(answer.total)} players matched; showing {answer.rows.length}. Sorted by{" "}
            {answer.sort}, {answer.order === "asc" ? "lowest" : "highest"} first
            {answer.minimums && Object.values(answer.minimums).some(Boolean)
              ? `, with a qualification floor of ${Object.entries(answer.minimums)
                  .filter(([, v]) => v)
                  .map(([k, v]) => `${num(v)} ${k.replace("min_", "")}`)
                  .join(" and ")}`
              : ""}
            .
          </p>
        </div>
      ) : null}
    </div>
  );
}
