"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Search, X } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Debounced, URL-backed text filter. The value lives in the query string so
 * the result set is shareable and the server component does the filtering.
 */
export function SearchBox({
  param = "q",
  placeholder = "Search players…",
  className,
}: {
  param?: string;
  placeholder?: string;
  className?: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [value, setValue] = React.useState(params.get(param) ?? "");
  const [pending, startTransition] = React.useTransition();

  // Keep the box in sync when the URL changes from elsewhere (back button).
  React.useEffect(() => {
    setValue(params.get(param) ?? "");
  }, [params, param]);

  React.useEffect(() => {
    const current = params.get(param) ?? "";
    if (value === current) return;
    const t = setTimeout(() => {
      const sp = new URLSearchParams(Array.from(params.entries()));
      if (value) sp.set(param, value);
      else sp.delete(param);
      sp.delete("offset");
      startTransition(() => router.push(`${pathname}?${sp.toString()}`, { scroll: false }));
    }, 280);
    return () => clearTimeout(t);
  }, [value, params, param, pathname, router]);

  return (
    <div className={cn("relative", className)}>
      <Search
        className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint"
        aria-hidden
      />
      <input
        type="search"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className={cn(
          "h-8 w-full rounded border border-line-strong bg-surface-raised pl-7 pr-7 text-xs text-ink outline-none transition-colors placeholder:text-ink-faint focus:border-accent/60",
          pending && "opacity-70",
        )}
      />
      {value ? (
        <button
          type="button"
          onClick={() => setValue("")}
          aria-label="Clear search"
          className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-faint hover:text-ink"
        >
          <X className="h-3.5 w-3.5" aria-hidden />
        </button>
      ) : null}
    </div>
  );
}
