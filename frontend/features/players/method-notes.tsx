import * as React from "react";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

/**
 * Every derived statistic on a page is defined here, in the page, rather than
 * in a separate glossary. A number whose formula is not visible is a number a
 * reader cannot check.
 */
export function MethodNotes({
  metrics,
  qualification,
  notes,
}: {
  metrics: Record<string, { label: string; formula: string; notes?: string }>;
  qualification?: Record<string, number>;
  notes?: React.ReactNode;
}) {
  const entries = Object.entries(metrics ?? {});
  return (
    <Panel>
      <PanelHeader
        title="How these numbers are calculated"
        description="Formulas and qualification thresholds, served by the same API that computes the figures above."
      />
      <PanelBody className="space-y-4">
        {notes ? <div className="text-xs leading-relaxed text-ink-muted">{notes}</div> : null}
        {entries.length ? (
          <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2 xl:grid-cols-3">
            {entries.map(([key, m]) => (
              <div key={key}>
                <dt className="text-xs font-medium text-ink">{m.label}</dt>
                <dd className="num mt-0.5 text-2xs text-accent">{m.formula}</dd>
                {m.notes ? (
                  <dd className="mt-0.5 text-2xs leading-relaxed text-ink-muted">{m.notes}</dd>
                ) : null}
              </div>
            ))}
          </dl>
        ) : null}
        {qualification && Object.keys(qualification).length ? (
          <div>
            <p className="label-xs mb-1.5">Qualification thresholds</p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(qualification).map(([k, v]) => (
                <Badge key={k}>
                  {k.replace(/_/g, " ")}: <span className="num text-ink">{v}</span>
                </Badge>
              ))}
            </div>
          </div>
        ) : null}
      </PanelBody>
    </Panel>
  );
}
