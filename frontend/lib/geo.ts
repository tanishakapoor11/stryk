import { headers } from "next/headers";

/**
 * Where the reader appears to be, as an ISO 3166-1 alpha-2 code.
 *
 * This is a hint for ordering, never for access or for filtering anything
 * out: a wrong guess should cost a reader one extra glance, not hide a
 * competition from them. Nothing is stored and nothing is sent anywhere —
 * the request carries it, and it is read for the length of the render.
 */
const GEO_HEADERS = [
  "x-vercel-ip-country",
  "cf-ipcountry",
  "cloudfront-viewer-country",
  "x-geo-country",
];

/** Cloudflare's "unknown", Tor, anonymising proxies, and the EU placeholder. */
const NOT_A_COUNTRY = new Set(["XX", "T1", "A1", "A2", "AP", "EU"]);

export function visitorCountry(): string | null {
  const h = headers();
  for (const name of GEO_HEADERS) {
    const value = h.get(name)?.trim().toUpperCase();
    if (value && /^[A-Z]{2}$/.test(value) && !NOT_A_COUNTRY.has(value)) return value;
  }
  // Deliberately no Accept-Language fallback. "en-GB" and "en-US" are the
  // factory setting on devices all over the world, so the language tag says
  // where a phone was configured far more often than where it is: this very
  // machine, in India, asks for en-GB. A guess that wrong is worse than no
  // guess, because the page then explains an order it got backwards. Without
  // a country header the directory keeps its normal order.
  return null;
}

/**
 * The ISO alpha-2 region inside a flag emoji.
 *
 * Cricket codes are their own thing — IND, RSA, ENG — and mapping 111 of them
 * onto ISO by hand is 111 chances to be wrong. The flag already holds the
 * answer: it is two regional indicator letters, so 🇮🇳 decodes to IN and the
 * catalogue stays the single source of truth.
 */
export function flagRegion(flag: string | null | undefined): string | null {
  if (!flag) return null;
  // Array.from walks code points, which matters: every character here is a
  // surrogate pair, and indexing by UTF-16 unit would split each one in half.
  const points = Array.from(flag).map((c) => c.codePointAt(0) ?? 0);
  const indicators = points
    .filter((c) => c >= 0x1f1e6 && c <= 0x1f1ff)
    .map((c) => String.fromCharCode(c - 0x1f1e6 + 65))
    .join("");
  if (indicators.length === 2) return indicators;
  // England, Scotland and Wales fly a subdivision flag: a black flag followed
  // by tag characters spelling "gbeng". The first two are the country, which
  // is why a reader in the UK meets county cricket first.
  const tags = points
    .filter((c) => c >= 0xe0061 && c <= 0xe007a)
    .map((c) => String.fromCodePoint(c - 0xe0000))
    .join("");
  return tags.length >= 2 ? tags.slice(0, 2).toUpperCase() : null;
}
