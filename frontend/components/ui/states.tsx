import * as React from "react";
import { AlertTriangle, Database, SearchX } from "lucide-react";
import { cn } from "@/lib/utils";

export function EmptyState({
  title = "Nothing to show",
  detail,
  icon: Icon = SearchX,
  className,
}: {
  title?: string;
  detail?: React.ReactNode;
  icon?: React.ElementType;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center gap-2 px-6 py-12 text-center", className)}>
      <Icon className="h-5 w-5 text-ink-faint" aria-hidden />
      <p className="text-sm text-ink">{title}</p>
      {detail ? <p className="max-w-md text-xs leading-relaxed text-ink-muted">{detail}</p> : null}
    </div>
  );
}

export function ErrorState({ title, detail }: { title: string; detail?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 border border-signal-down/30 bg-signal-down/5 px-6 py-10 text-center">
      <AlertTriangle className="h-5 w-5 text-signal-down" aria-hidden />
      <p className="text-sm text-ink">{title}</p>
      {detail ? <p className="max-w-lg text-xs leading-relaxed text-ink-muted">{detail}</p> : null}
    </div>
  );
}

export function NoDataState() {
  return (
    <ErrorState
      title="No data has been ingested yet"
      detail={
        <>
          Run <code className="text-accent">python scripts/fetch_cricsheet.py</code> then{" "}
          <code className="text-accent">python scripts/ingest.py</code> from the project root,
          then reload this page.
        </>
      }
    />
  );
}

export { Database };
