import * as React from "react";
import { teamIdentity } from "@/lib/teams";
import { cn } from "@/lib/utils";

/**
 * A franchise badge.
 *
 * The real IPL crests are trademarks, so these are original shield marks. The
 * emblem inside each one is a simplified landmark from the team's own city —
 * the Charminar for Hyderabad, Howrah Bridge for Kolkata, a gopuram for
 * Chennai — which ties the badge to the franchise without imitating anyone's
 * artwork, and gives a fan something they recognise.
 *
 * If you hold the rights to the real crests, drop files at
 * `public/teams/<SHORT>.svg` (or .png/.webp) and they are used instead; see
 * `teamLogo()` in lib/photos.ts.
 */
type Emblem =
  | "gopuram"    // Chennai temple tower
  | "gateway"    // Gateway of India, Mumbai
  | "dome"       // Vidhana Soudha, Bengaluru
  | "bridge"     // Howrah Bridge, Kolkata
  | "charminar"  // Charminar, Hyderabad
  | "hawamahal"  // Hawa Mahal, Jaipur
  | "indiagate"  // India Gate, Delhi
  | "wheat"      // Punjab's fields
  | "darwaza"    // Rumi Darwaza, Lucknow
  | "kite"       // Uttarayan kites, Gujarat
  | "fishingnet" // Chinese fishing nets, Kochi
  | "fort";      // Shaniwar Wada, Pune

/** Each franchise's city, not a guess from the colour. */
const EMBLEMS: Record<string, Emblem> = {
  CSK: "gopuram",
  MI: "gateway",
  RCB: "dome",
  KKR: "bridge",
  SRH: "charminar",
  DCH: "charminar",
  RR: "hawamahal",
  DC: "indiagate",
  DD: "indiagate",
  PBKS: "wheat",
  LSG: "darwaza",
  GT: "kite",
  GL: "kite",
  KTK: "fishingnet",
  RPS: "fort",
  PW: "fort",
};

function Emblem({ emblem, color }: { emblem: Emblem; color: string }) {
  const s = {
    fill: "none",
    stroke: color,
    strokeWidth: 2.4,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    opacity: 0.85,
  };
  switch (emblem) {
    case "gopuram":
      return (
        <g {...s}>
          <path d="M22 48 L24 34 H40 L42 48 Z" />
          <path d="M26 34 L27 26 H37 L38 34" />
          <path d="M29 26 L32 19 L35 26" />
          <path d="M28 48 V40 H36 V48" />
        </g>
      );
    case "gateway":
      return (
        <g {...s}>
          <path d="M20 48 V28 H44 V48" />
          <path d="M27 48 V36 A5 5 0 0 1 37 36 V48" />
          <path d="M18 28 H46" />
          <path d="M23 28 V22 M41 28 V22" />
        </g>
      );
    case "dome":
      return (
        <g {...s}>
          <path d="M18 48 V34 H46 V48" />
          <path d="M25 34 A7 7 0 0 1 39 34" />
          <path d="M32 22 V27" />
          <path d="M24 48 V40 M32 48 V40 M40 48 V40" />
        </g>
      );
    case "bridge":
      return (
        <g {...s}>
          <path d="M16 46 H48" />
          <path d="M22 46 V26 M42 46 V26" />
          <path d="M22 26 L32 38 L42 26" />
          <path d="M22 32 L42 32" />
        </g>
      );
    case "charminar":
      return (
        <g {...s}>
          <path d="M19 48 V30 H45 V48" />
          <path d="M28 48 V38 A4 4 0 0 1 36 38 V48" />
          <path d="M21 30 V22 M43 30 V22" />
          <path d="M21 22 L21 19 M43 22 L43 19" />
        </g>
      );
    case "hawamahal":
      return (
        <g {...s}>
          <path d="M18 48 V32 L32 22 L46 32 V48" />
          <path d="M24 48 V40 A3 3 0 0 1 30 40 V48" />
          <path d="M34 48 V40 A3 3 0 0 1 40 40 V48" />
          <path d="M26 33 H38" />
        </g>
      );
    case "indiagate":
      return (
        <g {...s}>
          <path d="M22 48 V26 H42 V48" />
          <path d="M29 48 V34 A5 6 0 0 1 35 34 V48" />
          <path d="M20 26 H44" />
        </g>
      );
    case "wheat":
      return (
        <g {...s}>
          <path d="M32 50 V26" />
          <path d="M32 30 C26 30 24 26 24 22 C29 22 32 25 32 30" />
          <path d="M32 30 C38 30 40 26 40 22 C35 22 32 25 32 30" />
          <path d="M32 38 C26 38 24 34 24 30 C29 30 32 33 32 38" />
          <path d="M32 38 C38 38 40 34 40 30 C35 30 32 33 32 38" />
        </g>
      );
    case "darwaza":
      return (
        <g {...s}>
          <path d="M20 48 V28 H44 V48" />
          <path d="M28 48 V34 A6 8 0 0 1 36 34 V48" />
          <path d="M20 28 Q32 18 44 28" />
          <path d="M32 18 V14" />
        </g>
      );
    case "kite":
      return (
        <g {...s}>
          <path d="M32 18 L44 32 L32 46 L20 32 Z" />
          <path d="M32 18 V46 M20 32 H44" />
          <path d="M32 46 Q36 50 32 54" />
        </g>
      );
    case "fishingnet":
      return (
        <g {...s}>
          <path d="M16 46 H48" />
          <path d="M22 46 L32 22 L42 46" />
          <path d="M26 34 H38" />
          <path d="M32 22 V16" />
        </g>
      );
    default:
      return (
        <g {...s}>
          <path d="M18 48 V30 H46 V48" />
          <path d="M27 48 V36 H37 V48" />
          <path d="M18 30 L32 21 L46 30" />
        </g>
      );
  }
}

