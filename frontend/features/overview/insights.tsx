import Link from "next/link";
import { Panel, PanelHeader } from "@/components/ui/card";
import type { Insight } from "@/types";

/**
 * Insights are computed from the loaded deliveries on every request — there
 * are no stored narratives. Each one states the sample it rests on, because a
 * finding without its denominator is a slogan.
 *
 * Laid out as a column rather than a strip: these are sentences to read, and a
 * reader gets further down a list than across a row of equal cards.
 */
export function InsightsPanel({ insights }: { insights: Insight[] }) {
  if (!insights.length) return null;
  return (
    <div>
      <h2 className="font-display text-base font-semibold tracking-tight text-ink">
        What stands out today
      </h2>
      <p className="mt-1 text-2xs leading-relaxed text-ink-faint">
        Recomputed from the ball-by-ball data on every visit.
      </p>
      <ul className="mt-3.5 space-y-2.5">
        {insights.slice(0, 4).map((insight) => (
          <li
            key={insight.title}
            className="rounded-lg border border-line bg-surface px-3.5 py-3 transition-colors hover:border-line-strong"
          >
            <div className="flex items-start justify-between gap-3">
              <h3 className="text-xs font-medium text-ink">{insight.title}</h3>
              {insight.metric ? (
                <span className="num shrink-0 rounded-full bg-accent/10 px-2 py-0.5 text-2xs text-accent">
                  {insight.metric}
                </span>
              ) : null}
            </div>
            <p className="mt-1.5 text-xs leading-relaxed text-ink-muted">
              {insight.link ? (
                <Link href={insight.link} className="decoration-accent/40 hover:underline">
                  {insight.detail}
                </Link>
              ) : (
                insight.detail
              )}
            </p>
            {insight.context ? (
              <p className="mt-1.5 text-2xs text-ink-faint">{insight.context}</p>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
