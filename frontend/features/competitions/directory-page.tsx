import { api, ApiError } from "@/lib/api";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { Section } from "@/components/layout/page-header";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { CompetitionCard } from "@/components/competitions/competition-card";
import { DirectoryFilters } from "@/components/competitions/directory-filters";
import { DIRECTORY_PRESETS, TYPE_LABEL, type DirectoryPreset } from "@/lib/competitions";
import { many, one, type RawParams } from "@/lib/search-params";
import { flagRegion, visitorCountry } from "@/lib/geo";
import type { CompetitionCard as Card, CompetitionDirectory, CompetitionType } from "@/types";

type CountryRow = { code: string; name: string; competitions: number };

/** Keeps both halves in the order the API sorted them. */
function partition<T>(items: T[], pick: (item: T) => boolean): [T[], T[]] {
  const yes: T[] = [];
  const no: T[] = [];
  for (const item of items) (pick(item) ? yes : no).push(item);
  return [yes, no];
}

const SECTION_ORDER: CompetitionType[] = [
  "INTERNATIONAL",
  "ICC_TOURNAMENT",
  "FRANCHISE_LEAGUE",
  "DOMESTIC",
  "REGIONAL",
  "OTHER",
];

/**
 * The single competition directory. Every entry point (International,
 * Tournaments, Domestic, Leagues, Women's, All) is this component with a
 * preset, so a new competition appears everywhere it belongs without a page
 * being written for it.
 */
export async function CompetitionDirectoryPage({
  preset,
  searchParams,
}: {
  preset: DirectoryPreset;
  searchParams: RawParams;
}) {
  const config = DIRECTORY_PRESETS[preset];
  const fixed = config.query as { type?: CompetitionType[]; gender?: string };
  const query = {
    q: one(searchParams, "q"),
    type: fixed.type ?? many(searchParams, "type"),
    gender: fixed.gender ?? one(searchParams, "gender"),
    country: one(searchParams, "country"),
    format: one(searchParams, "format"),
    coverage: many(searchParams, "coverage"),
    limit: 200,
  };

  let directory: CompetitionDirectory;
  let countries: CountryRow[];
  try {
    [directory, countries] = await Promise.all([
      api<CompetitionDirectory>("/api/competitions", query),
      api<CountryRow[]>("/api/countries"),
    ]);
  } catch (err) {
    const e = err as ApiError;
    return (
      <Section>
        <ErrorState title="Could not load competitions" detail={e.message} />
      </Section>
    );
  }

  const withData = directory.items.filter((c) => c.coverage.matches > 0).length;

  // Someone opening Domestic almost always wants their own country's cricket,
  // and ours is a directory of 21 of them in which Ranji can sit below the
  // Bob Willis Trophy. So the reader's own country is lifted to the front —
  // lifted, not filtered: everything else keeps its place directly below.
  // A country already chosen in the filters is honoured as-is; an explicit
  // choice outranks a guess about where someone is sitting.
  // The full directory groups by type, which is the point of those pages, so
  // only the single-type presets reorder by country.
  const byType = preset === "all" || preset === "women";
  const home = byType || query.country ? null : visitorCountry();
  // `home` must be checked explicitly: a competition with no country decodes
  // to null too, so a bare equality would quietly gather every international
  // and ICC event into "yours" the moment there is no country to compare.
  const [mine, elsewhere] = home
    ? partition(directory.items, (c) => flagRegion(c.country?.flag) === home)
    : [[] as Card[], directory.items];
  // Nothing of the reader's own, or nothing but it, means there is no order
  // to change — and so nothing to announce.
  const lifted = mine.length > 0 && elsewhere.length > 0;
  const homeLabel = Array.from(new Set(mine.map((c) => c.country?.name)))
    .filter(Boolean)
    .join(" and ");

  const groups: [string, Card[]][] = byType
    ? SECTION_ORDER.map((t) => [TYPE_LABEL[t], directory.items.filter((c) => c.type === t)] as [string, Card[]]).filter(
        ([, items]) => items.length,
      )
    : lifted
      ? [[homeLabel, mine], ["Elsewhere", elsewhere]]
      : [["", directory.items]];

  return (
    <>
      <div className="border-b border-line bg-surface-sunken">
        <div className="mx-auto max-w-[1600px] px-4 pb-7 pt-5 lg:px-6">
          <Breadcrumbs
            items={[
              { label: "Stryk", href: "/" },
              ...(preset === "all" ? [] : [{ label: "Competitions", href: "/competitions" }]),
              { label: config.title },
            ]}
          />
          <p className="label-xs mt-3">{config.eyebrow}</p>
          <h1 className="mt-1 font-display text-3xl font-bold tracking-tight text-ink lg:text-4xl">
            {config.title}
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-muted">
            {directory.total} {directory.total === 1 ? "competition" : "competitions"}, {withData} with
            data in STRYK. Every card says how much of it we actually hold, so a missing record is
            never mistaken for a zero.
            {lifted ? (
              <> {homeLabel} is listed first because that is where you appear to be reading from.</>
            ) : null}
          </p>
          <div className="mt-5">
            <DirectoryFilters
              facets={directory.facets}
              countries={countries.filter((c) => c.competitions > 0)}
              fixed={{ type: Boolean(fixed.type), gender: Boolean(fixed.gender) }}
            />
          </div>
        </div>
      </div>

      <Section className="space-y-8">
        {directory.items.length === 0 ? (
          <EmptyState title="No competitions match these filters" />
        ) : (
          groups.map(([title, items]) => (
            <div key={title || "all"}>
              {title ? (
                <h2 className="font-display text-base font-semibold tracking-tight text-ink">
                  {title}
                  <span className="num ml-2 text-xs font-normal text-ink-faint">{items.length}</span>
                </h2>
              ) : null}
              <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {items.map((c) => (
                  <CompetitionCard key={c.slug} competition={c} />
                ))}
              </div>
            </div>
          ))
        )}
      </Section>
    </>
  );
}
