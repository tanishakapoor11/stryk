import { api, ApiError } from "@/lib/api";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { Section } from "@/components/layout/page-header";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { CompetitionCard } from "@/components/competitions/competition-card";
import { DirectoryFilters } from "@/components/competitions/directory-filters";
import { DIRECTORY_PRESETS, TYPE_LABEL, type DirectoryPreset } from "@/lib/competitions";
import { many, one, type RawParams } from "@/lib/search-params";
import type { CompetitionCard as Card, CompetitionDirectory, CompetitionType } from "@/types";

type CountryRow = { code: string; name: string; competitions: number };

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
  // The full directory groups by type; a preset page is already one type.
  const groups: [string, Card[]][] =
    preset === "all" || preset === "women"
      ? SECTION_ORDER.map((t) => [TYPE_LABEL[t], directory.items.filter((c) => c.type === t)] as [string, Card[]]).filter(
          ([, items]) => items.length,
        )
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
