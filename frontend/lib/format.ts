/**
 * Display helpers.
 *
 * The single most important rule: a statistic that is undefined (a batting
 * average with no dismissals, an economy with no balls bowled) renders as an
 * em dash, never as zero. The API sends null for these and the UI must keep
 * that distinction visible.
 */
export const EMPTY = "—";

export function num(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY;
  return value.toLocaleString("en-IN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function dec(value: number | null | undefined, digits = 2): string {
  return num(value, digits);
}

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return EMPTY;
  return `${value.toFixed(digits)}%`;
}

export function signed(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return EMPTY;
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)}`;
}

export function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return EMPTY;
  const d = new Date(iso);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

/** "4/27" style bowling figures. */
export function figures(wickets?: number | null, runs?: number | null): string {
  if (wickets === null || wickets === undefined) return EMPTY;
  return `${wickets}/${runs ?? EMPTY}`;
}

export function initials(name: string): string {
  const parts = name.replace(/[^\w\s]/g, "").split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
