"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";
import { ChevronDown, Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { GlobalSearch } from "./global-search";

type NavItem = {
  href: string;
  label: string;
  /** Other paths that count as this section (a competition page under Leagues). */
  match?: string[];
  children?: { href: string; label: string; detail: string }[];
};

/**
 * Discovery first (where cricket is played), then the analysis tools that work
 * inside any of it. Table Lab joins when it exists; a nav item that leads to an
 * empty page would be worse than none.
 */
const NAV: NavItem[] = [
  { href: "/", label: "Home" },
  { href: "/international", label: "International" },
  { href: "/tournaments", label: "Tournaments" },
  { href: "/domestic", label: "Domestic" },
  // A competition page is not highlighted under any hub: an ODI series is not
  // a "league", and the page's breadcrumb already says where it belongs.
  { href: "/leagues", label: "Leagues" },
  { href: "/women", label: "Women's" },
  { href: "/players", label: "Players" },
  { href: "/teams", label: "Teams" },
  {
    href: "/compare",
    label: "Analyse",
    match: ["/compare", "/matchups"],
    children: [
      { href: "/compare", label: "Compare", detail: "Two to four players on an identical sample" },
      { href: "/matchups", label: "Match-ups", detail: "Batter against bowler, ball by ball" },
    ],
  },
  { href: "/auction", label: "Scout" },
];

export function TopBar() {
  const pathname = usePathname();
  const [open, setOpen] = React.useState(false);

  const isActive = (item: NavItem) =>
    item.href === "/"
      ? pathname === "/"
      : [item.href, ...(item.match ?? [])].some((p) => pathname.startsWith(p));

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-canvas/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-[1600px] items-center gap-4 px-4 lg:px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2.5" aria-label="Stryk — home">
          {/* The wordmark is a fixed asset, so next/image buys nothing here and
              a plain img keeps it out of the optimiser. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/brand/wordmark-white.png"
            alt="Stryk"
            width={104}
            height={26}
            className="h-[26px] w-auto"
          />
          <span className="hidden border-l border-line pl-2.5 text-2xs text-ink-faint xl:inline">
            Cricket intelligence
          </span>
        </Link>

        <nav className="ml-2 hidden min-w-0 items-center gap-0.5 lg:flex" aria-label="Primary">
          {NAV.map((item) =>
            item.children ? (
              <div key={item.label} className="group relative">
                <button
                  type="button"
                  aria-haspopup="true"
                  className={cn(
                    "flex items-center gap-0.5 rounded px-2 py-1.5 text-xs transition-colors",
                    isActive(item) ? "bg-surface-raised text-ink" : "text-ink-muted hover:text-ink",
                  )}
                >
                  {item.label}
                  <ChevronDown className="h-3 w-3" aria-hidden />
                </button>
                <div className="invisible absolute left-0 top-full z-50 pt-1 opacity-0 transition-opacity group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100">
                  <ul className="w-64 rounded-xl border border-line-strong bg-surface-raised py-1 shadow-lift">
                    {item.children.map((child) => (
                      <li key={child.href}>
                        <Link href={child.href} className="block px-3 py-2 hover:bg-accent/10">
                          <span className="block text-xs text-ink">{child.label}</span>
                          <span className="block text-2xs text-ink-faint">{child.detail}</span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "whitespace-nowrap rounded px-2 py-1.5 text-xs transition-colors",
                  isActive(item) ? "bg-surface-raised text-ink" : "text-ink-muted hover:text-ink",
                )}
              >
                {item.label}
              </Link>
            ),
          )}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <GlobalSearch />
          <button
            type="button"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            className="rounded border border-line-strong p-1.5 text-ink-muted lg:hidden"
          >
            {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {open ? (
        <nav className="border-t border-line lg:hidden" aria-label="Primary mobile">
          {NAV.flatMap((item): { href: string; label: string }[] => item.children ?? [item]).map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className={cn(
                "block border-b border-line/60 px-4 py-2.5 text-sm",
                pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href))
                  ? "bg-surface text-accent"
                  : "text-ink-muted",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      ) : null}
    </header>
  );
}
