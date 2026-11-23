export function SiteFooter() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-1 px-4 py-5 text-2xs text-ink-faint lg:flex-row lg:items-center lg:justify-between lg:px-6">
        <p className="flex items-center gap-2.5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/brand/mark-white.png"
            alt=""
            width={22}
            height={18}
            className="h-[18px] w-auto opacity-70"
          />
          <span>
          Stryk — cricket intelligence built on{" "}
          <a
            href="https://cricsheet.org/"
            target="_blank"
            rel="noreferrer"
            className="text-ink-muted underline-offset-2 hover:text-accent hover:underline"
          >
            Cricsheet
          </a>{" "}
          ball-by-ball data. Statistics are computed from deliveries, not scraped scorecards.
          </span>
        </p>
        <p>Phases: powerplay 1–6 · middle 7–15 · death 16–20</p>
      </div>
    </footer>
  );
}
