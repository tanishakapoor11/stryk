/**
 * The API contract, declared once on the client side.
 *
 * The FastAPI layer returns analytical documents assembled by pandas; these
 * types are the single hand-maintained description of that shape.
 */

export type Nullable<T> = T | null;

export interface BattingLine {
  player_id?: string;
  player_name?: string;
  innings: number;
  matches?: number;
  runs: number;
  balls: number;
  fours: number;
  sixes: number;
  dots: number;
  outs: number;
  not_outs: number;
  average: Nullable<number>;
  strike_rate: Nullable<number>;
  boundary_pct: Nullable<number>;
  dot_pct: Nullable<number>;
  boundary_run_pct: Nullable<number>;
  highest_score: number;
  highest_not_out?: boolean;
  fifties: number;
  hundreds: number;
  thirties: number;
}

export interface BowlingLine {
  player_id?: string;
  player_name?: string;
  innings: number;
  matches?: number;
  balls: number;
  overs: string;
  runs: number;
  wickets: number;
  dots: number;
  average: Nullable<number>;
  economy: Nullable<number>;
  strike_rate: Nullable<number>;
  dot_pct: Nullable<number>;
  boundary_pct: Nullable<number>;
  four_wicket_hauls: number;
  five_wicket_hauls: number;
  best_wickets?: Nullable<number>;
  best_runs?: Nullable<number>;
  wides?: number;
  noballs?: number;
}

export type PhaseLine = { phase: string } & Partial<BattingLine> & Partial<BowlingLine>;

export interface Summary {
  matches: number;
  deliveries: number;
  players: number;
  teams: number;
  seasons: number;
  season_range: number[];
  venues: number;
  runs: number;
  wickets: number;
  last_updated: string;
  source: string;
  /** Names of the competitions this summary covers. */
  competitions?: string[];
}

export interface Insight {
  title: string;
  detail: string;
  metric: Nullable<string>;
  context: Nullable<string>;
  link: Nullable<string>;
}

export interface SeasonTrend {
  season: number;
  runs: number;
  balls: number;
  wickets: number;
  matches: number;
  run_rate: number;
  balls_per_wicket: number;
  boundary_pct: number;
}

export interface PhaseTrend {
  season: number;
  phase: string;
  runs: number;
  balls: number;
  wickets: number;
  run_rate: number;
}

export interface TeamTrend {
  season: number;
  team_id: number;
  team_name: string;
  played: number;
  won: number;
  win_pct: number;
}

export interface QualifiedBoard {
  qualification: string;
  rows: Array<Record<string, unknown>>;
}

/** Whether STRYK holds every season a competition has played. */
export interface ScopeCoverage {
  complete: boolean | null;
  /** The year the competition began, null where its lineage is ambiguous. */
  begins: number | null;
  indexed_from: number | null;
  indexed_to: number | null;
}

export interface OverviewPayload {
  scope?: Scope;
  coverage?: ScopeCoverage;
  summary: Summary;
  leaderboards: {
    most_runs: BattingLine[];
    most_wickets: BowlingLine[];
    highest_scores: Array<Record<string, any>>;
    best_figures: Array<Record<string, any>>;
    best_strike_rate: QualifiedBoard;
    best_economy: QualifiedBoard;
    best_average: QualifiedBoard;
  };
  trends: { seasons: SeasonTrend[]; phases: PhaseTrend[]; teams: TeamTrend[] };
  distribution: {
    batting: Array<{ player_id: string; player_name: string; runs: number; average: number; strike_rate: number; boundary_pct: number }>;
    bowling: Array<{ player_id: string; player_name: string; wickets: number; average: number; economy: number; dot_pct: number }>;
  };
  insights: Insight[];
  featured_innings: Nullable<FeaturedInnings>;
  filters: Record<string, unknown>;
}

