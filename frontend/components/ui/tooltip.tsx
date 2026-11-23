"use client";
import * as React from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { Info } from "lucide-react";
import { cn } from "@/lib/utils";

export const TooltipProvider = TooltipPrimitive.Provider;

/** Small "what does this metric mean" affordance used across every table. */
export function Hint({ text, className }: { text: string; className?: string }) {
  return (
    <TooltipPrimitive.Root delayDuration={120}>
      <TooltipPrimitive.Trigger asChild>
        <button
          type="button"
          aria-label={text}
          className={cn("text-ink-faint transition-colors hover:text-accent", className)}
        >
          <Info className="h-3 w-3" aria-hidden />
        </button>
      </TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          sideOffset={6}
          className="z-50 max-w-xs animate-fade-in rounded border border-line-strong bg-surface-raised px-2.5 py-2 text-xs leading-relaxed text-ink shadow-raise"
        >
          {text}
          <TooltipPrimitive.Arrow className="fill-line-strong" />
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}