/** A franchise with no entry gets a plain shield rather than a wrong landmark. */
function emblemFor(short: string): Emblem | null {
  return EMBLEMS[short] ?? null;
}

export function TeamCrest({
  team,
  size = 64,
  className,
  logoSrc,
}: {
  team: string | null | undefined;
  size?: number;
  className?: string;
  /** Operator-supplied artwork, used in place of the generated badge. */
  logoSrc?: string | null;
}) {
  const identity = teamIdentity(team);
  const id = React.useId();
  const emblem = emblemFor(identity.short);

  if (logoSrc) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={logoSrc}
        alt={`${team} crest`}
        width={size}
        height={size}
        className={cn("shrink-0 object-contain", className)}
      />
    );
  }

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 72"
      className={cn("shrink-0", className)}
      role="img"
      aria-label={`${team ?? "Team"} badge`}
    >
      <defs>
        <linearGradient id={`crest-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={identity.primary} stopOpacity={0.34} />
          <stop offset="100%" stopColor={identity.secondary} stopOpacity={0.12} />
        </linearGradient>
      </defs>
      <path
        d="M32 2 L60 10 V34 C60 50 48 62 32 70 C16 62 4 50 4 34 V10 Z"
        fill={`url(#crest-${id})`}
        stroke={identity.primary}
        strokeWidth={2}
        strokeOpacity={0.8}
      />
      {emblem ? (
        <g transform={size >= 56 ? "translate(0,-2)" : "translate(0,4)"}>
          <Emblem emblem={emblem} color={identity.primary} />
        </g>
      ) : null}
      {/* The short name is only legible above ~56px; at card size it is already
          set in large type beside the badge. */}
      {size >= 56 ? (
        <text
          x={32}
          y={63}
          textAnchor="middle"
          className="font-display"
          fontSize={12}
          fontWeight={700}
          fill={identity.primary}
        >
          {identity.short}
        </text>
      ) : null}
    </svg>
  );
}
