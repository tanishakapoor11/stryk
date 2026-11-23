import * as React from "react";
import { cn } from "@/lib/utils";
import { Hint } from "./tooltip";

/** Dense KPI cell. Values are mono so columns of figures line up. */
export function Stat({
  label,
  value,
  sub,
  hint,
  tone = "default",
  className,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  hint?: string;
  tone?: "default" | "accent" | "muted";
  className?: string;
}) {
  return (
    <div className={cn("px-4 py-3", className)}>
      <div className="flex items-center gap-1">
        <span className="label-xs">{label}</span>
        {hint ? <Hint text={hint} /> : null}
      </div>
      <div
        className={cn(
          "num mt-1 text-xl font-medium leading-none",
          tone === "accent" && "text-accent",
          tone === "muted" && "text-ink-muted",
        )}
      >
        {value}
      </div>
      {sub ? <div className="mt-1 text-2xs text-ink-faint">{sub}</div> : null}
    </div>
  );
}

export function StatRow({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "grid grid-cols-2 divide-x divide-y divide-line border-line sm:grid-cols-3 lg:grid-cols-6 lg:divide-y-0",
        className,
      )}
      {...props}
    />
  );
}
