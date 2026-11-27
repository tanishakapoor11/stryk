"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Search, Loader2 } from "lucide-react";
import { PlayerAvatar } from "@/components/ui/player-identity";
import type { SearchHit } from "@/types";

/** Global search over players, teams and competitions. Debounced, keyboard driven. */
export function GlobalSearch() {
  const router = useRouter();
  const [query, setQuery] = React.useState("");
  const [hits, setHits] = React.useState<SearchHit[]>([]);
  const [open, setOpen] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [cursor, setCursor] = React.useState(0);
  const boxRef = React.useRef<HTMLDivElement>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  React.useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
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
          setOpen(true);
        }
      } catch {
        /* aborted */
      } finally {
        setLoading(false);
      }
    }, 180);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  const go = (hit: SearchHit) => {
    setOpen(false);
    setQuery("");
    router.push(hit.href);
  };

  return (
    <div ref={boxRef} className="relative">
      <div className="flex items-center gap-2 rounded border border-line-strong bg-surface px-2 py-1.5 field-shell focus-within:border-accent/50">
        {loading ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-ink-faint" aria-hidden />
        ) : (
          <Search className="h-3.5 w-3.5 text-ink-faint" aria-hidden />
        )}
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => hits.length && setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") setCursor((c) => Math.min(c + 1, hits.length - 1));
            if (e.key === "ArrowUp") setCursor((c) => Math.max(c - 1, 0));
            if (e.key === "Enter" && hits[cursor]) go(hits[cursor]);
            if (e.key === "Escape") setOpen(false);
          }}
          placeholder="Search players, teams, competitions"
          aria-label="Search players, teams and competitions"
          className="w-32 bg-transparent text-xs text-ink outline-none placeholder:text-ink-faint sm:w-56 lg:w-32 xl:w-56"
        />
        <kbd className="hidden rounded border border-line px-1 text-2xs text-ink-faint sm:inline">
          ⌘K
        </kbd>
      </div>

      {open && hits.length > 0 ? (
        <ul
          role="listbox"
          className="absolute right-0 top-full z-50 mt-1.5 max-h-80 w-80 animate-fade-in overflow-auto rounded-xl border border-line-strong bg-surface-raised py-1 shadow-lift"
        >
          {hits.map((hit, i) => (
            <li key={`${hit.type}-${hit.id}`}>
              <button
                type="button"
                onMouseEnter={() => setCursor(i)}
                onClick={() => go(hit)}
                className={`flex w-full items-center gap-2.5 px-3 py-2 text-left ${
                  i === cursor ? "bg-accent/10" : ""
                }`}
              >
                {hit.type === "player" ? <PlayerAvatar name={hit.name} size="sm" /> : null}
                {hit.type === "competition" || hit.type === "season" ? (
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded border border-line-strong text-[9px] text-ink-muted">
                    {hit.type === "season" ? "YR" : "CMP"}
                  </span>
                ) : null}
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-xs font-medium text-ink">{hit.name}</span>
                  {hit.secondary && hit.type === "player" ? (
                    <span className="block truncate text-2xs text-ink-faint">
                      listed as {hit.secondary}
                    </span>
                  ) : null}
                </span>
                {hit.detail ? (
                  <span className="num shrink-0 text-2xs text-ink-faint">{hit.detail}</span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {open && !loading && query.length >= 2 && hits.length === 0 ? (
        <div className="absolute right-0 top-full z-50 mt-1 w-72 border border-line-strong bg-surface-raised px-3 py-3 text-xs text-ink-muted">
          No players, teams or competitions match “{query}”.
        </div>
      ) : null}
    </div>
  );
}
