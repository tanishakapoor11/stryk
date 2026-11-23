"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Search, X } from "lucide-react";
import { GENDER_LABEL, TYPE_LABEL } from "@/lib/competitions";
import type { CompetitionDirectory, CompetitionType, Gender } from "@/types";

const COVERAGE_OPTIONS: Record<string, string> = {
  ball_by_ball: "Ball-by-ball",
  scorecard: "Scorecards",
  results: "Results only",
  not_ingested: "Not yet imported",
  unavailable: "No source",
};

/**
 * Directory filters. State lives in the URL (as everywhere in STRYK), so a
 * filtered directory is a shareable link. Filters a preset already fixes
 * (the women's hub fixes gender) are not offered.
 */
export function DirectoryFilters({
  facets,
  countries,
  fixed,
}: {
  facets: CompetitionDirectory["facets"];
  countries: { code: string; name: string }[];
  fixed: { type?: boolean; gender?: boolean };
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [q, setQ] = React.useState(params.get("q") ?? "");

  const set = React.useCallback(
    (key: string, value: string | null) => {
      const next = new URLSearchParams(params.toString());
      if (value) next.set(key, value);
      else next.delete(key);
      router.replace(`${pathname}${next.toString() ? `?${next}` : ""}`, { scroll: false });
    },
    [params, pathname, router],
  );

  React.useEffect(() => {
    const t = setTimeout(() => {
      if ((params.get("q") ?? "") !== q) set("q", q.trim() || null);
    }, 250);
    return () => clearTimeout(t);
  }, [q, params, set]);

  const select = (
    key: string,
    label: string,
    options: [string, string][],
  ) => (
    <label className="flex items-center gap-1.5 text-2xs text-ink-faint">
      <span className="sr-only sm:not-sr-only">{label}</span>
      <select
        value={params.get(key) ?? ""}
        onChange={(e) => set(key, e.target.value || null)}
        className="rounded border border-line-strong bg-surface px-2 py-1.5 text-xs text-ink focus:border-accent/50 focus:outline-none"
        aria-label={label}
      >
        <option value="">All</option>
        {options.map(([value, text]) => (
          <option key={value} value={value}>
            {text}
          </option>
        ))}
      </select>
    </label>
  );

  const active = ["q", "type", "gender", "country", "format", "coverage"].some((k) => params.get(k));

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex min-w-[220px] flex-1 items-center gap-2 rounded border border-line-strong bg-surface px-2 py-1.5 focus-within:border-accent/50 sm:max-w-xs">
        <Search className="h-3.5 w-3.5 text-ink-faint" aria-hidden />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search competitions"
          aria-label="Search competitions"
          className="w-full bg-transparent text-xs text-ink outline-none placeholder:text-ink-faint"
        />
      </div>
      {!fixed.type
        ? select("type", "Type", Object.keys(facets.type).map((t) => [t, TYPE_LABEL[t as CompetitionType] ?? t]))
        : null}
      {!fixed.gender
        ? select("gender", "Gender", Object.keys(facets.gender).map((g) => [g, GENDER_LABEL[g as Gender] ?? g]))
        : null}
      {select("country", "Country", countries.map((c) => [c.code, c.name]))}
      {select("format", "Format", Object.keys(facets.format).map((f) => [f, f]))}
      {select(
        "coverage",
        "Data",
        Object.keys(COVERAGE_OPTIONS)
          .filter((k) => facets.coverage[k])
          .map((k) => [k, COVERAGE_OPTIONS[k]]),
      )}
      {active ? (
        <button
          type="button"
          onClick={() => {
            setQ("");
            router.replace(pathname, { scroll: false });
          }}
          className="flex items-center gap-1 text-2xs text-ink-muted hover:text-accent"
        >
          <X className="h-3 w-3" aria-hidden /> Clear
        </button>
      ) : null}
    </div>
  );
}
