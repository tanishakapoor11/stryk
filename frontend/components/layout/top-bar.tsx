"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";
import { Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { GlobalSearch } from "./global-search";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/players", label: "Players" },
  { href: "/compare", label: "Compare" },
  { href: "/matchups", label: "Match-ups" },
  { href: "/teams", label: "Teams" },
  { href: "/auction", label: "Auction" },
];

export function TopBar() {
  const pathname = usePathname();
  const [open, setOpen] = React.useState(false);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

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
          <span className="hidden border-l border-line pl-2.5 text-2xs text-ink-faint lg:inline">
            IPL ball-by-ball
          </span>
        </Link>

        <nav className="ml-4 hidden items-center gap-1 md:flex" aria-label="Primary">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "rounded px-2.5 py-1.5 text-xs transition-colors",
                isActive(item.href)
                  ? "bg-surface-raised text-ink"
                  : "text-ink-muted hover:text-ink",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <GlobalSearch />
          <button
            type="button"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            className="rounded border border-line-strong p-1.5 text-ink-muted md:hidden"
          >
            {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {open ? (
        <nav className="border-t border-line md:hidden" aria-label="Primary mobile">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className={cn(
                "block border-b border-line/60 px-4 py-2.5 text-sm",
                isActive(item.href) ? "bg-surface text-accent" : "text-ink-muted",
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
