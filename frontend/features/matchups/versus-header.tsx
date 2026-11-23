import * as React from "react";
import Link from "next/link";
import { photoFor } from "@/lib/photos";
import { teamIdentity } from "@/lib/teams";
import { initials, num, dec, pct } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Matchup, PlayerProfile } from "@/types";

/**
 * The head-to-head, staged as a contest.
 *
 * Two portraits facing each other across the figures that matter, each tinted
 * with their own franchise. The reliability of the sample still leads the page
 * above this — a good-looking contest card is exactly the kind of thing that
 * can make twelve deliveries feel like evidence, so the warning stays first.
 */
function Side({
  profile,
  align,
  role,
}: {
  profile: PlayerProfile;
  align: "left" | "right";
  role: string;
}) {
  const team = profile.player.teams[0]?.team_name ?? null;
  const identity = teamIdentity(team);
  const photo = photoFor(profile.player.id);

  return (
    <div
      className={cn(
        "flex min-w-0 flex-1 items-center gap-3.5",
        align === "right" && "flex-row-reverse text-right",
      )}
    >
      <div className="relative shrink-0">
        <div
          aria-hidden
          className="absolute -inset-1 rounded-full blur-lg"
          style={{ background: `color-mix(in srgb, ${identity.primary} 45%, transparent)` }}
        />
        <div
          className="relative h-16 w-16 overflow-hidden rounded-full"
          style={{
            background: `color-mix(in srgb, ${identity.primary} 18%, #121923)`,
            boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${identity.primary} 50%, transparent)`,
          }}
        >
          {photo ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={photo.src}
              alt={profile.player.name}
              className="h-full w-full object-cover object-top"
            />
          ) : (
            <span
              className="flex h-full w-full items-center justify-center font-display text-lg font-bold"
              style={{ color: identity.primary }}
            >
              {initials(profile.player.name)}
            </span>
          )}
        </div>
      </div>
      <div className="min-w-0">
        <div className="text-2xs" style={{ color: identity.primary }}>
          {role}
          {team ? ` · ${identity.short}` : ""}
        </div>
        <Link
          href={`/players/${profile.player.id}`}
          className="block truncate font-display text-lg font-bold leading-tight text-ink hover:text-accent"
        >
          {profile.player.name}
        </Link>
        <div className="num text-2xs text-ink-faint">
          {num(profile.player.matches)} matches
        </div>
      </div>
    </div>
  );
}

export function VersusHeader({
  batter,
  bowler,
  matchup,
}: {
  batter: PlayerProfile;
  bowler: PlayerProfile;
  matchup: Matchup;
}) {
  const s = matchup.summary;
  const batterColor = teamIdentity(batter.player.teams[0]?.team_name).primary;
  const bowlerColor = teamIdentity(bowler.player.teams[0]?.team_name).primary;

  return (
    <section className="relative overflow-hidden rounded-xl border border-line bg-surface">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background: `radial-gradient(70% 140% at 0% 50%, color-mix(in srgb, ${batterColor} 20%, transparent) 0%, transparent 52%), radial-gradient(70% 140% at 100% 50%, color-mix(in srgb, ${bowlerColor} 20%, transparent) 0%, transparent 52%)`,
        }}
      />
      <div className="relative flex flex-wrap items-center gap-4 p-5 sm:flex-nowrap">
        <Side profile={batter} align="left" role="Batter" />
        <div className="mx-auto shrink-0 px-2 text-center sm:mx-0">
          <span className="font-display text-xl font-bold text-ink-faint">vs</span>
        </div>
        <Side profile={bowler} align="right" role="Bowler" />
      </div>

      <dl className="relative grid grid-cols-2 border-t border-line sm:grid-cols-5">
        {[
          { label: "Balls", value: num(s.balls) },
          { label: "Runs", value: num(s.runs), tint: batterColor },
          { label: "Dismissals", value: num(s.dismissals), tint: bowlerColor },
          { label: "Strike rate", value: dec(s.strike_rate) },
          { label: "Dot %", value: pct(s.dot_pct) },
        ].map((f, i) => (
          <div key={f.label} className={cn("px-4 py-3", i > 0 && "sm:border-l sm:border-line")}>
            <dt className="text-2xs text-ink-faint">{f.label}</dt>
            <dd
              className="num mt-1 font-display text-xl font-bold leading-none"
              style={{ color: f.tint ?? undefined }}
            >
              {f.value}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
