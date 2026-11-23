import * as React from "react";
import { cn } from "@/lib/utils";

const tones = {
  default: "border-line-strong text-ink-muted",
  accent: "border-accent/40 bg-accent/10 text-accent",
  warn: "border-signal-warn/40 bg-signal-warn/10 text-signal-warn",
  danger: "border-signal-down/40 bg-signal-down/10 text-signal-down",
  info: "border-signal-info/40 bg-signal-info/10 text-signal-info",
} as const;

export function Badge({
  tone = "default",
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: keyof typeof tones }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded border px-1.5 py-0.5 text-2xs",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