export interface PlayerRow {
  player_id: string;
  name: string;
  /** The Cricsheet scorecard form ("SS Iyer"), when it differs from `name`. */
  scorecard_name?: Nullable<string>;
  role: Nullable<string>;
  team_id: Nullable<number>;
  team_name: Nullable<string>;
  matches: number;
  seasons: number;
  innings: Nullable<number>;
  runs: Nullable<number>;
  balls: Nullable<number>;
  batting_average: Nullable<number>;
  strike_rate: Nullable<number>;
  highest_score: Nullable<number>;
  fifties: Nullable<number>;
  hundreds: Nullable<number>;
  boundary_pct: Nullable<number>;
  wickets: Nullable<number>;
  overs: Nullable<string>;
  economy: Nullable<number>;
  bowling_average: Nullable<number>;
  balls_bowled: Nullable<number>;
}

export interface PlayerDirectory {
  total: number;
  limit: number;
  offset: number;
  sort: string;
  order: string;
  rows: PlayerRow[];
  filters: Record<string, unknown>;
}

export interface PlayerProfile {
  /** The competition scope this profile was computed over. */
  scope?: Scope;
  /** Every competition the player has appeared in, busiest first. */
  competitions?: EntityCompetition[];
  player: {
    id: string;
    name: string;
    scorecard_name: Nullable<string>;
    role: Nullable<string>;
    role_basis: Nullable<string>;
    matches: number;
    seasons: number[];
    teams: Array<{ team_id: number; team_name: string; matches: number; first_season: number; last_season: number }>;
  };
  filters: Record<string, unknown>;
  batting: Nullable<BattingLine>;
  bowling: Nullable<BowlingLine>;
  batting_by_phase: PhaseLine[];
  bowling_by_phase: PhaseLine[];
  batting_by_innings_type: { chasing: BattingLine[]; setting: BattingLine[] };
  bowling_by_innings_type: { defending: BowlingLine[]; first_innings: BowlingLine[] };
  batting_by_season: Array<BattingLine & { season: number }>;
  bowling_by_season: Array<BowlingLine & { season: number }>;
  batting_by_venue: Array<BattingLine & { venue: string }>;
  bowling_by_venue: Array<BowlingLine & { venue: string }>;
  batting_by_opposition: Array<BattingLine & { opposition: string }>;
  bowling_by_opposition: Array<BowlingLine & { opposition: string }>;
  recent_innings: Array<{ date: string; opposition: string; runs: number; balls: number; fours: number; sixes: number; strike_rate: Nullable<number>; out: boolean; season: number; sequence: string[] }>;
  recent_spells: Array<{ date: string; opposition: string; overs: string; runs: number; wickets: number; economy: Nullable<number>; season: number }>;
  dismissal_patterns: Record<string, number>;
  scoring_shape: Nullable<ScoringShape>;
  by_over: OverProfile[];
  highlights: PlayerHighlight[];
  data_notes: {
    bowling_style_splits_available: boolean;
    bowling_style_note: string;
    qualification: Record<string, number>;
    metrics: Record<string, { label: string; formula: string; notes?: string }>;
    phases: string[];
  };
}

export interface Matchup {
  batter: { id: string; name: string };
  bowler: { id: string; name: string };
  filters: Record<string, unknown>;
  sample: { balls: number; innings: number; matches: number };
  reliability: { level: "none" | "insufficient" | "indicative" | "readable"; message: string };
  summary: {
    balls: number;
    runs: number;
    dismissals: number;
    bowler_dismissals: number;
    strike_rate: Nullable<number>;
    average: Nullable<number>;
    dot_pct: Nullable<number>;
    boundary_pct: Nullable<number>;
    fours: number;
    sixes: number;
    balls_per_dismissal: Nullable<number>;
  };
  baseline: { batter: Nullable<BattingLine>; bowler: Nullable<BowlingLine> };
  by_phase: Array<{ phase: string; balls: number; runs: number; dismissals: number; strike_rate: Nullable<number>; dot_pct: Nullable<number> }>;
  by_season: Array<{ season: number; balls: number; runs: number; dismissals: number; strike_rate: Nullable<number> }>;
  dismissal_log: Array<{ date: Nullable<string>; season: number; kind: string; phase: string; over: number; credited_to_bowler: boolean }>;
  notes: Record<string, unknown>;
}

