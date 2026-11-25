import { Panel } from "@/components/ui/card";
import type { ScopeCoverage } from "@/types";

/**
 * Stands in for the cumulative lists - most runs, most wickets - on a
 * competition STRYK does not hold in full.
 *
 * Cricsheet publishes deliveries, and the earliest are from 2001. For a
 * competition older than that, a "most runs" list is not the competition's
 * all-time order: it is whoever has played most of their career since the
 * data starts. Test cricket is the clearest case - Tendulkar scored 15,921
 * Test runs, of which 6,416 fall inside the ball-by-ball record, so a list
 * built from deliveries puts players who debuted later above him. Everything
 * else on the page is a rate or a per-innings figure and stays true; only the
 * career totals are withheld.
 */
export function PartialCoverageNote({
  name,
  coverage,
}: {
  name: string;
  coverage: ScopeCoverage;
}) {
  const from = coverage.indexed_from;
  const began = coverage.begins;
  return (
    <Panel className="p-4">
      <h3 className="font-display text-sm font-semibold tracking-tight text-ink">
        Career totals are not shown for the {name}
      </h3>
      <p className="mt-1.5 max-w-2xl text-xs leading-relaxed text-ink-muted">
        {began ? (
          <>
            The {name} dates from <span className="num">{began}</span>, and ball-by-ball data
            exists only from <span className="num">{from}</span>.
          </>
        ) : (
          <>
            Ball-by-ball data for the {name} begins in <span className="num">{from}</span>, after
            the competition itself.
          </>
        )}{" "}
        A most-runs list built from these deliveries would rank players by how much of their
        career happens to fall inside the record, not by how many runs they scored, so it is left
        out rather than shown with a caveat. Rates, per-innings records and everything below are
        computed from the same deliveries and are unaffected.
      </p>
    </Panel>
  );
}
