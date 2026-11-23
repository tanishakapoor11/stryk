"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Loader2, Plus, Search, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { SearchHit } from "@/types";

/**
 * Typeahead that writes player ids into the URL.
 *
 * `mode: "append"` is the comparison case (several players under one key);
 * `mode: "set"` is the match-up case (one batter, one bowler). Either way the
 * selection is a query parameter, so a comparison is a shareable link.
 */
export function PlayerPicker({
  param,
  mode = "append",
  label,
  placeholder = "Add a player…",
  max = 4,
  className,
}: {
  param: string;
  mode?: "append" | "set";
  label?: string;
  placeholder?: string;
  max?: number;
  className?: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [query, setQuery] = React.useState("");
  const [hits, setHits] = React.useState<SearchHit[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [open, setOpen] = React.useState(false);
  const boxRef = React.useRef<HTMLDivElement>(null);

  const selected = params.getAll(param);
  const full = mode === "append" && selected.length >= max;

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
          const all: SearchHit[] = await res.json();
          setHits(all.filter((h) => h.type === "player" && !selected.includes(String(h.id))));
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
    // `selected` is derived from params; re-filtering on every keystroke is enough.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  const add = (id: string) => {
    const sp = new URLSearchParams(Array.from(params.entries()));
    if (mode === "set") sp.set(param, id);
    else if (!sp.getAll(param).includes(id)) sp.append(param, id);
    setQuery("");
    setHits([]);
    setOpen(false);
    router.push(`${pathname}?${sp.toString()}`, { scroll: false });
  };

  return (
    <div ref={boxRef} className={cn("relative", className)}>
      {label ? <span className="label-xs mb-1 block">{label}</span> : null}
      <div
        className={cn(
          "flex items-center gap-2 rounded border border-line-strong bg-surface-raised px-2 py-1.5 focus-within:border-accent/60",
          full && "opacity-50",
        )}
      >
        {loading ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-ink-faint" aria-hidden />
        ) : (
          <Search className="h-3.5 w-3.5 text-ink-faint" aria-hidden />
        )}
        <input
          value={query}
          disabled={full}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => hits.length && setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && hits[0]) add(String(hits[0].id));
            if (e.key === "Escape") setOpen(false);
          }}
          placeholder={full ? `Maximum ${max} selected` : placeholder}
          aria-label={label ?? placeholder}
          className="w-full bg-transparent text-xs text-ink outline-none placeholder:text-ink-faint"
        />
      </div>
      {open && hits.length ? (
        <ul
          role="listbox"
          className="absolute left-0 top-full z-50 mt-1 max-h-72 w-full min-w-[220px] animate-fade-in overflow-auto border border-line-strong bg-surface-raised shadow-raise"
        >
          {hits.map((h) => (
            <li key={h.id}>
              <button
                type="button"
                onClick={() => add(String(h.id))}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-ink-muted hover:bg-accent/10 hover:text-ink"
              >
                <Plus className="h-3 w-3 shrink-0 text-ink-faint" aria-hidden />
                <span className="truncate">{h.name}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/** Removable chip for an already-selected player. */
export function SelectedChip({
  param,
  id,
  name,
  color,
}: {
  param: string;
  id: string;
  name: string;
  color?: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const remove = () => {
    const sp = new URLSearchParams(Array.from(params.entries()));
    const rest = sp.getAll(param).filter((v) => v !== id);
    sp.delete(param);
    rest.forEach((v) => sp.append(param, v));
    router.push(`${pathname}?${sp.toString()}`, { scroll: false });
  };

  return (
    <span className="inline-flex items-center gap-1.5 rounded border border-line-strong bg-surface-raised px-2 py-1 text-xs text-ink">
      {color ? (
        <span className="h-2 w-2 shrink-0 rounded-sm" style={{ background: color }} aria-hidden />
      ) : null}
      {name}
      <button
        type="button"
        onClick={remove}
        aria-label={`Remove ${name}`}
        className="text-ink-faint transition-colors hover:text-signal-down"
      >
        <X className="h-3 w-3" aria-hidden />
      </button>
    </span>
  );
}