export interface MatchupOpponent {
  opponent_id: string;
  opponent_name: string;
  balls: number;
  runs: number;
  dismissals: number;
  strike_rate: Nullable<number>;
  average: Nullable<number>;
  reliability: string;
}

export interface TeamSummary {
  id: number;
  name: string;
  short_name: Nullable<string>;
  /** A national side's flag emoji; null for clubs and the composite XIs. */
  flag: Nullable<string>;
  aliases: string[];
  matches: number;
  won: number;
  win_pct: Nullable<number>;
  first_season: number;
  last_season: number;
  active: boolean;
}

export interface TeamProfile {
  scope?: Scope;
  competitions?: EntityCompetition[];
  team: {
    id: number;
    name: string;
    short_name: Nullable<string>;
    flag: Nullable<string>;
    aliases: string[];
  };
  filters: Record<string, unknown>;
  record: { played: number; won: number; lost: number; no_result: number; win_pct: Nullable<number> };
  by_season: Array<{ season: number; played: number; won: number; lost: number; win_pct: Nullable<number> }>;
  squad: {
    players: Array<{
      player_id: string;
      name: string;
      matches: number;
      seasons: number[];
      role: Nullable<string>;
      batting_position: Nullable<number>;
      runs: number;
      balls: number;
      batting_average: Nullable<number>;
      strike_rate: Nullable<number>;
      wickets: number;
      overs: string;
      economy: Nullable<number>;
    }>;
    role_distribution: Record<string, number>;
  };
  batting_depth: Array<{ position: number; innings: number; runs: number; balls: number; outs: number; strike_rate: Nullable<number>; average: Nullable<number>; runs_per_innings: Nullable<number> }>;
  phase_profile: {
    batting: Array<{ phase: string; runs: number; balls: number; wickets: number; run_rate: Nullable<number>; league_run_rate: Nullable<number>; balls_per_wicket: Nullable<number> }>;
    bowling: Array<{ phase: string; runs: number; balls: number; wickets: number; run_rate: Nullable<number>; league_run_rate: Nullable<number>; balls_per_wicket: Nullable<number> }>;
  };
  innings_type: Record<string, { innings: number; runs: number; balls: number; run_rate: Nullable<number>; wickets_lost: number; wins: number }>;
  data_notes: Record<string, unknown>;
}

export interface SeasonMeta { season: number; matches: number }
export interface SearchHit {
  type: "player" | "team" | "competition" | "season";
  id: string | number;
  name: string;
  /** Scorecard name for a player, short name for a team or season's competition. */
  secondary: Nullable<string>;
  detail: Nullable<string>;
  href: string;
}
export interface MetricMeta {
  metrics: Record<string, { label: string; formula: string; notes?: string }>;
  qualification: Record<string, number>;
  phases: { order: string[]; definitions: Record<string, [string, number, number][]> };
  data_availability: Record<string, boolean>;
}

export interface AuctionCandidate {
  player_id: string;
  name: string;
  player_name?: string;
  role: Nullable<string>;
  team_id: Nullable<number>;
  team_name: Nullable<string>;
  matches: number;
  seasons: number;
  last_season: Nullable<number>;
  runs: number;
  balls_faced: number;
  strike_rate: Nullable<number>;
  batting_average: Nullable<number>;
  wickets: number;
  balls_bowled: number;
  overs: Nullable<string>;
  economy: Nullable<number>;
  batting_impact: Nullable<number>;
  bowling_impact: Nullable<number>;
  batting_impact_per_match: Nullable<number>;
  bowling_impact_per_match: Nullable<number>;
  /** Only present when an operator price file has been supplied. */
  price_inr?: Nullable<number>;
  price_season?: Nullable<number>;
}

