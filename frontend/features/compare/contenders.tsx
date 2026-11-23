import * as React from "react";
import Link from "next/link";
import { photoFor } from "@/lib/photos";
import { teamIdentity } from "@/lib/teams";
import { dec, initials, num } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { PlayerProfile } from "@/types";

/**
 * The players being compared, staged like a line-up.
 *
 * Same idea as the match-up header: portraits, franchise colours and the
 * headline each player is actually known for. The figures shown depend on what
 * the player does, so a bowler is introduced by wickets and economy rather
 * than by an empty batting average.
 *
 * Nothing here ranks anybody — the tables below do the comparing, and they tint
 * one leading value per row rather than declaring a winner.
 */
export function Contenders({ players }: { players: PlayerProfile[] }) {
  return (
    <div className="relative">
      <div
        className={cn(
          "grid min-w-0 gap-3 [&>*]:min-w-0",
          players.length === 2 ? "sm:grid-cols-2" : "sm:grid-cols-2 lg:grid-cols-4",
        )}
      >
        {players.map((p) => (
          <Contender key={p.player.id} profile={p} />
        ))}
      </div>
      {/* Only meaningful between two; with four it would be noise. Sits on the
          grid rather than inside a card, which clips its own overflow. */}
      {players.length === 2 ? (
        <span
          aria-hidden
          className="absolute left-1/2 top-[88px] hidden -translate-x-1/2 sm:block"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-full border border-line-strong bg-canvas font-display text-xs font-bold text-ink-muted">
            vs
          </span>
        </span>
      ) : null}
    </div>
  );
}

function Contender({ profile }: { profile: PlayerProfile }) {
  const p = profile.player;
  const team = p.teams[0]?.team_name ?? null;
  const identity = teamIdentity(team);
  const photo = photoFor(p.id);
  const bat = profile.batting;
  const bowl = profile.bowling;

  // Introduce the player by whichever discipline they actually have a record in.
  const leadsWithBat = (bat?.balls ?? 0) >= (bowl?.balls ?? 0);
  const figures = leadsWithBat && bat
    ? [
        { label: "Runs", value: num(bat.runs) },
        { label: "Average", value: dec(bat.average) },
        { label: "Strike rate", value: dec(bat.strike_rate) },
      ]
    : bowl
      ? [
          { label: "Wickets", value: num(bowl.wickets) },
          { label: "Economy", value: dec(bowl.economy) },
          { label: "Average", value: dec(bowl.average) },
        ]
      : [];

  return (
    <div className="relative overflow-hidden rounded-xl border border-line bg-surface">
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background: `radial-gradient(85% 110% at 50% 0%, color-mix(in srgb, ${identity.primary} 22%, transparent) 0%, transparent 62%)`,
        }}
      />
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[3px]"
        style={{ background: identity.primary }}
      />
      <div className="relative flex flex-col items-center gap-2.5 px-4 pb-4 pt-5 text-center">
        <div className="relative">
          <span
            aria-hidden
            className="absolute -inset-1 rounded-full blur-lg"
            style={{ background: `color-mix(in srgb, ${identity.primary} 45%, transparent)` }}
          />
          <span
            className="relative block h-20 w-20 overflow-hidden rounded-full"
            style={{
              background: `color-mix(in srgb, ${identity.primary} 18%, #121923)`,
              boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${identity.primary} 50%, transparent)`,
            }}
          >
            {photo ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={photo.src}
                alt={p.name}
                className="h-full w-full object-cover object-top"
              />
            ) : (
              <span
                className="flex h-full w-full items-center justify-center font-display text-xl font-bold"
                style={{ color: identity.primary }}
              >
                {initials(p.name)}
              </span>
            )}
          </span>
        </div>

        <div className="min-w-0">
          <Link
            href={`/players/${p.id}`}
            className="block truncate font-display text-base font-semibold text-ink hover:text-accent"
          >
            {p.name}
          </Link>
          <p className="mt-0.5 text-2xs" style={{ color: identity.primary }}>
            {p.role ?? "Unclassified"}
            {team ? ` · ${identity.short}` : ""}
          </p>
          <p className="num mt-0.5 text-2xs text-ink-faint">{num(p.matches)} matches</p>
        </div>
      </div>

      {figures.length ? (
        <dl className="relative grid grid-cols-3 border-t border-line">
          {figures.map((f, i) => (
            <div key={f.label} className={cn("px-2 py-2.5 text-center", i > 0 && "border-l border-line")}>
              <dt className="text-[0.5625rem] text-ink-faint">{f.label}</dt>
              <dd className="num mt-0.5 font-display text-base font-bold leading-none text-ink">
                {f.value}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}
