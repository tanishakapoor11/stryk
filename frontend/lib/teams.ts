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

  // --- Big Bash League (men's and women's share a club and a colour) ---
  "Adelaide Strikers":   { short: "STR", primary: "#4FA8D8", secondary: "#27406E", tagline: "" },
  "Brisbane Heat":       { short: "HEA", primary: "#3FBFB0", secondary: "#14504C", tagline: "" },
  "Hobart Hurricanes":   { short: "HUR", primary: "#9B6FD4", secondary: "#46307A", tagline: "" },
  "Melbourne Renegades": { short: "REN", primary: "#E0565F", secondary: "#5B2328", tagline: "" },
  "Melbourne Stars":     { short: "STA", primary: "#5FBF6B", secondary: "#1E5B2B", tagline: "" },
  "Perth Scorchers":     { short: "SCO", primary: "#F08A3C", secondary: "#5B3A1E", tagline: "" },
  "Sydney Sixers":       { short: "SIX", primary: "#E668A8", secondary: "#7A2550", tagline: "" },
  "Sydney Thunder":      { short: "THU", primary: "#A8D44F", secondary: "#3F5B1E", tagline: "" },

  // --- The Hundred (men's and women's share a club) ---
  "Birmingham Phoenix":      { short: "BPH", primary: "#C86FD4", secondary: "#5B2A66", tagline: "" },
  "London Spirit":           { short: "LNS", primary: "#4FA37E", secondary: "#1E4A38", tagline: "" },
  "Manchester Originals":    { short: "MNR", primary: "#E0565F", secondary: "#6B1E24", tagline: "" },
  "Northern Superchargers":  { short: "NOS", primary: "#4FC4C4", secondary: "#1E5B5B", tagline: "" },
  "Oval Invincibles":        { short: "OVI", primary: "#4FC0E8", secondary: "#1E5B7A", tagline: "" },
  "Southern Brave":          { short: "SOB", primary: "#5C7FD6", secondary: "#22305B", tagline: "" },
  "Trent Rockets":           { short: "TRT", primary: "#A8D44F", secondary: "#3F5B1E", tagline: "" },
  "Welsh Fire":              { short: "WEF", primary: "#F0703C", secondary: "#6B2A1E", tagline: "" },
  // The 2025 sales rebranded three clubs onto their new owners' identities.
  "MI London":               { short: "MIL", primary: "#4A8FD4", secondary: "#E0B64A", tagline: "" },
  "Manchester Super Giants": { short: "MSG", primary: "#4FB8C4", secondary: "#E0B64A", tagline: "" },
  "Sunrisers Leeds":         { short: "SUL", primary: "#EE8A3C", secondary: "#2E6FB7", tagline: "" },

  // --- Pakistan Super League ---
  "Islamabad United":  { short: "ISL", primary: "#E05A4A", secondary: "#6B2A22", tagline: "" },
  "Karachi Kings":     { short: "KAR", primary: "#4FA8D8", secondary: "#1E4A7A", tagline: "" },
  "Lahore Qalandars":  { short: "LAH", primary: "#5FBF8F", secondary: "#1E5B3F", tagline: "" },
  "Multan Sultans":    { short: "MUL", primary: "#4FB8C4", secondary: "#1E5B66", tagline: "" },
  "Peshawar Zalmi":    { short: "PES", primary: "#F2C14E", secondary: "#6B5B1E", tagline: "" },
  "Quetta Gladiators": { short: "QUE", primary: "#9B7BD4", secondary: "#46307A", tagline: "" },

  // --- Caribbean Premier League (current franchises only) ---
  "Barbados Royals":            { short: "BR",  primary: "#E673A8", secondary: "#2E6FB7", tagline: "" },
  "Guyana Amazon Warriors":     { short: "GAW", primary: "#5FBF6B", secondary: "#D4A24A", tagline: "" },
  "Jamaica Tallawahs":          { short: "JAM", primary: "#F2C14E", secondary: "#3F7A3F", tagline: "" },
  "St Kitts and Nevis Patriots":{ short: "SKN", primary: "#5C8FD6", secondary: "#E0565F", tagline: "" },
  "St Lucia Kings":             { short: "SLK", primary: "#4F8FD6", secondary: "#D4A24A", tagline: "" },
  "Trinbago Knight Riders":     { short: "TKR", primary: "#9B7BD4", secondary: "#D4A24A", tagline: "" },

  // --- SA20, ILT20, MLC: these carry their parent franchise's identity by
  //     design, which is why the colours repeat rather than being invented.
  "Durban's Super Giants":  { short: "DSG", primary: "#4FB8C4", secondary: "#E0B64A", tagline: "" },
  "Joburg Super Kings":     { short: "JSK", primary: "#F2B134", secondary: "#2E6FB7", tagline: "" },
  "MI Cape Town":           { short: "MICT",primary: "#4A8FD4", secondary: "#E0B64A", tagline: "" },
  "Paarl Royals":           { short: "PR",  primary: "#E673A8", secondary: "#2E6FB7", tagline: "" },
  "Pretoria Capitals":      { short: "PC",  primary: "#5C8FD6", secondary: "#E0565F", tagline: "" },
  "Sunrisers Eastern Cape": { short: "SEC", primary: "#EE8A3C", secondary: "#2E6FB7", tagline: "" },
  "Abu Dhabi Knight Riders":{ short: "ADKR",primary: "#9B7BD4", secondary: "#D4A24A", tagline: "" },
  "Dubai Capitals":         { short: "DUB", primary: "#5C8FD6", secondary: "#E0565F", tagline: "" },
  "MI Emirates":            { short: "MIE", primary: "#4A8FD4", secondary: "#E0B64A", tagline: "" },
  "Los Angeles Knight Riders": { short: "LAKR", primary: "#9B7BD4", secondary: "#D4A24A", tagline: "" },
  "MI New York":            { short: "MINY",primary: "#4A8FD4", secondary: "#E0B64A", tagline: "" },
  "Texas Super Kings":      { short: "TSK", primary: "#F2B134", secondary: "#2E6FB7", tagline: "" },

  // --- Women's Premier League (the other three are IPL clubs, above) ---
  "Gujarat Giants": { short: "GG",  primary: "#6B8FC4", secondary: "#D4A24A", tagline: "" },
  "UP Warriorz":    { short: "UPW", primary: "#9B7BD4", secondary: "#D4A24A", tagline: "" },
};