export interface AuctionPool {
  total: number;
  returned: number;
  sort: string;
  rows: AuctionCandidate[];
  filters: Record<string, unknown>;
  qualification: Record<string, number>;
  method: Record<string, { label: string; formula: string; notes?: string }>;
  prices_available: boolean;
  price_note: string;
  price_file: string;
  requirements: Array<{ role: string; minimum: number; note: string }>;
}

export interface PlayerHighlight {
  text: string;
  figure: string;
  tone: "good" | "watch";
}

export interface FeaturedInnings {
  player_id: string;
  player_name: string;
  runs: number;
  balls: number;
  fours: number;
  sixes: number;
  out: boolean;
  opposition: Nullable<string>;
  team_name: Nullable<string>;
  season: number;
  date: Nullable<string>;
  sequence: string[];
  strike_rate: Nullable<number>;
}

export interface ScoringShape {
  balls: number;
  runs: number;
  buckets: Array<{
    runs_per_ball: Nullable<number>;
    label: string;
    balls: number;
    runs: number;
    ball_share: number;
    run_share: number;
  }>;
}

export interface OverProfile {
  over: number;
  balls_faced: number;
  runs: number;
  strike_rate: Nullable<number>;
  dismissals: number;
  balls_bowled: number;
  runs_conceded: number;
  economy: Nullable<number>;
  wickets: number;
}

/* ------------------------------------------------------------------ *
 * Competitions (global platform, Phase 1). Mirrors
 * backend/app/analytics/competitions.py.
 * ------------------------------------------------------------------ */
export type CompetitionType =
  | "INTERNATIONAL"
  | "ICC_TOURNAMENT"
  | "DOMESTIC"
  | "FRANCHISE_LEAGUE"
  | "REGIONAL"
  | "OTHER";
export type Gender = "MEN" | "WOMEN" | "MIXED" | "UNKNOWN";
export type CoverageStatus =
  | "ball_by_ball"
  | "detailed"
  | "scorecard"
  | "results"
  | "metadata"
  | "mixed"
  | "not_ingested"
  | "unavailable";
export type SeasonStatus = "upcoming" | "in_progress" | "completed" | "unknown";

export interface Scope {
  competitions: string[];
  gender: Nullable<Gender>;
  format: Nullable<string>;
}

export interface CountryRef {
  id: number;
  code: string;
  name: string;
  flag: Nullable<string>;
  cricket_board: Nullable<string>;
}

export interface SourceDatasetRef {
  source: string;
  dataset: string;
  name: string;
  url: string;
  published_matches: Nullable<number>;
  gender_filter: Nullable<Gender>;
  checked_on: Nullable<string>;
}

export interface Coverage {
  status: CoverageStatus;
  label: string;
  detail: Nullable<string>;
  matches: number;
  seasons: number;
  first_match?: string;
  last_match?: string;
  data_levels: number[];
  sources: SourceDatasetRef[];
}

export interface SeasonSummary {
  id: number;
  name: string;
  year: number;
  status: SeasonStatus;
  format: Nullable<string>;
  start_date: Nullable<string>;
  end_date: Nullable<string>;
  matches: number;
}

export interface CompetitionCard {
  id: number;
  slug: string;
  name: string;
  short_name: Nullable<string>;
  type: CompetitionType;
  gender: Gender;
  country: Nullable<CountryRef>;
  governing_body: Nullable<string>;
  description: Nullable<string>;
  formats: string[];
  is_active: boolean;
  is_catalogued: boolean;
  has_points_system: boolean;
  latest_season: Nullable<SeasonSummary>;
  coverage: Coverage;
}

export interface CompetitionDirectory {
  total: number;
  items: CompetitionCard[];
  limit: number;
  offset: number;
  facets: Record<"type" | "gender" | "country" | "format" | "coverage", Record<string, number>>;
}

