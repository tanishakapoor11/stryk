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
  | "fort"        // Shaniwar Wada, Pune / Bala Hisar, Peshawar
  // Big Bash
  | "operahouse"  // Sydney Opera House
  | "harbourbr"   // Sydney Harbour Bridge
  | "spire"       // Arts Centre spire, Melbourne
  | "clocktower"  // Flinders Street Station, Melbourne
  | "belltower"   // Swan Bell Tower, Perth
  | "cathedral"   // St Peter's twin spires, Adelaide
  | "storybridge" // Story Bridge, Brisbane
  | "mountain"    // kunanyi / Mt Wellington, Hobart; the Quetta ranges
  // The Hundred
  | "rotunda"     // the Rotunda, Birmingham
  | "mediacentre" // the pavilion at Lord's
  | "gasholder"   // the gasholder at the Oval
  | "tower"       // Beetham Tower, Manchester
  | "townhall"    // Leeds Town Hall
  | "sail"        // Southampton, a port
  | "castle"      // Nottingham Castle
  | "flame"       // Welsh Fire, named for it
  | "towerbridge" // Tower Bridge, London
  // Pakistan Super League
  | "minaret"     // Minar-e-Pakistan, Lahore
  | "mausoleum"   // Mazar-e-Quaid, Karachi
  | "tentmosque"  // Faisal Mosque, Islamabad
  | "shrine";     // the Sufi shrines of Multan

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

  // Big Bash. Two clubs share Sydney and two share Melbourne, so each takes a
  // different landmark of its own city rather than repeating one.
  SIX: "operahouse", THU: "harbourbr",
  STA: "spire", REN: "clocktower",
  SCO: "belltower", STR: "cathedral", HEA: "storybridge", HUR: "mountain",

  // The Hundred. The 2025 rebrands keep their club's landmark, because they
  // are the same club under a new owner, not a new one.
  BPH: "rotunda", LNS: "mediacentre", OVI: "gasholder",
  MNR: "tower", MSG: "tower",
  NOS: "townhall", SUL: "townhall",
  SOB: "sail", TRT: "castle", WEF: "flame", MIL: "towerbridge",

  // Pakistan Super League.
  LAH: "minaret", KAR: "mausoleum", ISL: "tentmosque",
  MUL: "shrine", PES: "fort", QUE: "mountain",
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
    case "operahouse":
      return (
        <g {...s}>
          <path d="M16 48 H48" />
          <path d="M19 48 C19 39 23 33 29 31 L29 48" />
          <path d="M27 48 C27 37 31 31 37 29 L37 48" />
          <path d="M35 48 C35 35 39 29 45 27 L45 48" />
        </g>
      );
    case "harbourbr":
      return (
        <g {...s}>
          <path d="M16 46 H48" />
          <path d="M21 46 V28 M43 46 V28" />
          <path d="M18 38 Q32 21 46 38" />
          <path d="M18 38 H46" />
        </g>
      );
    case "spire":
      return (
        <g {...s}>
          <path d="M20 48 H44" />
          <path d="M26 48 L32 30 L38 48" />
          <path d="M32 48 V17" />
          <path d="M28 37 H36" />
        </g>
      );
    case "clocktower":
      return (
        <g {...s}>
          <path d="M20 48 H44" />
          <path d="M26 48 V28 H38 V48" />
          <path d="M26 28 Q32 21 38 28" />
          <path d="M32 21 V17" />
          <circle cx="32" cy="37" r="4" />
        </g>
      );
    case "belltower":
      return (
        <g {...s}>
          <path d="M20 48 H44" />
          <path d="M28 48 V26 H36 V48" />
          <path d="M32 26 V17" />
          <path d="M22 41 L28 33 M42 41 L36 33" />
        </g>
      );
    case "cathedral":
      return (
        <g {...s}>
          <path d="M19 48 H45" />
          <path d="M22 48 V33 H42 V48" />
          <path d="M25 33 L28 20 L31 33" />
          <path d="M33 33 L36 20 L39 33" />
        </g>
      );
    case "storybridge":
      return (
        <g {...s}>
          <path d="M16 45 H48" />
          <path d="M24 45 V27 M40 45 V27" />
          <path d="M16 36 L24 27 L40 27 L48 36" />
          <path d="M24 36 H40" />
        </g>
      );
    case "mountain":
      return (
        <g {...s}>
          <path d="M16 46 H48" />
          <path d="M18 46 L27 29 L33 37 L39 24 L48 46" />
        </g>
      );
    case "rotunda":
      return (
        <g {...s}>
          <path d="M20 48 H44" />
          <path d="M26 48 V29 H38 V48" />
          <path d="M26 29 Q32 25 38 29" />
          <path d="M26 35 H38 M26 41 H38" />
        </g>
      );
    case "mediacentre":
      return (
        <g {...s}>
          <path d="M18 48 H46" />
          <path d="M22 48 V32 H42 V48" />
          <path d="M20 32 L32 22 L44 32" />
          <path d="M28 48 V40 H36 V48" />
          <circle cx="32" cy="29" r="2.5" />
        </g>
      );
    case "gasholder":
      return (
        <g {...s}>
          <path d="M18 48 H46" />
          <path d="M21 48 V28 H43 V48" />
          <path d="M27 28 V48 M32 28 V48 M37 28 V48" />
          <path d="M21 36 H43" />
        </g>
      );
    case "tower":
      return (
        <g {...s}>
          <path d="M22 48 H42" />
          <path d="M27 48 V20 H37 V48" />
          <path d="M37 20 V14" />
          <path d="M27 27 H37" />
        </g>
      );
    case "townhall":
      return (
        <g {...s}>
          <path d="M17 48 H47" />
          <path d="M21 48 V36 H43 V48" />
          <path d="M27 36 V22 H37 V36" />
          <path d="M27 22 Q32 15 37 22" />
          <path d="M32 15 V12" />
        </g>
      );
    case "sail":
      return (
        <g {...s}>
          <path d="M32 43 V17" />
          <path d="M32 19 L43 40 H32" />
          <path d="M32 25 L23 40 H32" />
          <path d="M21 43 Q32 49 43 43" />
        </g>
      );
    case "castle":
      return (
        <g {...s}>
          <path d="M18 48 H46" />
          <path d="M21 48 V30 H43 V48" />
          <path d="M21 30 V25 H26 V30 M29 30 V25 H34 V30 M37 30 V25 H43 V30" />
          <path d="M28 48 V39 A4 4 0 0 1 36 39 V48" />
        </g>
      );
    case "flame":
      return (
        <g {...s}>
          <path d="M32 50 C24 44 23 36 28 28 C29 32 31 33 32 31 C33 25 36 21 39 18 C38 25 44 29 42 38 C41 45 36 49 32 50 Z" />
        </g>
      );
    case "towerbridge":
      return (
        <g {...s}>
          <path d="M14 46 H50" />
          <path d="M22 46 V26 H28 V46 M36 46 V26 H42 V46" />
          <path d="M23 26 V21 H27 V26 M37 26 V21 H41 V26" />
          <path d="M28 32 H36" />
          <path d="M14 40 H22 M42 40 H50" />
        </g>
      );
    case "minaret":
      return (
        <g {...s}>
          <path d="M21 48 H43" />
          <path d="M26 44 H38" />
          <path d="M30 44 V28 L32 16 L34 28 V44" />
        </g>
      );
    case "mausoleum":
      return (
        <g {...s}>
          <path d="M19 48 H45" />
          <path d="M22 48 V35 H42 V48" />
          <path d="M24 35 Q32 20 40 35" />
          <path d="M32 20 V16" />
          <path d="M28 48 V41 A4 4 0 0 1 36 41 V48" />
        </g>
      );
    case "tentmosque":
      return (
        <g {...s}>
          <path d="M16 46 H48" />
          <path d="M21 46 L32 28 L43 46 Z" />
          <path d="M23 46 V23 M41 46 V23" />
          <path d="M23 23 V19 M41 23 V19" />
        </g>
      );
    case "shrine":
      return (
        <g {...s}>
          <path d="M18 48 H46" />
          <path d="M23 48 V37 H41 V48" />
          <path d="M25 37 Q32 18 39 37" />
          <path d="M32 18 V14" />
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

/**
 * The tile a flag or a supplied logo sits in. One constant, because the two
 * appear side by side in the same column and must not read as two different
 * kinds of thing.
 */
const BADGE_TILE =
  "inline-flex shrink-0 items-center justify-center overflow-hidden " +
  "rounded-lg border border-line bg-surface-raised";

/** A franchise with no entry gets a plain shield rather than a wrong landmark. */
function emblemFor(short: string): Emblem | null {
  return EMBLEMS[short] ?? null;
}

export function TeamCrest({
  team,
  size = 64,
  className,
  logoSrc,
  flag,
  short,
}: {
  team: string | null | undefined;
  size?: number;
  className?: string;
  /** Operator-supplied artwork, used in place of the generated badge. */
  logoSrc?: string | null;
  /**
   * A national side's flag, from the API. A nation has a flag and no crest
   * problem: it is not owned artwork and it is not a guess, which is why the
   * country is the one case where real identity can be shown. Club crests
   * stay generated, because they are trademarks.
   */
  flag?: string | null;
  /** The API's abbreviation, when the caller has one. */
  short?: string | null;
}) {
  const identity = teamIdentity(team, short);
  const id = React.useId();
  const emblem = emblemFor(identity.short);

  if (flag && !logoSrc) {
    return (
      <span
        role="img"
        aria-label={`${team ?? "Team"} flag`}
        className={cn(BADGE_TILE, className)}
        style={{ width: size, height: size }}
      >
        {/* ponytail: emoji flag — zero assets, renders natively on macOS,
            iOS and Android. Windows has no flag glyphs and falls back to the
            two country letters, which is legible but plain. Upgrade path:
            drop SVGs at public/flags/<CODE>.svg and prefer them here. */}
        <span
          aria-hidden
          style={{
            fontSize: Math.round(size * 0.62),
            lineHeight: 1,
            // The brand display face has no emoji glyphs; name the system
            // emoji fonts so the flag is never substituted into tofu.
            fontFamily:
              '"Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji","Twemoji Mozilla",sans-serif',
          }}
        >
          {flag}
        </span>
      </span>
    );
  }

  if (logoSrc) {
    // The same tile the flag sits in, deliberately. A logo is one badge in a
    // column of them, and giving it a light plate of its own made the one
    // team that had artwork look like a sticker stuck on the card while every
    // other side sat flat against it. Whatever the tile is, both wear it.
    //
    // The cost is that artwork inked for white paper - a black or navy
    // wordmark - has little contrast here. That is a property of the file,
    // not of the layout, and the fix is to supply the light-background
    // variant of the mark, which every club publishes.
    return (
      <span
        className={cn(BADGE_TILE, "p-1", className)}
        // Height is fixed so a row of badges aligns, but a wide wordmark may
        // spread to 1.6x before it is squeezed - at a square 44px a 2.77:1
        // mark renders 13px tall and cannot be read.
        style={{ height: size, minWidth: size, maxWidth: Math.round(size * 1.6) }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={logoSrc}
          alt={`${team ?? "Team"} crest`}
          // object-contain, never cover: a crest cropped to fill the box is a
          // mangled trademark, which is worse than a small one.
          className="max-h-full max-w-full object-contain"
        />
      </span>
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
