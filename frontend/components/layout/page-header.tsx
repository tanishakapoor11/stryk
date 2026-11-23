import * as React from "react";
import { Breadcrumbs, type Crumb } from "./breadcrumbs";

export function PageHeader({
  title,
  subtitle,
  crumbs,
  meta,
  actions,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  crumbs?: Crumb[];
  meta?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="border-b border-line bg-surface-sunken">
      <div className="mx-auto max-w-[1600px] px-4 py-5 lg:px-6">
        {crumbs ? <Breadcrumbs items={crumbs} /> : null}
        <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-xl font-semibold tracking-tight text-ink lg:text-2xl">{title}</h1>
            {subtitle ? (
              <p className="mt-1 max-w-3xl text-xs leading-relaxed text-ink-muted">{subtitle}</p>
            ) : null}
            {meta ? <div className="mt-2 flex flex-wrap items-center gap-2">{meta}</div> : null}
          </div>
          {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
        </div>
      </div>
    </div>
  );
}

export function Section({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`mx-auto max-w-[1600px] px-4 py-6 lg:px-6 ${className}`}>{children}</div>
  );
}
