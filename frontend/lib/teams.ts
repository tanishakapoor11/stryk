/**
 * Franchise identity.
 *
 * A fan recognises CSK by yellow and KKR by purple long before they read the
 * name, so franchise colour is treated as data the reader already has. It is
 * the protagonist of every team and player page: the page is tinted by whoever
 * it is about, rather than every page looking the same.
 *
 * `primary` and `secondary` are each franchise's own colours, nudged for
 * legibility on a dark ground. No logos or crests are used — those are
 * trademarks — so identity is carried by colour and a typographic monogram.
 *
 * Keyed on the team name Cricsheet uses; renamed franchises point at the same
 * identity as their current name, because a rename is not a new team.
 */
export interface TeamIdentity {
  short: string;
  primary: string;
  secondary: string;
  /** Shown on the team page: what this franchise is known for. */
  tagline: string;
}

const TEAMS: Record<string, TeamIdentity> = {
  "Chennai Super Kings": {
    short: "CSK", primary: "#F2B134", secondary: "#2E6FB7", tagline: "Yellow army",
  },
  "Mumbai Indians": {
    short: "MI", primary: "#4A8FD4", secondary: "#E0B64A", tagline: "Paltan",
  },
  "Royal Challengers Bengaluru": {
    short: "RCB", primary: "#E0565F", secondary: "#D4A24A", tagline: "Bold diaries",
  },
  "Royal Challengers Bangalore": {
    short: "RCB", primary: "#E0565F", secondary: "#D4A24A", tagline: "Bold diaries",
  },
  "Kolkata Knight Riders": {
    short: "KKR", primary: "#9B7BD4", secondary: "#E0B64A", tagline: "Korbo laro jeetbo",
  },
  "Sunrisers Hyderabad": {
    short: "SRH", primary: "#EE8A3C", secondary: "#2E6FB7", tagline: "Orange army",
  },
  "Rajasthan Royals": {
    short: "RR", primary: "#E673A8", secondary: "#2E6FB7", tagline: "Halla bol",
  },
  "Delhi Capitals": {
    short: "DC", primary: "#5C8FD6", secondary: "#E0565F", tagline: "Roar of Delhi",
  },
  "Delhi Daredevils": {
    short: "DD", primary: "#5C8FD6", secondary: "#E0565F", tagline: "Roar of Delhi",
  },
  "Punjab Kings": {
    short: "PBKS", primary: "#D9535F", secondary: "#D4A24A", tagline: "Sadda punjab",
  },
  "Kings XI Punjab": {
    short: "PBKS", primary: "#D9535F", secondary: "#D4A24A", tagline: "Sadda punjab",
  },
  "Lucknow Super Giants": {
    short: "LSG", primary: "#4FB8C4", secondary: "#E0B64A", tagline: "Ab apni baari hai",
  },
  "Gujarat Titans": {
    short: "GT", primary: "#8FA6BF", secondary: "#D4A24A", tagline: "Aava de",
  },
  "Gujarat Lions": {
    short: "GL", primary: "#E09F3E", secondary: "#5C8FD6", tagline: "Pride of Gujarat",
  },
  "Rising Pune Supergiant": {
    short: "RPS", primary: "#B07CC6", secondary: "#E0B64A", tagline: "Pune's giants",
  },
  "Rising Pune Supergiants": {
    short: "RPS", primary: "#B07CC6", secondary: "#E0B64A", tagline: "Pune's giants",
  },
  "Pune Warriors": {
    short: "PW", primary: "#6BA3C9", secondary: "#8FA6BF", tagline: "Warriors of Pune",
  },
  "Deccan Chargers": {
    short: "DCH", primary: "#9AA5B1", secondary: "#E0B64A", tagline: "Charge of Deccan",
  },
  "Kochi Tuskers Kerala": {
    short: "KTK", primary: "#D98F6B", secondary: "#4FB8C4", tagline: "Kerala's tuskers",
  },
};

/** Neutral slate for a franchise with no entry; never a random colour. */
const FALLBACK: TeamIdentity = {
  short: "—", primary: "#8FA6BF", secondary: "#64748B", tagline: "",
};

export function teamIdentity(name: string | null | undefined): TeamIdentity {
  if (!name) return FALLBACK;
  return TEAMS[name] ?? FALLBACK;
}

export function teamColor(name: string | null | undefined): string {
  return teamIdentity(name).primary;
}

/**
 * CSS custom properties for a franchise, spread onto any wrapper element.
 * Children then style themselves with `var(--team)` and friends, so one
 * component tree can be re-skinned per team without prop drilling.
 */
export function teamVars(name: string | null | undefined): React.CSSProperties {
  const id = teamIdentity(name);
  return {
    ["--team" as string]: id.primary,
    ["--team-2" as string]: id.secondary,
  };
}
