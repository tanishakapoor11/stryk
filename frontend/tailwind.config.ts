import type { Config } from "tailwindcss";

/**
 * Stryk design tokens.
 *
 * Taken from the Stryk mark: its navy becomes the canvas and its orange the
 * accent, so the product and the logo are the same object.
 *
 * The accent does the brand and interaction work, which leaves green and red
 * free to mean only one thing anywhere in the product - better or worse than
 * the league. A reader never has to ask whether a green number is "good" or
 * just "branded". Warnings keep amber, now clearly distinct from the accent,
 * and the negative signal is pushed towards crimson so it never reads as a
 * shade of the brand orange.
 *
 * Franchise colours live in lib/teams.ts, because a team's colour is data a
 * fan already knows, not decoration.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./features/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#080F1C",
        surface: { DEFAULT: "#101827", raised: "#182234", sunken: "#0B1322" },
        line: { DEFAULT: "#1F2B3D", strong: "#31405A" },
        ink: { DEFAULT: "#EDF2F8", muted: "#93A3B8", faint: "#64748B" },
        accent: {
          /** The ball in the mark. */
          DEFAULT: "#FC5200",
          soft: "#3A1405",
          dim: "#C24000",
          /** Near-black on orange: white would fail contrast at small sizes. */
          foreground: "#1A0A00",
        },
        signal: {
          up: "#3FBF7F",
          down: "#F2415F",
          warn: "#F2B134",
          info: "#6AA9E0",
        },
        /** The ball-by-ball strip: the one visual every cricket fan can read. */
        ball: {
          dot: "#2A3645",
          run: "#5C7490",
          four: "#6AA9E0",
          six: "#3FBF7F",
          wicket: "#F2415F",
          extra: "#F2B134",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "var(--font-sans)", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.01em" }],
      },
      borderRadius: { DEFAULT: "6px", md: "8px", lg: "12px", xl: "16px" },
      boxShadow: {
        raise: "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 1px 2px rgba(0,0,0,0.45)",
        lift: "0 8px 30px -12px rgba(0,0,0,0.7)",
      },
      keyframes: {
        shimmer: { "100%": { transform: "translateX(100%)" } },
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        /** Route changes and first paint. Kept short: anything longer and the
         *  page is invisible while someone is waiting to read it. */
        "fade-rise": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "pop-in": {
          "0%": { opacity: "0", transform: "scale(0.92)" },
          "60%": { transform: "scale(1.02)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        /* The loader, in pure CSS, so it animates on the first paint rather
           than after a fetch. Split across three keyframe sets because the
           bounce, the squash and the spin apply to nested elements - one
           transform property cannot carry all three. */
        "ball-fall": {
          from: { transform: "translateY(0)" },
          to: { transform: "translateY(var(--drop, 44px))" },
        },
        "ball-squash": {
          "0%, 42%": { transform: "scale(1, 1)" },
          "50%": { transform: "scale(1.2, 0.8)" },
          "58%, 100%": { transform: "scale(1, 1)" },
        },
        "ball-spin": {
          from: { transform: "rotate(0deg)" },
          to: { transform: "rotate(360deg)" },
        },
        "ball-shadow": {
          "0%, 100%": { transform: "scaleX(0.6)", opacity: "0.12" },
          "50%": { transform: "scaleX(1.15)", opacity: "0.34" },
        },
      },
      animation: {
        shimmer: "shimmer 1.6s infinite",
        "fade-in": "fade-in 180ms ease-out",
        "fade-rise": "fade-rise 260ms cubic-bezier(0.22, 0.8, 0.3, 1) both",
        "pop-in": "pop-in 240ms cubic-bezier(0.22, 0.9, 0.3, 1) both",
        "ball-fall": "ball-fall 600ms cubic-bezier(0.5, 0, 1, 0.5) infinite alternate",
        "ball-squash": "ball-squash 1200ms linear infinite",
        "ball-spin": "ball-spin 1200ms linear infinite",
        "ball-shadow": "ball-shadow 1200ms linear infinite",
      },
      transitionTimingFunction: {
        snap: "cubic-bezier(0.22, 0.8, 0.3, 1)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
export default config;
