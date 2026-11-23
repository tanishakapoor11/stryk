import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * A faint seam-and-stumps motif for large empty areas.
 *
 * Decoration earns its place here by being the subject's own vocabulary: the
 * curve is a ball's seam and the uprights are stumps. It sits at very low
 * contrast behind content and is hidden from assistive technology, so it adds
 * atmosphere without competing with a single figure on the page.
 */
export function PitchMotif({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 400 300"
      aria-hidden
      className={cn("pointer-events-none select-none", className)}
      fill="none"
    >
      {/* Seam arcs */}
      <path
        d="M-20 250 C 80 150, 200 120, 420 60"
        stroke="currentColor"
        strokeWidth="1"
        strokeOpacity="0.5"
      />
      <path
        d="M-20 268 C 80 168, 200 138, 420 78"
        stroke="currentColor"
        strokeWidth="1"
        strokeDasharray="5 7"
        strokeOpacity="0.35"
      />
      {/* Stumps */}
      <g stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.4">
        <path d="M300 96 V156" />
        <path d="M312 94 V154" />
        <path d="M324 96 V156" />
        <path d="M298 98 H326" />
      </g>
      {/* Ball */}
      <circle cx="96" cy="196" r="13" stroke="currentColor" strokeOpacity="0.45" />
      <path d="M85 191 C 92 196, 100 196, 107 191" stroke="currentColor" strokeOpacity="0.3" />
    </svg>
  );
}
