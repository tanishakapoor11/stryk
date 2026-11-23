import * as React from "react";
import Link from "next/link";
import { GitCompareArrows, Swords } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Reads } from "@/components/ui/reads";
import { teamIdentity, teamVars } from "@/lib/teams";
import { photoFor } from "@/lib/photos";
import { dec, figures, initials, num } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { PlayerProfile } from "@/types";

/**
 * The player card.
 *
 * A profile should feel like it is about *this* player, so the card is themed
 * with their franchise's colour: the monogram, the glow behind it and the
 * headline figures all take `--team`. No crest or logo is used — those are
 * trademarks — so the identity is carried by colour, the monogram and the
 * franchise's own short name.
 *
 * The headline figures are chosen by what the player actually does: a bowler
 * leads with wickets and economy, a batter with runs and strike rate, an
 * all-rounder gets both.
 */
export function PlayerCard({ profile }: { profile: PlayerProfile }) {
  const p = profile.player;
  const team = p.teams[0]?.team_name ?? null;
  const identity = teamIdentity(team);
  const photo = photoFor(p.id);
  const bat = profile.batting;
  const bowl = profile.bowling;
  const hasBat = (bat?.balls ?? 0) > 0;
  const hasBowl = (bowl?.balls ?? 0) > 0;
  /** Headline figures need a real sample behind them; the full career line
   *  below the card still reports every ball either way. */
  const HEADLINE_BALLS = 120;
  const leadsWithBat = (bat?.balls ?? 0) >= HEADLINE_BALLS;
  const leadsWithBowl = (bowl?.balls ?? 0) >= HEADLINE_BALLS;
  // A player short of the threshold in both still gets whichever they did more of.
  const showBat = leadsWithBat || (!leadsWithBowl && hasBat);
  const showBowl = leadsWithBowl || (!leadsWithBat && !hasBat && hasBowl);

  const figuresList: Array<{ label: string; value: string; sub?: string }> = [];
  if (showBat && bat) {
    figuresList.push(
      { label: "Runs", value: num(bat.runs), sub: `${num(bat.innings)} innings` },
      { label: "Average", value: dec(bat.average), sub: `${num(bat.not_outs)} not out` },
      { label: "Strike rate", value: dec(bat.strike_rate), sub: `${num(bat.balls)} balls` },
      {
        label: "Best",
        value: `${num(bat.highest_score)}${bat.highest_not_out ? "*" : ""}`,
        sub: `${num(bat.fifties)}×50 · ${num(bat.hundreds)}×100`,
      },
    );
  }
  if (showBowl && bowl) {
    figuresList.push(
      { label: "Wickets", value: num(bowl.wickets), sub: `${bowl.overs} overs` },
      { label: "Economy", value: dec(bowl.economy), sub: "per over" },
      { label: "Bowl avg", value: dec(bowl.average), sub: "runs per wicket" },
      { label: "Figures", value: figures(bowl.best_wickets, bowl.best_runs), sub: "best" },
    );
  }

  return (
    <section
      style={teamVars(team)}
      className="relative overflow-hidden rounded-xl border border-line bg-surface"
    >
      {/* Franchise wash: strong at the monogram, gone by the middle of the card. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(120% 140% at 0% 0%, color-mix(in srgb, var(--team) 26%, transparent) 0%, transparent 58%)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[3px]"
        style={{ background: "linear-gradient(90deg, var(--team), var(--team-2), transparent)" }}
      />

      <div className="relative flex flex-wrap items-start gap-x-6 gap-y-5 p-5 lg:p-6">
        {/* Portrait, or a monogram when no freely licensed photo exists. */}
        <div className="relative shrink-0">
          <div
            aria-hidden
            className="absolute -inset-1 rounded-2xl blur-xl"
            style={{ background: "color-mix(in srgb, var(--team) 45%, transparent)" }}
          />
          <div
            className="relative h-28 w-28 overflow-hidden rounded-2xl"
            style={{
              background: "color-mix(in srgb, var(--team) 16%, #121923)",
              boxShadow: "inset 0 0 0 1px color-mix(in srgb, var(--team) 50%, transparent)",
            }}
          >
            {photo ? (
              <>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={photo.src}
                  alt={p.name}
                  width={112}
                  height={112}
                  className="h-full w-full object-cover object-top"
                />
                <span
                  aria-hidden
                  className="pointer-events-none absolute inset-0"
                  style={{
                    background:
                      "linear-gradient(to top, color-mix(in srgb, var(--team) 55%, transparent) 0%, transparent 55%)",
                  }}
                />
              </>
            ) : (
              <span className="flex h-full w-full items-center justify-center">
                <span
                  className="font-display text-3xl font-bold leading-none"
                  style={{ color: "var(--team)" }}
                >
                  {initials(p.name)}
                </span>
              </span>
            )}
          </div>
        </div>

        {/* Name and identity */}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {team ? (
              <span
                className="rounded-full px-2 py-0.5 font-display text-2xs font-semibold"
                style={{
                  background: "color-mix(in srgb, var(--team) 18%, transparent)",
                  color: "var(--team)",
                }}
              >
                {identity.short}
              </span>
            ) : null}
            <span className="rounded-full border border-line-strong px-2 py-0.5 text-2xs text-ink-muted">
              {p.role ?? "Unclassified"}
            </span>
          </div>

          <h1 className="mt-2 font-display text-3xl font-bold leading-[1.05] tracking-tight text-ink lg:text-4xl">
            {p.name}
          </h1>
          <p className="mt-1.5 text-xs text-ink-faint">
            {p.scorecard_name && p.scorecard_name !== p.name
              ? `Listed on scorecards as ${p.scorecard_name} · `
              : ""}
            {num(p.matches)} matches across {p.seasons.length} seasons
          </p>

          {p.teams.length ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {p.teams.slice(0, 4).map((t) => {
                const tid = teamIdentity(t.team_name);
                return (
                  <Link
                    key={t.team_id}
                    href={`/teams/${t.team_id}`}
                    className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-2xs transition-opacity hover:opacity-80"
                    style={{
                      background: `color-mix(in srgb, ${tid.primary} 14%, transparent)`,
                      color: tid.primary,
                    }}
                  >
                    <span
                      className="h-1.5 w-1.5 rounded-full"
                      style={{ background: tid.primary }}
                      aria-hidden
                    />
                    {tid.short}
                    <span className="num text-ink-faint">{t.matches}</span>
                  </Link>
                );
              })}
            </div>
          ) : null}

          {profile.highlights?.length ? (
            <Reads reads={profile.highlights} className="mt-4" />
          ) : null}
        </div>

        {/* Actions. On a narrow screen these take their own row rather than
            competing with the name for the little width there is. */}
        <div className="order-last flex w-full shrink-0 gap-2 sm:order-none sm:w-auto">
          <Button asChild variant="outline">
            <Link href={`/compare?player=${p.id}`}>
              <GitCompareArrows className="h-3.5 w-3.5" aria-hidden /> Compare
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href={`/matchups?${hasBat ? "batter" : "bowler"}=${p.id}`}>
              <Swords className="h-3.5 w-3.5" aria-hidden /> Match-ups
            </Link>
          </Button>
        </div>
      </div>

      {/* Headline figures, broadcast style */}
      {figuresList.length ? (
        <div
          className={cn(
            "relative grid border-t border-line",
            figuresList.length > 4 ? "grid-cols-2 sm:grid-cols-4" : "grid-cols-2 sm:grid-cols-4",
          )}
        >
          {figuresList.map((f, i) => (
            <div
              key={f.label}
              className={cn(
                "px-4 py-3.5",
                i > 0 && "border-l border-line",
                i === 4 && "sm:border-l-0",
                i >= 4 && "border-t border-line sm:border-t",
              )}
            >
              <div className="text-2xs text-ink-faint">{f.label}</div>
              <div className="num mt-1 font-display text-2xl font-bold leading-none text-ink">
                {f.value}
              </div>
              {f.sub ? <div className="mt-1 text-[0.5625rem] text-ink-faint">{f.sub}</div> : null}
            </div>
          ))}
        </div>
      ) : null}

      {photo ? (
        <p className="relative border-t border-line px-5 py-2 text-[0.5625rem] leading-relaxed text-ink-faint">
          Photo:{" "}
          <a
            href={photo.credit.source}
            target="_blank"
            rel="noreferrer"
            className="underline-offset-2 hover:text-ink-muted hover:underline"
          >
            Wikimedia Commons
          </a>{" "}
          — {photo.credit.author}, {photo.credit.licence}
        </p>
      ) : null}
    </section>
  );
}
