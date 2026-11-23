"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Filter, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { SeasonMeta, TeamSummary } from "@/types";

/**
 * The shared filter surface.
 *
 * Every filter is written into the URL query string, so any view in Stryk is
 * a shareable link and the back button behaves. The server components read
 * the same parameter names and forward them to the API unchanged.
 */
export interface FilterBarProps {
  seasons: SeasonMeta[];
  teams?: TeamSummary[];
  show?: Array<"season" | "team" | "phase" | "innings">;
  className?: string;
}

const PHASES = [
  { value: "powerplay", label: "Powerplay", hint: "Overs 1–6" },
  { value: "middle", label: "Middle", hint: "Overs 7–15" },
  { value: "death", label: "Death", hint: "Overs 16–20" },
];

const INNINGS = [
  { value: "false", label: "Batting first" },
  { value: "true", label: "Chasing" },
];

export function FilterBar({
  seasons,
  teams,
  show = ["season", "phase", "innings"],
  className,
}: FilterBarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [pending, startTransition] = React.useTransition();

  const selectedSeasons = params.getAll("season");
  const selectedPhases = params.getAll("phase");
  const selectedTeams = params.getAll("team");
  const chasing = params.get("chasing");

  const update = (mutate: (sp: URLSearchParams) => void) => {
    const sp = new URLSearchParams(Array.from(params.entries()));
    mutate(sp);
    sp.delete("offset");
    startTransition(() => router.push(`${pathname}?${sp.toString()}`, { scroll: false }));
  };

  const toggleMulti = (key: string, value: string) =>
    update((sp) => {
      const current = sp.getAll(key);
      sp.delete(key);
      const next = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value];
      next.forEach((v) => sp.append(key, v));
    });

  const setSingle = (key: string, value: string | null) =>
    update((sp) => (value === null ? sp.delete(key) : sp.set(key, value)));

  const activeCount =
    selectedSeasons.length + selectedPhases.length + selectedTeams.length + (chasing ? 1 : 0);

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line bg-surface px-4 py-2.5",
        pending && "opacity-60",
        className,
      )}
    >
      <span className="flex items-center gap-1.5 text-ink-faint">
        <Filter className="h-3.5 w-3.5" aria-hidden />
        <span className="label-xs">Filters</span>
      </span>

      {show.includes("season") ? (
        <Group label="Season">
          <div className="scrollbar-thin flex max-w-full gap-1 overflow-x-auto pb-0.5">
            {seasons.map((s) => (
              <Chip
                key={s.season}
                active={selectedSeasons.includes(String(s.season))}
                onClick={() => toggleMulti("season", String(s.season))}
                title={`${s.matches} matches`}
              >
                {s.season}
              </Chip>
            ))}
          </div>
        </Group>
      ) : null}

      {show.includes("team") && teams ? (
        <Group label="Team">
          <select
            value={selectedTeams[0] ?? ""}
            onChange={(e) => setSingle("team", e.target.value || null)}
            className="h-7 rounded border border-line-strong bg-surface-raised px-2 text-xs text-ink outline-none"
          >
            <option value="">All teams</option>
            {teams.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </Group>
      ) : null}

      {show.includes("phase") ? (
        <Group label="Phase">
          {PHASES.map((p) => (
            <Chip
              key={p.value}
              active={selectedPhases.includes(p.value)}
              onClick={() => toggleMulti("phase", p.value)}
              title={p.hint}
            >
              {p.label}
            </Chip>
          ))}
        </Group>
      ) : null}

      {show.includes("innings") ? (
        <Group label="Innings">
          {INNINGS.map((i) => (
            <Chip
              key={i.value}
              active={chasing === i.value}
              onClick={() => setSingle("chasing", chasing === i.value ? null : i.value)}
            >
              {i.label}
            </Chip>
          ))}
        </Group>
      ) : null}

      {activeCount > 0 ? (
        <button
          type="button"
          onClick={() => startTransition(() => router.push(pathname, { scroll: false }))}
          className="ml-auto flex items-center gap-1 text-2xs text-ink-faint transition-colors hover:text-signal-down"
        >
          <X className="h-3 w-3" aria-hidden />
          Clear {activeCount}
        </button>
      ) : null}
    </div>
  );
}

function Group({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex min-w-0 items-center gap-1.5">
      <span className="label-xs shrink-0">{label}</span>
      <div className="flex min-w-0 items-center gap-1">{children}</div>
    </div>
  );
}

function Chip({
  active,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={cn(
        "shrink-0 rounded-full border px-2 py-0.5 text-2xs transition-colors",
        active
          ? "border-accent/60 bg-accent/15 text-accent"
          : "border-line-strong text-ink-muted hover:border-accent/40 hover:text-ink",
      )}
      {...props}
    >
      {children}
    </button>
  );
}
