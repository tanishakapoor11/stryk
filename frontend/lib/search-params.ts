/**
 * Next.js hands page components `searchParams` as string | string[].
 * These helpers normalise that into the repeatable query shape the API wants,
 * so a URL is the only state container in the app.
 */
export type RawParams = Record<string, string | string[] | undefined>;

export function many(params: RawParams, key: string): string[] {
  const v = params[key];
  if (v === undefined) return [];
  return Array.isArray(v) ? v : [v];
}

export function one(params: RawParams, key: string): string | undefined {
  const v = params[key];
  return Array.isArray(v) ? v[0] : v;
}

export function numbers(params: RawParams, key: string): number[] {
  return many(params, key)
    .map((v) => Number(v))
    .filter((n) => Number.isFinite(n));
}

/** The filter parameters every analytics endpoint understands. */
export function filterQuery(params: RawParams) {
  return {
    season: numbers(params, "season"),
    team: numbers(params, "team"),
    phase: many(params, "phase"),
    chasing: one(params, "chasing"),
    venue: numbers(params, "venue"),
    innings: one(params, "innings"),
    date_from: one(params, "date_from"),
    date_to: one(params, "date_to"),
  };
}

export function describeFilters(params: RawParams): string {
  const seasons = numbers(params, "season");
  const phases = many(params, "phase");
  const chasing = one(params, "chasing");
  const bits: string[] = [];
  if (seasons.length) bits.push(seasons.length === 1 ? `${seasons[0]}` : `${seasons.length} seasons`);
  else bits.push("all seasons");
  if (phases.length) bits.push(phases.join(" + "));
  if (chasing === "true") bits.push("chasing only");
  if (chasing === "false") bits.push("batting first only");
  return bits.join(" · ");
}
