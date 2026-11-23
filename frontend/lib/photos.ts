import "server-only";
import fs from "node:fs";
import path from "node:path";

/**
 * Player photographs fetched from Wikimedia Commons.
 *
 * Most Commons licences require credit, so a photo is only shown when its
 * author and licence were recorded alongside it; anything uncredited is left
 * out and the player keeps their generated monogram. See
 * scripts/fetch_player_photos.py.
 */
export interface PhotoCredit {
  file: string;
  author: string;
  licence: string;
  source: string;
}

const CREDITS_PATH = path.join(process.cwd(), "public", "players", "credits.json");

let cache: Record<string, PhotoCredit> | null = null;

function load(): Record<string, PhotoCredit> {
  if (cache) return cache;
  try {
    const parsed = JSON.parse(fs.readFileSync(CREDITS_PATH, "utf8")) as Record<string, PhotoCredit>;
    // Only a successful read is cached. Caching the failure would mean a dev
    // server started before the photos were fetched never picks them up, which
    // looks exactly like "the photos do not work".
    cache = parsed;
    return cache;
  } catch {
    // No photos fetched yet. The interface is built to work without them.
    return {};
  }
}

export function photoFor(playerId: string): { src: string; credit: PhotoCredit } | null {
  const credit = load()[playerId];
  if (!credit) return null;
  return { src: `/players/${playerId}.jpg`, credit };
}

/** Which of these players have a photo — used to pick who to feature. */
export function withPhotos(playerIds: string[]): Set<string> {
  const credits = load();
  return new Set(playerIds.filter((id) => credits[id]));
}

/** Operator-supplied team artwork at public/teams/<short>.(svg|png), if any. */
export function teamLogo(short: string): string | null {
  for (const ext of ["svg", "png", "webp"]) {
    const file = path.join(process.cwd(), "public", "teams", `${short}.${ext}`);
    try {
      if (fs.existsSync(file)) return `/teams/${short}.${ext}`;
    } catch {
      /* unreadable public dir */
    }
  }
  return null;
}
