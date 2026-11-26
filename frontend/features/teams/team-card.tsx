import * as React from "react";
import Link from "next/link";
import { teamIdentity, teamVars } from "@/lib/teams";
import { teamLogo } from "@/lib/photos";
import { TeamCrest } from "@/components/ui/team-crest";
import { dec, num } from "@/lib/format";
import type { TeamSummary } from "@/types";

/**
 * A franchise as a card in its own colours.
 *
 * The win rate is drawn as a bar rather than printed alone, so a column of
 * cards can be compared at a glance without reading any numbers — which is how
 * most people will actually use this page.
 */
export function TeamCard({ team, competition }: { team: TeamSummary; competition?: string }) {
  const identity = teamIdentity(team.name, team.short_name);
  const winPct = team.win_pct ?? 0;
  // Real artwork if the operator supplied it; otherwise a flag for a nation,
  // otherwise the generated badge.
  const logo = teamLogo(team.name, identity.short);

  return (
    <Link
      href={competition ? `/teams/${team.id}?competition=${competition}` : `/teams/${team.id}`}
      style={teamVars(team.name)}
      className="card-interactive group relative block overflow-hidden rounded-xl border border-line bg-surface hover:border-line-strong"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-70 transition-opacity group-hover:opacity-100"
        style={{
          background:
            "radial-gradient(90% 120% at 100% 0%, color-mix(in srgb, var(--team) 22%, transparent) 0%, transparent 60%)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[3px]"
        style={{ background: "linear-gradient(90deg, var(--team), var(--team-2))" }}
      />

      <div className="relative p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <TeamCrest
              team={team.name}
              size={44}
              logoSrc={logo}
              flag={team.flag}
              short={team.short_name}
              className="mt-0.5"
            />
            <div className="min-w-0">
            <div
              className="font-display text-2xl font-bold leading-none"
              style={{ color: "var(--team)" }}
            >
              {identity.short}
            </div>
            <h3 className="mt-1.5 truncate font-display text-sm font-semibold text-ink">
              {team.name}
            </h3>
            {identity.tagline ? (
              <p className="mt-0.5 text-2xs italic text-ink-faint">{identity.tagline}</p>
            ) : null}
            </div>
          </div>
          <span className="num shrink-0 text-right">
            <span className="font-display text-xl font-bold text-ink">{dec(team.win_pct, 1)}</span>
            <span className="block text-2xs text-ink-faint">win %</span>
          </span>
        </div>

        <div className="mt-3.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-raised">
          <div
            className="h-full rounded-full transition-all"
            style={{ width: `${Math.min(winPct, 100)}%`, background: "var(--team)" }}
          />
        </div>

        <div className="num mt-2.5 flex items-center justify-between text-2xs text-ink-faint">
          <span>
            {num(team.won)}W &middot; {num(team.matches - team.won)}L of {num(team.matches)}
          </span>
          <span>
            {team.first_season}–{team.last_season}
          </span>
        </div>

        {team.aliases.length ? (
          <p className="mt-2 truncate text-2xs text-ink-faint">
            Formerly {team.aliases.join(", ")}
          </p>
        ) : null}
      </div>
    </Link>
  );
}
