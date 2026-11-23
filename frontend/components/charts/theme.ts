/** Chart tokens, kept in step with tailwind.config.ts so the system reads as one. */
export const CHART = {
  grid: "#1F2B3D",
  axis: "#64748B",
  tick: "#93A3B8",
  surface: "#182234",
  accent: "#FC5200",
};

/**
 * Categorical ramp. Amber leads because it is the product's accent, then hues
 * that stay separable on a dark blue ground without any two reading as "the
 * green one" and "the red one" - those two are reserved for direction.
 */
export const SERIES = [
  "#FC5200",
  "#6AA9E0",
  "#3FBF7F",
  "#E673A8",
  "#9B7BD4",
  "#4FB8C4",
  "#EE8A3C",
  "#94A3B8",
];

/** Phases keep one colour each everywhere they appear. */
export const PHASE_COLORS: Record<string, string> = {
  powerplay: "#6AA9E0",
  middle: "#94A3B8",
  death: "#FC5200",
};