export interface PointsSystemSummary {
  slug: string;
  name: string;
  points: Record<string, number | null>;
  tie_breakers: string[];
  tie_resolution: "super_over" | "shared";
  qualifiers: Nullable<number>;
  sources: string[];
  verified_on: Nullable<string>;
  notes: Nullable<string>;
}

export interface TeamRef {
  id: number;
  name: string;
  short_name: Nullable<string>;
}

export interface MatchRow {
  id: string;
  /** Present on cross-competition lists (home page). */
  competition?: { slug: string; name: string; short_name: Nullable<string> };
  date: string;
  match_number: Nullable<number>;
  stage: Nullable<string>;
  stage_type: Nullable<"league" | "group" | "knockout">;
  format: string;
  team1: TeamRef;
  team2: TeamRef;
  winner_id: Nullable<number>;
  result: string;
  status: string;
  venue: Nullable<{ name: string; city: Nullable<string> }>;
  data_level: Nullable<number>;
}

export interface SeasonTeam extends TeamRef {
  played: number;
  won: number;
}

export interface CompetitionDetail extends CompetitionCard {
  seasons: SeasonSummary[];
  points_system: Nullable<PointsSystemSummary>;
  unavailable_reason: Nullable<string>;
  fixtures: { available: boolean; reason: string };
  current_season: Nullable<SeasonSummary>;
  teams: SeasonTeam[];
  recent_results: MatchRow[];
  leaders: Nullable<OverviewPayload["leaderboards"]>;
  scope?: Scope;
}

export interface StandingsRow {
  position: number;
  team_id: number;
  name: string;
  short_name: Nullable<string>;
  played: number;
  won: number;
  lost: number;
  tied: number;
  drawn: number;
  no_result: number;
  points: number;
  net_run_rate: Nullable<number>;
  runs_for: number;
  overs_for: Nullable<string>;
  runs_against: number;
  overs_against: Nullable<string>;
  reached_knockouts: boolean;
}

export type Standings =
  | { available: false; reason: string }
  | {
      available: true;
      complete: boolean;
      warnings: string[];
      matches_counted: number;
      points_system: PointsSystemSummary;
      groups: { group: Nullable<string>; rows: StandingsRow[]; played_counts: number[] }[];
    };

export interface SeasonDetail {
  competition: CompetitionCard;
  season: SeasonSummary;
  stages: { id: number; name: string; type: "league" | "group" | "knockout"; matches: number }[];
  teams: SeasonTeam[];
  standings: Standings;
  knockouts: MatchRow[];
  leaders: Nullable<OverviewPayload["leaderboards"]>;
  fixtures: { available: boolean; reason: string };
  coverage: { status: CoverageStatus; label: string; matches: number; data_levels?: number[] };
  scope?: Scope;
}

export interface Paged<T> {
  total: number;
  items: T[];
  limit: number;
  offset: number;
}

/** A competition a player or team has appeared in, for the profile switcher. */
export interface EntityCompetition {
  id: number;
  slug: string;
  name: string;
  short_name: Nullable<string>;
  gender: Gender;
  type: CompetitionType;
  format: string;
  matches: number;
  first_match: string;
  last_match: string;
}

export interface GlobalSummary {
  competitions: {
    catalogued: number;
    with_data: number;
    women_with_data: number;
    women_catalogued: number;
    by_type: Partial<Record<CompetitionType, { catalogued: number; with_data: number }>>;
  };
  matches: number;
  matches_by_gender: Partial<Record<Gender, number>>;
  deliveries: number;
  players: number;
  teams: number;
  formats: string[];
  first_match: Nullable<string>;
  last_match: Nullable<string>;
  with_data: CompetitionCard[];
  latest_results: MatchRow[];
  /** Leading run-scorer of each of the busiest competitions: search starters. */
  suggestions: { id: string; name: string; competition: string }[];
}
