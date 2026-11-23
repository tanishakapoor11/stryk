import Link from "next/link";
import { BallStripLegend } from "@/components/ui/ball-strip";
import { InningsReplay } from "@/components/ui/innings-replay";
import { PlayerAvatar } from "@/components/ui/player-identity";
import { teamColor } from "@/lib/teams";
import { dec, num, shortDate } from "@/lib/format";
import type { FeaturedInnings } from "@/types";

/**
 * One real innings, ball by ball.
 *
 * Every number elsewhere in the product is an aggregate of sequences like this
 * one, so the front page shows the source material before it claims anything
 * about it — and the notation teaches itself in the process.
 */
export function FeaturedInningsCard({ innings }: { innings: FeaturedInnings }) {
  return (
    <figure className="relative overflow-hidden rounded-xl border border-line bg-surface p-4 lg:p-5">
      <figcaption className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <span className="flex items-center gap-2.5">
          <PlayerAvatar
            name={innings.player_name}
            team={innings.team_name}
            size="sm"
          />
          <span>
            <Link
              href={`/players/${innings.player_id}`}
              className="font-display text-sm font-semibold text-ink hover:text-accent"
            >
              {innings.player_name}
            </Link>
            <span className="block text-2xs text-ink-faint">
              v {innings.opposition}, {shortDate(innings.date)}
            </span>
          </span>
        </span>
        <span className="num text-sm text-ink">
          <span className="font-semibold text-accent">
            {num(innings.runs)}
            {innings.out ? "" : "*"}
          </span>
          <span className="text-ink-muted"> off {num(innings.balls)}</span>
          <span className="block text-right text-2xs text-ink-faint">
            {dec(innings.strike_rate)} SR
          </span>
        </span>
      </figcaption>

      <InningsReplay
        sequence={innings.sequence}
        accent={teamColor(innings.team_name)}
        className="mt-4"
      />

      <p className="mt-3 text-2xs leading-relaxed text-ink-faint">
        The highest individual score in the data, every ball of it. Press play to watch it
        build. This notation runs through the whole site.
      </p>
      <BallStripLegend className="mt-2.5" />
    </figure>
  );
}