/*
 * Which sides are listed above, and which are deliberately not.
 *
 * A franchise's colours are a fact about it, the way its name is: a fan reads
 * Sydney Sixers from the magenta before reading the word. So the strongly
 * branded T20 franchises are listed, and that is what stops a league page
 * being a wall of identical grey.
 *
 * Three groups are left out on purpose rather than by oversight:
 *
 *  - First-class and List A sides - the counties, the Sheffield Shield and
 *    Plunket Shield states, the Ranji sides. These have club colours in the
 *    heraldic sense, but no recognised brand palette, and picking one would
 *    be invention dressed as data.
 *  - Leagues whose franchises churn every season or two: the BPL's 34 teams
 *    across its history, the LPL's 19, the Nepal and Mzansi leagues. The
 *    current holders are not stable enough to be worth asserting.
 *  - Individual clubs whose colours I could not establish - several ILT20 and
 *    MLC sides. A guessed colour is worse than a neutral one, because it
 *    looks like knowledge.
 *
 * Everything left out falls back to the neutral slate below and its derived
 * abbreviation, which is a legible, honest default rather than a wrong one.
 */

/** Neutral slate for a franchise with no entry; never a random colour. */
const FALLBACK: TeamIdentity = {
  short: "", primary: "#8FA6BF", secondary: "#64748B", tagline: "",
};

/** Words that never contribute a letter to an abbreviation. */
const MINOR = new Set(["and", "of", "the", "de", "xi"]);

/**
 * An abbreviation for a side nobody has configured one for.
 *
 * The database supplies a short name for the 15 IPL franchises and, since
 * national teams were linked to their country, for every nation. That leaves
 * roughly 300 domestic and franchise sides — counties, Shield states, BBL and
 * PSL clubs — which had been rendering as an em dash. An abbreviation built
 * from the name is a display label, not a claimed statistic: it says nothing
 * the name does not already say, and it is better than a blank where the eye
 * expects a badge.
 *
 * Several words take their initials (Trinbago Knight Riders -> TKR); one word
 * takes its first three letters (Surrey -> SUR).
 */
export function initials(name: string): string {
  const words = name
    .split(/[\s-]+/)
    .map((w) => w.replace(/[^A-Za-z0-9]/g, ""))
    .filter((w) => w && !MINOR.has(w.toLowerCase()));
  if (!words.length) return name.slice(0, 3).toUpperCase();
  if (words.length === 1) return words[0].slice(0, 3).toUpperCase();
  return words.map((w) => w[0]).join("").slice(0, 4).toUpperCase();
}

/**
 * `short` is the abbreviation the API supplies — an IPL franchise's own, or a
 * national side's country code. The hardcoded table still wins, because it is
 * also where a franchise's colours and tagline live, and the two must agree.
 */
export function teamIdentity(
  name: string | null | undefined,
  short?: string | null,
): TeamIdentity {
  if (!name) return FALLBACK;
  const known = TEAMS[name];
  if (known) return known;
  return { ...FALLBACK, short: short || initials(name) };
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
