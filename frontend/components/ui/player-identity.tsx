import * as React from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { teamColor } from "@/lib/teams";
import { initials } from "@/lib/format";

/**
 * A player's face in the interface.
 *
 * Cricsheet stores a scorecard name ("SS Iyer"); the readable name sits first
 * and the scorecard form follows in smaller type, so a reader learns the
 * mapping instead of being confused by it. The disc is tinted with the
 * player's franchise colour, which most fans read faster than any label.
 */
export function PlayerAvatar({
  name,
  team,
  size = "md",
  className,
  photoSrc,
}: {
  name: string;
  team?: string | null;
  size?: "sm" | "md" | "lg";
  className?: string;
  /** Resolved by a server component; falls back to initials when absent. */
  photoSrc?: string | null;
}) {
  const color = teamColor(team);
  const dims = {
    sm: "h-7 w-7 text-[0.625rem]",
    md: "h-9 w-9 text-xs",
    lg: "h-16 w-16 text-lg",
  }[size];
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full font-semibold",
        dims,
        className,
      )}
      style={{
        background: `color-mix(in srgb, ${color} 18%, transparent)`,
        color,
        boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${color} 40%, transparent)`,
      }}
    >
      {photoSrc ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={photoSrc}
          alt=""
          className="h-full w-full rounded-full object-cover object-top"
        />
      ) : (
        initials(name)
      )}
    </span>
  );
}

export function PlayerName({
  id,
  name,
  scorecardName,
  team,
  sub,
  size = "md",
  className,
  photoSrc,
}: {
  id: string;
  name: string;
  scorecardName?: string | null;
  team?: string | null;
  sub?: React.ReactNode;
  size?: "sm" | "md";
  className?: string;
  photoSrc?: string | null;
}) {
  // Only worth showing when it differs: "Mohit Sharma" is both names at once.
  const showScorecard = scorecardName && scorecardName !== name;
  return (
    <span className={cn("flex min-w-0 items-center gap-2.5", className)}>
      <PlayerAvatar
        name={name}
        team={team}
        size={size === "sm" ? "sm" : "md"}
        photoSrc={photoSrc}
      />
      <span className="min-w-0">
        <Link
          href={`/players/${id}`}
          className={cn(
            "block truncate font-display font-semibold text-ink transition-colors hover:text-accent",
            size === "sm" ? "text-sm" : "text-[0.9375rem]",
          )}
        >
          {name}
        </Link>
        <span className="block truncate text-2xs text-ink-faint">
          {sub ?? (showScorecard ? scorecardName : null)}
        </span>
      </span>
    </span>
  );
}

/** Team chip: colour first, then the short name a fan already uses. */
export function TeamChip({ name, className }: { name: string | null | undefined; className?: string }) {
  const color = teamColor(name);
  if (!name) return null;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-2xs",
        className,
      )}
      style={{
        background: `color-mix(in srgb, ${color} 14%, transparent)`,
        color,
      }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} aria-hidden />
      {name}
    </span>
  );
}
