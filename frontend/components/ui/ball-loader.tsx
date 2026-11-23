"use client";

import * as React from "react";
import dynamic from "next/dynamic";
import { cn } from "@/lib/utils";

/**
 * The loading state: a cricket ball bouncing on its seam.
 *
 * Pure CSS by default, and deliberately so.
 *
 * This started as a Lottie. Two problems killed it as the default. It could
 * not animate until a JSON fetch and a dynamically imported player had both
 * landed, which on a screen that lives for under a second meant a frozen
 * circle was all anyone saw. And its playback could not be verified here at
 * all: lottie-web drives itself from requestAnimationFrame, which is starved
 * under headless Chrome, so the animation advanced one frame in 1.5 seconds
 * on the test rig.
 *
 * CSS keyframes have neither problem. They animate on the first paint, need no
 * runtime, cannot fail to load, and are driven by the compositor rather than a
 * JavaScript timer. A loading indicator is the one component that must never
 * depend on something else loading first.
 *
 * The Lottie path is kept behind `lottie`, for dropping in a stock animation -
 * replace public/brand/ball-loader.json and pass the prop. It is opt-in
 * because its failure mode is a motionless loader.
 */
const Lottie = dynamic(() => import("lottie-react"), { ssr: false });

/**
 * A cricket ball, not a circle with a line through it: the seam curves across
 * the face and carries its stitches, which is what makes it read as a ball
 * rather than a loading dot.
 */
function CricketBall({ className }: { className?: string }) {
  // One curve, drawn three times: two thin rails and a thick dashed stroke
  // between them. Dashes follow the path, so the stitching curves with the
  // seam instead of being plotted along a straight line, which is what made an
  // earlier version look like scratches across the ball.
  const seam = "M24 22 C 42 40, 58 56, 76 78";
  const railA = "M19 27 C 37 45, 53 61, 71 83";
  const railB = "M29 17 C 47 35, 63 51, 81 73";
  return (
    <svg viewBox="0 0 100 100" className={cn("h-full w-full", className)} aria-hidden>
      <defs>
        <radialGradient id="ball-sheen" cx="34%" cy="28%" r="78%">
          <stop offset="0%" stopColor="#FF9256" />
          <stop offset="45%" stopColor="#FC5200" />
          <stop offset="100%" stopColor="#B33800" />
        </radialGradient>
      </defs>

      <circle cx="50" cy="50" r="42" fill="url(#ball-sheen)" />

      <g fill="none" strokeLinecap="round">
        <path d={railA} stroke="#FFFFFF" strokeWidth="1.6" opacity="0.75" />
        <path d={railB} stroke="#FFFFFF" strokeWidth="1.6" opacity="0.75" />
        <path
          d={seam}
          stroke="#FFFFFF"
          strokeWidth="8"
          strokeDasharray="2.4 6"
          opacity="0.95"
        />
      </g>

      {/* A soft terminator keeps it reading as a sphere rather than a disc. */}
      <circle cx="50" cy="50" r="42" fill="url(#ball-shade)" />
      <defs>
        <radialGradient id="ball-shade" cx="68%" cy="74%" r="62%">
          <stop offset="0%" stopColor="#000000" stopOpacity="0.28" />
          <stop offset="100%" stopColor="#000000" stopOpacity="0" />
        </radialGradient>
      </defs>
    </svg>
  );
}

/** The always-on loader: three nested transforms, no JavaScript. */
function BouncingBall({ size }: { size: number }) {
  const drop = Math.round(size * 0.55);
  return (
    <div className="relative" style={{ width: size, height: size + drop + 14 }}>
      <div
        className="absolute left-0 top-0 animate-ball-fall"
        style={{ width: size, height: size, ["--drop" as string]: `${drop}px` }}
      >
        <div className="h-full w-full origin-bottom animate-ball-squash">
          <div className="h-full w-full animate-ball-spin">
            <CricketBall />
          </div>
        </div>
      </div>
      <div
        className="absolute left-1/2 animate-ball-shadow rounded-[50%] bg-black"
        style={{
          width: size * 0.78,
          height: Math.max(6, size * 0.1),
          top: size + drop + 2,
          marginLeft: -(size * 0.39),
        }}
      />
    </div>
  );
}

export function BallLoader({
  label = "Loading",
  size = 96,
  className,
  lottie = false,
}: {
  label?: string;
  size?: number;
  className?: string;
  /** Opt in to the Lottie in public/brand/ball-loader.json. */
  lottie?: boolean;
}) {
  const [animationData, setAnimationData] = React.useState<object | null>(null);
  const [reduced, setReduced] = React.useState(false);

  React.useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReduced(query.matches);
    sync();
    query.addEventListener("change", sync);
    return () => query.removeEventListener("change", sync);
  }, []);

  React.useEffect(() => {
    if (!lottie || reduced) return;
    let live = true;
    fetch("/brand/ball-loader.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((json) => live && json && setAnimationData(json))
      .catch(() => {
        /* the CSS ball is already bouncing */
      });
    return () => {
      live = false;
    };
  }, [lottie, reduced]);

  const useLottie = lottie && animationData && !reduced;

  return (
    <div
      className={cn("flex flex-col items-center justify-center gap-4", className)}
      role="status"
      aria-live="polite"
    >
      {useLottie ? (
        <div style={{ width: size * 1.5, height: size * 1.5 }}>
          <Lottie animationData={animationData} loop />
        </div>
      ) : (
        <BouncingBall size={size} />
      )}
      <p className="text-xs text-ink-muted">{label}</p>
    </div>
  );
}

export { CricketBall };
