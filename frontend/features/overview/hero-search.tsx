"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Loader2, Search, Sparkles } from "lucide-react";
import { PlayerAvatar } from "@/components/ui/player-identity";
import { cn } from "@/lib/utils";
import type { SearchHit } from "@/types";

/**
 * The front door.
 *
 * Looking up a player is what most people come here to do, so the search box
 * is the page rather than a control in the corner of it. The examples below it
 * are there to teach the one thing that is not obvious: any form of a name
 * works, including just a first name.
 */
export function HeroSearch({
  suggestions,
}: {
  suggestions: Array<{ id: string; name: string; team?: string | null }>;
}) {
  const router = useRouter();
  const [query, setQuery] = React.useState("");
  const [hits, setHits] = React.useState<SearchHit[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [cursor, setCursor] = React.useState(0);
  const boxRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setHits([]);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  React.useEffect(() => {
    if (query.trim().length < 2) {
      setHits([]);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`, {
          signal: controller.signal,
        });
        if (res.ok) {
          setHits(await res.json());
          setCursor(0);
        }
      } catch {
        /* aborted */
      } finally {
        setLoading(false);
      }
    }, 160);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  return (
    <div ref={boxRef} className="relative">
      <label htmlFor="hero-search" className="sr-only">
        Search players and teams
      </label>
      <div className="flex items-center gap-3 rounded-xl border border-line-strong bg-surface-raised px-4 py-3.5 shadow-lift transition-colors field-shell focus-within:border-accent/60">
        {loading ? (
          <Loader2 className="h-5 w-5 shrink-0 animate-spin text-accent" aria-hidden />
        ) : (
          <Search className="h-5 w-5 shrink-0 text-ink-faint" aria-hidden />
        )}
        <input
          id="hero-search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") setCursor((c) => Math.min(c + 1, hits.length - 1));
            if (e.key === "ArrowUp") setCursor((c) => Math.max(c - 1, 0));
            if (e.key === "Enter" && hits[cursor]) router.push(hits[cursor].href);
            if (e.key === "Escape") setHits([]);
          }}
          placeholder="Search any player or team"
          autoComplete="off"
          className="w-full bg-transparent text-base text-ink outline-none placeholder:text-ink-faint"
        />
      </div>

      {hits.length > 0 ? (
        <ul
          role="listbox"
          aria-label="Search results"
          className="absolute left-0 right-0 top-full z-50 mt-2 max-h-96 animate-fade-in overflow-auto rounded-xl border border-line-strong bg-surface-raised py-1 shadow-lift"
        >
          {hits.map((hit, i) => (
            <li key={`${hit.type}-${hit.id}`}>
              <Link
                href={hit.href}
                onMouseEnter={() => setCursor(i)}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 text-left",
                  i === cursor ? "bg-accent/10" : "",
                )}
              >
                {hit.type === "player" ? (
                  <PlayerAvatar name={hit.name} size="sm" />
                ) : (
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-line text-[0.625rem] text-ink-muted">
                    {hit.secondary ?? "T"}
                  </span>
                )}
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-ink">{hit.name}</span>
                  {hit.secondary && hit.type === "player" ? (
                    <span className="block truncate text-2xs text-ink-faint">
                      listed as {hit.secondary}
                    </span>
                  ) : null}
                </span>
                {hit.detail ? (
                  <span className="num shrink-0 text-2xs text-ink-faint">{hit.detail}</span>
                ) : null}
              </Link>
            </li>
          ))}
        </ul>
      ) : null}

      {query.trim().length >= 2 && !loading && hits.length === 0 ? (
        <p className="absolute left-0 right-0 top-full mt-2 rounded-xl border border-line bg-surface-raised px-4 py-3 text-sm text-ink-muted">
          Nothing matches &ldquo;{query}&rdquo;. Try a surname on its own.
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {/* The box above matches names. A question in prose belongs on /ask,
            which costs a model call and so waits for Enter rather than firing
            on every keystroke. */}
        <Link
          href="/ask"
          className="inline-flex items-center gap-1.5 rounded-full border border-accent/40 bg-accent/5 px-2.5 py-1 text-xs text-ink-muted transition-colors hover:border-accent/70 hover:text-ink"
        >
          <Sparkles className="h-3 w-3 text-accent" aria-hidden />
          Ask a question instead
        </Link>
        <span className="text-xs text-ink-faint">or try</span>
        {suggestions.map((s) => (
          <Link
            key={s.id}
            href={`/players/${s.id}`}
            className="inline-flex items-center gap-1.5 rounded-full border border-line-strong bg-surface px-2.5 py-1 text-xs text-ink-muted transition-colors hover:border-accent/50 hover:text-ink"
          >
            <PlayerAvatar name={s.name} team={s.team} size="sm" className="!h-4 !w-4 !text-[0.5rem]" />
            {s.name}
          </Link>
        ))}
      </div>
    </div>
  );
}
