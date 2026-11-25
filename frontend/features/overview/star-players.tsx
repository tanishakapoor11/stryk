import * as React from "react";
import Link from "next/link";
import { teamIdentity, teamVars } from "@/lib/teams";
import { photoFor } from "@/lib/photos";
import { dec, initials, num } from "@/lib/format";
import type { PlayerRow } from "@/types";

/**
 * A row of the league's biggest names, each in their franchise's colours.
 *
 * This is the shortcut most visitors actually want: they arrive wanting a
 * particular player, and recognising a face beats typing a name. Which players
 * appear is decided by the data (runs and wickets), not a hand-picked list.
 */
export function StarPlayers({
  batters,
  bowlers,
  seasonRange,
  complete = false,
}: {
  batters: PlayerRow[];
  bowlers: PlayerRow[];
  /** The seasons STRYK holds ball-by-ball data for, named in the caption. */
  seasonRange?: number[];
  /** True when that is every season the competition has played. */
  complete?: boolean;
}) {
  // A cumulative list is only a real all-time order where the data covers the
  // whole competition, which is why the caller withholds this row otherwise.
  // Where it does - every IPL season, every men's T20I - the caption says so,
  // because "2008-2026" alone reads like a slice of something longer.
  const span = seasonRange?.length === 2 ? `${seasonRange[0]}\u2013${seasonRange[1]}` : null;
  const runs = complete && span ? `Every season, ${span}` : span ? `Runs in ${span}` : "Runs";
  const wickets = complete && span
    ? `Every season, ${span} \u00b7 credited to the bowler`
    : "Wickets credited to the bowler";
  return (
    <div className="space-y-5">
      <StarRow
        title="Most runs"
        caption={runs}
        players={batters}
        stat={(p) => ({ value: num(p.runs), label: "runs", second: `${dec(p.strike_rate)} SR` })}
      />
      <StarRow
        title="Most wickets"
        caption={wickets}
        players={bowlers}
        stat={(p) => ({ value: num(p.wickets), label: "wickets", second: `${dec(p.economy)} econ` })}
      />
    </div>
  );
}

function StarRow({
  title,
  caption,
  players,
  stat,
}: {
  title: string;
  caption: string;
  players: PlayerRow[];
  stat: (p: PlayerRow) => { value: string; label: string; second: string };
}) {
  if (!players.length) return null;
  return (
    <div>
      <div className="mb-2.5 flex items-baseline justify-between gap-3">
        <h3 className="font-display text-sm font-semibold tracking-tight text-ink">{title}</h3>
        <span className="text-2xs text-ink-faint">{caption}</span>
      </div>
      <div className="scrollbar-thin -mx-1 flex gap-2.5 overflow-x-auto px-1 pb-1">
        {players.map((p) => {
          const identity = teamIdentity(p.team_name);
          const photo = photoFor(p.player_id);
          const s = stat(p);
          return (
            <Link
              key={p.player_id}
              href={`/players/${p.player_id}`}
              style={teamVars(p.team_name)}
              className="card-interactive group relative w-[168px] shrink-0 overflow-hidden rounded-lg border border-line bg-surface p-3 hover:border-line-strong"
            >
              <span
                aria-hidden
                className="pointer-events-none absolute inset-0 opacity-80 transition-opacity group-hover:opacity-100"
                style={{
                  background:
                    "radial-gradient(90% 110% at 100% 0%, color-mix(in srgb, var(--team) 20%, transparent) 0%, transparent 62%)",
                }}
              />
              <span className="relative block">
                <span className="flex items-center justify-between gap-2">
                  <span
                    className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-full font-display text-xs font-bold"
                    style={{
                      background: "color-mix(in srgb, var(--team) 18%, transparent)",
                      color: "var(--team)",
                      boxShadow: "inset 0 0 0 1px color-mix(in srgb, var(--team) 40%, transparent)",
                    }}
                  >
                    {photo ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={photo.src}
                        alt=""
                        width={44}
                        height={44}
                        className="h-full w-full object-cover object-top"
                      />
                    ) : (
                      initials(p.name)
                    )}
                  </span>
                  {p.team_name ? (
                    <span
                      className="font-display text-2xs font-semibold"
                      style={{ color: "var(--team)" }}
                    >
                      {identity.short}
                    </span>
                  ) : null}
                </span>
                <span className="mt-2.5 block truncate font-display text-sm font-semibold text-ink">
                  {p.name}
                </span>
                <span className="num mt-1.5 block font-display text-xl font-bold leading-none text-ink">
                  {s.value}
                  <span className="ml-1 text-2xs font-normal text-ink-faint">{s.label}</span>
                </span>
                <span className="num mt-1 block text-2xs text-ink-faint">{s.second}</span>
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
