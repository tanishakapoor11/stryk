import type { MetadataRoute } from "next";
import { api } from "@/lib/api";
import { SITE_URL } from "@/lib/seo";

/** Rebuilt daily; the data only changes when an ingest runs. */
export const revalidate = 86400;

/**
 * A player with one or two appearances has a near-empty profile. Thousands of
 * those are worth less to a search engine than the few thousand people
 * actually look for, and thin pages drag the rest of the site down with them.
 * They stay crawlable through links; they are just not advertised here.
 */
const MIN_APPEARANCES = 3;

type SitemapData = {
  competitions: { slug: string; last_match: string }[];
  seasons: { competition: string; season: string; last_match: string }[];
  teams: { id: number }[];
  players: { id: string; matches: number }[];
};

const STATIC_PATHS = [
  ["/", 1.0],
  ["/competitions", 0.9],
  ["/leagues", 0.8],
  ["/tournaments", 0.8],
  ["/international", 0.8],
  ["/domestic", 0.7],
  ["/women", 0.8],
  ["/players", 0.7],
  ["/teams", 0.7],
  ["/matchups", 0.5],
  ["/auction", 0.4],
] as const;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();
  const base: MetadataRoute.Sitemap = STATIC_PATHS.map(([path, priority]) => ({
    url: `${SITE_URL}${path}`,
    lastModified: now,
    changeFrequency: "daily",
    priority,
  }));

  let data: SitemapData;
  try {
    data = await api<SitemapData>("/api/sitemap", {}, { revalidate });
  } catch {
    // A sitemap that 500s is worse than one listing only the fixed pages:
    // crawlers back off from a URL that keeps failing.
    return base;
  }

  return [
    ...base,
    ...data.competitions.map((c) => ({
      url: `${SITE_URL}/competitions/${c.slug}`,
      lastModified: new Date(c.last_match),
      changeFrequency: "weekly" as const,
      priority: 0.8,
    })),
    ...data.seasons.map((s) => ({
      url: `${SITE_URL}/competitions/${s.competition}/${s.season}`,
      lastModified: new Date(s.last_match),
      changeFrequency: "monthly" as const,
      priority: 0.6,
    })),
    ...data.teams.map((t) => ({
      url: `${SITE_URL}/teams/${t.id}`,
      lastModified: now,
      changeFrequency: "weekly" as const,
      priority: 0.6,
    })),
    ...data.players
      .filter((p) => p.matches >= MIN_APPEARANCES)
      .map((p) => ({
        url: `${SITE_URL}/players/${p.id}`,
        lastModified: now,
        changeFrequency: "weekly" as const,
        priority: 0.5,
      })),
  ];
}
