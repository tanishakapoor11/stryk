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

const TEAM_DIR = path.join(process.cwd(), "public", "teams");

let teamFiles: Map<string, string> | null = null;

/**
 * One listing of public/teams, keyed by basename without extension.
 *
 * This used to stat three candidate paths per team per render; a competition
 * with 26 sides on screen was 78 filesystem calls on every request. The
 * directory is read once instead. As with the photo credits, only a successful
 * read is cached, so a dev server started before any artwork was added picks
 * it up on the next request rather than looking permanently broken.
 */
function teamIndex(): Map<string, string> {
  if (teamFiles) return teamFiles;
  try {
    const index = new Map<string, string>();
    for (const name of fs.readdirSync(TEAM_DIR)) {
      const ext = path.extname(name).slice(1).toLowerCase();
      if (!["svg", "png", "webp", "jpg", "jpeg"].includes(ext)) continue;
      // First extension wins in the order listed above, so a vector file is
      // preferred over a bitmap of the same name.
      const key = path.basename(name, path.extname(name)).toLowerCase();
      if (!index.has(key)) index.set(key, name);
    }
    // Cached in production only, where the directory cannot change while the
    // server runs. In development it is re-read every time: artwork gets
    // added and removed constantly while a set is being assembled, and a
    // cached listing is wrong in both directions — a file added after the
    // server started never appears, and one deleted leaves the page pointing
    // at a 404. Either looks exactly like "the logos do not work". A readdir
    // of a directory this size is a single cheap syscall; the 78 existsSync
    // calls per page this replaced were the thing worth avoiding.
    if (process.env.NODE_ENV === "production") teamFiles = index;
    return index;
  } catch {
    return new Map();
  }
}

/** `Royal Challengers Bengaluru` -> `royal-challengers-bengaluru`. */
export function teamSlug(name: string): string {
  return name
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/**
 * Team artwork supplied by the operator, if any.
 *
 * Looked up by the team's full name slugged (`sydney-sixers.svg`), which is
 * unique across the whole dataset. The abbreviation is tried second, for
 * artwork added before this existed — it is not a safe key on its own, because
 * across 151 competitions the short forms collide: Kent and Kenya are both
 * KEN, Northamptonshire and Norway both NOR.
 *
 * Nothing is bundled with the project. Drop files into
 * `frontend/public/teams/` and they are picked up automatically; teams with
 * none fall back to a flag, then to the generated badge.
 */
export function teamLogo(name: string | null | undefined, short?: string | null): string | null {
  const index = teamIndex();
  for (const key of [name ? teamSlug(name) : "", (short ?? "").toLowerCase()]) {
    const file = key && index.get(key);
    if (file) return `/teams/${encodeURIComponent(file)}`;
  }
  return null;
}
