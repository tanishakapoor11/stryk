import Link from "next/link";
import { ArrowLeft, Search } from "lucide-react";
import { BallStrip } from "@/components/ui/ball-strip";

export const metadata = { title: "Not found" };

/**
 * 404, told in the one notation this product already uses.
 *
 * The strip reads as a wicket off the fourth ball, which is the joke: the page
 * is out. It is decoration built from the site's own vocabulary rather than a
 * stock illustration, and it degrades to a row of coloured dots if anything
 * fails to load.
 */
const OUT_SEQUENCE = [".", ".", ".", "W"];

const PLACES = [
  { href: "/players", label: "Players", detail: "Search every player in the data" },
  { href: "/matchups", label: "Match-ups", detail: "One batter against one bowler" },
  { href: "/teams", label: "Teams", detail: "Squad depth and phase strength" },
  { href: "/auction", label: "Auction", detail: "Build a hypothetical squad" },
];

export default function NotFound() {
  return (
    <div className="relative mx-auto flex min-h-[70vh] max-w-3xl flex-col justify-center px-4 py-16 lg:px-6">
      <div className="animate-fade-in">
        <p className="num font-display text-[5rem] font-bold leading-none tracking-tight text-ink/15 lg:text-[7rem]">
          404
        </p>

        <h1 className="-mt-4 font-display text-2xl font-bold tracking-tight text-ink lg:text-3xl">
          This one&apos;s out
        </h1>
        <p className="mt-3 max-w-lg text-sm leading-relaxed text-ink-muted">
          There is no page at this address. It may have been renamed, or the link may have
          carried a player or team id that is not in the data.
        </p>

        <div className="mt-6 flex items-center gap-3">
          <BallStrip sequence={OUT_SEQUENCE} />
          <span className="text-2xs text-ink-faint">bowled, fourth ball</span>
        </div>

        <div className="mt-8 flex flex-wrap items-center gap-3">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 rounded-full bg-accent px-3.5 py-2 text-xs font-medium text-accent-foreground transition-transform hover:-translate-y-0.5"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
            Back to the overview
          </Link>
          <Link
            href="/players"
            className="inline-flex items-center gap-1.5 rounded-full border border-line-strong px-3.5 py-2 text-xs text-ink-muted transition-colors hover:border-accent/50 hover:text-ink"
          >
            <Search className="h-3.5 w-3.5" aria-hidden />
            Find a player
          </Link>
        </div>

        <nav aria-label="Elsewhere in Stryk" className="mt-10 border-t border-line pt-6">
          <p className="label-xs mb-3">Or try one of these</p>
          <ul className="grid gap-2 sm:grid-cols-2">
            {PLACES.map((place) => (
              <li key={place.href}>
                <Link
                  href={place.href}
                  className="card-interactive group block rounded-lg border border-line bg-surface px-3.5 py-3 hover:border-line-strong"
                >
                  <span className="block font-display text-sm font-semibold text-ink transition-colors group-hover:text-accent">
                    {place.label}
                  </span>
                  <span className="mt-0.5 block text-2xs text-ink-faint">{place.detail}</span>
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </div>
  );
}
