import type { CompetitionCard, CompetitionType, CoverageStatus, Gender, SeasonStatus } from "@/types";

/**
 * Display vocabulary for competitions. One place, so a type or coverage status
 * reads the same on every page.
 */
export const TYPE_LABEL: Record<CompetitionType, string> = {
  INTERNATIONAL: "International",
  ICC_TOURNAMENT: "ICC tournament",
  DOMESTIC: "Domestic",
  FRANCHISE_LEAGUE: "Franchise league",
  REGIONAL: "Regional",
  OTHER: "Other",
};

export const GENDER_LABEL: Record<Gender, string> = {
  MEN: "Men",
  WOMEN: "Women",
  MIXED: "Mixed",
  UNKNOWN: "Unspecified",
};

export const SEASON_STATUS_LABEL: Record<SeasonStatus, string> = {
  upcoming: "Upcoming",
  in_progress: "In progress",
  completed: "Completed",
  unknown: "Status unknown",
};

/** Coverage tone: what a reader can rely on, most to least. */
export const COVERAGE_TONE: Record<CoverageStatus, "accent" | "info" | "warn" | "default" | "danger"> = {
  ball_by_ball: "accent",
  detailed: "info",
  scorecard: "info",
  results: "warn",
  metadata: "warn",
  mixed: "warn",
  not_ingested: "default",
  unavailable: "default",
};

export const COVERAGE_EXPLAINER: Record<CoverageStatus, string> = {
  ball_by_ball: "Every delivery is held, so every statistic on this page is computed from the balls.",
  detailed: "Batting and bowling figures per player, without ball-by-ball detail.",
  scorecard: "Scorecards only: no phase, match-up or delivery-level statistics.",
  results: "Results only: no player statistics.",
  metadata: "Fixtures and metadata only: no results or statistics.",
  mixed: "Coverage varies between matches; statistics cover only the matches with detail.",
  not_ingested: "A source publishes this competition, but it has not been imported yet.",
  unavailable: "No data source STRYK uses publishes this competition.",
};

/** URL form of a season name: "2023/24" -> "2023-24". */
export function seasonSlug(name: string): string {
  return name.replace(/\//g, "-");
}

/** A factual one-line description composed from metadata, never written from memory. */
export function describeCompetition(c: CompetitionCard): string {
  const bits = [
    c.gender === "WOMEN" ? "Women's" : c.gender === "MEN" ? "Men's" : null,
    TYPE_LABEL[c.type].toLowerCase(),
    c.formats.length ? `(${c.formats.join(", ")})` : null,
    c.country ? `in ${c.country.name}` : null,
    c.governing_body ? `· ${c.governing_body}` : null,
  ];
  return bits.filter(Boolean).join(" ");
}

export const DIRECTORY_PRESETS = {
  all: { title: "Competitions", eyebrow: "Every competition", query: {} },
  international: {
    title: "International cricket",
    eyebrow: "Tests, ODIs and T20Is",
    query: { type: ["INTERNATIONAL"] },
  },
  tournaments: {
    title: "ICC tournaments",
    eyebrow: "World Cups and global events",
    query: { type: ["ICC_TOURNAMENT"] },
  },
  domestic: {
    title: "Domestic cricket",
    eyebrow: "First-class, one-day and T20 competitions by country",
    query: { type: ["DOMESTIC"] },
  },
  leagues: {
    title: "Franchise leagues",
    eyebrow: "T20 and Hundred leagues worldwide",
    query: { type: ["FRANCHISE_LEAGUE"] },
  },
  women: {
    title: "Women's cricket",
    eyebrow: "International, ICC, franchise and domestic",
    query: { gender: "WOMEN" },
  },
} as const;
export type DirectoryPreset = keyof typeof DIRECTORY_PRESETS;
