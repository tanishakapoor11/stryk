# Stryk — Cricket Intelligence Lab

A cricket analytics platform built on [Cricsheet](https://cricsheet.org/) ball-by-ball data.
It is not a scorecard site: it exists to answer questions like *where does this bowler
actually leak runs*, *is this strike rate good for the role*, and *does this head-to-head
record mean anything at all*.

Currently indexed: **IPL 2008–2026, 1,243 matches, ~296,000 deliveries, 816 players.**

---

## Quick start

```bash
# 1. Python environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

# 2. Data (≈ 20 MB download, ~1,200 match files)
python scripts/fetch_cricsheet.py ipl
python scripts/ingest.py                 # add --limit 50 for a fast smoke import
python scripts/fetch_player_names.py     # required for name search: "SS Iyer" -> "Shreyas Iyer"
python scripts/fetch_player_photos.py    # optional: freely licensed portraits

# 3. API on :8000
cd backend && uvicorn app.main:app --reload

# If the API was already running while step 2 ran, it is still serving the old data:
curl -X POST http://127.0.0.1:8000/api/admin/reload

# 4. Frontend on :3000 (separate terminal)
cd frontend && npm install && npm run dev
```

Open <http://localhost:3000>. The frontend reads `API_URL` from `frontend/.env.local`
(default `http://127.0.0.1:8000`).

Tests: `cd backend && python -m pytest`

**Gotchas on a fresh setup**

- **Skip `fetch_player_names.py` and search only knows scorecard names.** `Shreyas`
  finds nothing; only `SS Iyer` does, and Prabhsimran Singh shows as `P Simran Singh`.
  Ingest creates the players with scorecard names; this script adds the full names and
  aliases that search depends on (see [Player names](#player-names)).
- **The API caches the dataset in memory.** It is loaded on the first request and kept,
  so anything the scripts write afterwards — new matches, names, aliases — is invisible
  until `POST /api/admin/reload` or a server restart. Stale names after a successful
  name fetch almost always mean this.
- **The frontend caches the photo credits.** `lib/photos.ts` reads
  `public/players/credits.json` once and keeps it, and a photo is only shown when it
  has a credit entry. After fetching photos, restart `npm run dev` to see them.
- **Run the name and photo scripts one after the other, never at the same time.** Both
  call Wikimedia, which rate-limits with HTTP 429. Both scripts back off and retry, but
  in parallel they slow each other down. A photo run that reports
  `saved 0 photo(s)` / `skipped: no readable licence` was rate-limited: re-run it on
  its own. The thumbnail server also blocks after a burst of new downloads; the
  script then stops early and says so. Re-run it 15–30 minutes later, and it fetches
  only what is still missing.
- **The name fetch takes several minutes.** The bulk queries are quick, but players they
  miss are looked up one at a time, a second apart, and nothing is written to the
  database until the run ends.
- **"Internal error computing this analysis" on every page** with
  `unable to open database file` in the API log means `ingest.py` has not been run, so
  `data/processed/stryk.db` does not exist.

---

## What it does

| Page | What it answers |
|---|---|
| **Overview** `/` | Dataset scale, leaderboards with published qualification thresholds, season and phase trends, and insights generated from the data rather than written by hand. |
| **Player Intelligence** `/players` | Searchable, sortable directory; per-player profiles with batting and bowling splits by phase, season, venue, opposition and innings type, plus dismissal patterns, most-faced bowlers, and every recent innings ball by ball. |
| **Comparison** `/compare` | Two to four players on an identical filtered sample: metric tables, radar profiles, season trajectories, phase splits, chase/set splits and season-to-season spread. |
| **Match-ups** `/matchups` | Ball-by-ball head-to-head between a batter and a bowler, read against each player's own baseline, with the sample size stated before the statistics. |
| **Team Intelligence** `/teams` | Squad composition, batting depth by position, phase strength measured against the league, and chasing vs batting-first records. |
| **Auction Intelligence** `/auction` | Candidate pool scored against the league rate for the same deliveries, and a hypothetical squad builder with role requirements. |

Every filter lives in the URL, so any analysis is a shareable link:
`/players?season=2024&season=2025&phase=death&sort=strike_rate`.

---

## Architecture

```
Cricsheet JSON  ──▶  ingestion  ──▶  SQLite/PostgreSQL  ──▶  in-memory fact table
                     (parser)        (normalised schema)      (pandas, cached)
                                                                    │
                                              FastAPI  ◀────────────┘
                                                 │  JSON analytical documents
                                      Next.js RSC pages  ──▶  browser
```

**Why an in-memory fact table.** Every metric is a pandas aggregation over one
denormalised delivery table read from the database once and cached
(`backend/app/analytics/store.py`). At IPL scale (~300k rows, ~60 MB) this is faster
and far more maintainable than a bespoke SQL query per metric, and it keeps the
scoring rules in one place instead of scattering them across queries. The ceiling is
noted in the module: past a few million deliveries, or a multi-process deployment,
this becomes materialised SQL aggregates.

**Why the API returns loose JSON.** Analytical payloads are deep and change shape as
metrics are added. A second hand-maintained Pydantic mirror of every nested table
would rot. The contract is declared once, in TypeScript, in `frontend/types/index.ts`.

**Why all data fetching is server-side.** Pages are React Server Components; the
browser never talks to FastAPI directly, so none of the analytics payload cost lands
in the client bundle. Only the interactive pieces — filters, pickers, charts — are
client components.

**Database portability.** `database_url` is any SQLAlchemy URL. SQLite is the
zero-setup default; point `STRYK_DATABASE_URL` at PostgreSQL for deployment. Nothing
in the data-access layer is dialect specific.

**Extensibility to other formats.** Phase boundaries are per match type
(`PHASE_DEFINITIONS` in `backend/app/analytics/constants.py` already carries ODI
alongside T20), and `match_type` travels on every delivery row. The ingestion parser
is format-agnostic; adding Tests or internationals is a fetch, an ingest, and a phase
definition — not a rewrite.

### Layout

```
backend/app/
  analytics/      store (fact table + filters), metrics, players, teams,
                  matchups, overview, auction, constants (scoring rules)
  api/            router, dependency-injected filter parsing
  core/           config, database engine
  ingestion/      Cricsheet JSON parser
  models/         SQLAlchemy schema
tests/            statistical correctness tests on hand-worked scenarios

frontend/
  app/            routes (RSC pages)
  components/     design system (ui, charts, layout)
  features/       per-domain composition (players, compare, matchups, teams, auction)
  lib/            API client, URL-parameter helpers, formatters
  types/          the API contract

scripts/          fetch_cricsheet.py, ingest.py
data/raw/         downloaded Cricsheet JSON
data/processed/   stryk.db
```

---

## Player names

Cricsheet identifies players the way a scorecard does: initials plus surname, so
Shreyas Iyer is `SS Iyer` and Jasprit Bumrah is `JJ Bumrah`. Nobody searches like
that, so the product resolves a real full name for every player it can.

`scripts/fetch_player_names.py` does most of the work with three bulk requests to
public endpoints:

1. `cricsheet.org/register/people.csv` — Cricsheet identifier to ESPNcricinfo id.
2. Wikidata SPARQL (property `P2697`, "ESPNcricinfo player ID") — that id to a full name.
3. Wikidata SPARQL for English aliases on the same items (see below).

Players still unresolved after that, and still in initials form, are looked up one at a
time through Wikidata's search API, one request per second, with retries on HTTP 429.
That step is why a run takes minutes rather than seconds.

Joining them resolves **797 of 816 players (97.7%)**. Players it cannot resolve keep
their scorecard name; no name is ever constructed from the initials. The 19 remaining
are mostly uncapped domestic players, plus a few — `MS Dhoni`, `CH Gayle` — whose
Wikidata item has no English label. Drop a `cricsheet_id,full_name` row into
`data/raw/people/full_names_manual.csv` to override any of them.

Wikidata **aliases** are indexed too, which matters more than it sounds. Cricsheet writes
Prabhsimran Singh as `P Simran Singh` and Wikidata's label for him is the shorter
"Simran Singh", so the name people actually type lives only in an alias. 468 of 816
players carry at least one, covering full legal names, alternative transliterations and
abbreviated forms.

An alias is promoted to the *displayed* name only when it spells out the start of the
first name — same word count, identical surname, and the label's first word is the tail
of the alias's ("Simran Singh" → "Prabhsimran Singh"). Plain substring containment was
tried first and was far too eager: it promoted "Separamadu Lasith Malinga", "Cricketer
Ravindra Jadeja" and the misspelling "Nicolas Poorann", none of which is the name anyone
uses. Being passed over costs nothing, since every alias is indexed for search either way.

Search then matches on any of these forms, so all of these find the same player:

```
Shreyas  ·  Iyer  ·  Shreyas Iyer  ·  iyer shreyas  ·  SS Iyer  ·  S Iyer
Prabhsimran  ·  Simran  ·  Prabhsimran Singh  ·  P Simran Singh
```

A single-letter token is treated as an initial rather than a substring, so `v kohli`
finds V Kohli without returning every name containing a "v". In a multi-token query a
first name may match an initial — which is what keeps `chris gayle` working for a
player whose full name could not be sourced. Results are ranked by match quality and
then by matches played, so `sharma` returns Rohit Sharma first rather than a player who
appeared twice in 2011. See `backend/app/analytics/names.py`.

---

## Motion, loading and errors

**The loader** is a cricket ball in the brand orange — seam band with stitching, spinning
as it bounces, with a shadow that spreads on impact. It is **pure CSS**
(`components/ui/ball-loader.tsx`), and that is a deliberate reversal.

It started as a Lottie. Two things killed it as the default:

1. It could not animate until a JSON fetch *and* a dynamically imported player had both
   landed. On a screen that lives for under a second, all anyone saw was a frozen circle
   — which is exactly what got reported.
2. Its playback could not be verified. `lottie-web` drives itself from
   `requestAnimationFrame`, which is starved under headless Chrome: the animation
   advanced one frame in 1.5 seconds on the test rig, so there was no way to confirm it
   worked before shipping it.

CSS keyframes have neither problem. They animate on the first paint, need no runtime,
cannot fail to load, and are driven by the compositor rather than a JavaScript timer. A
loading indicator is the one component that must never depend on something else loading
first.

**The Lottie path is still there**, behind a `lottie` prop on `BallLoader`. Replace
`frontend/public/brand/ball-loader.json` (generated by `scripts/make_lottie.py`) and pass
the prop. It is opt-in rather than default because its failure mode is a motionless
loader. Note that stock animations from LottieFiles put the raw JSON behind an account
and carry the [Lottie Simple License](https://lottiefiles.com/page/license), whose terms
must travel with the file wherever it is distributed.

**404** (`app/not-found.tsx`) tells the story in the notation the product already uses:
a ball strip reading dot, dot, dot, W — the page is out. It offers a way back, a player
search, and the four main sections, because an empty screen should be an invitation to
act rather than a dead end.

**Transitions** are deliberately small. Route changes get a 260ms, 6px rise via
`app/template.tsx`; interactive cards lift slightly on hover through the
`.card-interactive` utility. Everything collapses to nothing under
`prefers-reduced-motion`, which is enforced globally in `globals.css`. Nothing on any
page is hidden until an animation runs — an earlier version of the ball strip gated its
content on a stagger and only showed eight of sixty-six balls, which is the mistake these
rules exist to prevent.

---

## Brand assets

The Stryk mark and wordmark live in `frontend/public/brand/`. Two of them are derived
rather than supplied: `mark-white.png` and `wordmark-white.png` were keyed out of the
navy-background originals so they sit on any surface, which is why the top bar and
footer can use them directly.

| File | Use |
|---|---|
| `wordmark-white.png` | Top bar |
| `mark-white.png` | Footer, and anywhere on a dark surface |
| `mark-navy.png`, `wordmark-navy.png` | Light surfaces |
| `icon-dark.png`, `icon-light.png` | Square app icons |
| `app/icon.png`, `app/apple-icon.png` | Favicon and touch icon (Next picks these up by filename) |
| `app/opengraph-image.png` | Social share card |

The palette in `tailwind.config.ts` is taken from the mark: its navy is the canvas and
its orange (`#FC5200`) is the accent, so the product and the logo are the same object.
The accent carries brand and interaction only — green and red still mean better or worse
than the league and nothing else, warnings keep amber (now clearly distinct from the
accent), and the negative signal was pushed towards crimson so it can never read as a
shade of the brand orange. Accent buttons use near-black text because white on that
orange fails contrast at small sizes.

---

## Imagery and franchise identity

Two things the product deliberately does *not* do: scrape player photographs from
cricket sites, and reproduce IPL franchise logos. The photographs are all rights
reserved and the crests are trademarks.

**Player portraits** come from Wikimedia Commons, matched to players through the same
ESPNcricinfo ids used for names (Wikidata property `P18`). Around **44% of players**
have a freely licensed image, including every one of the top 20 run scorers. Most
Commons licences require credit, so `scripts/fetch_player_photos.py` records the author
and licence for each image and the player card displays them; an image whose
attribution cannot be read is skipped rather than shown uncredited. Requests back off
and retry when Wikimedia rate-limits with HTTP 429 — without that, a throttled run
skipped every image because no licence could be read. Players without a
photo fall back to a monogram in their franchise's colour, so the interface never
depends on a photo existing.

Photos land in `frontend/public/players/` and are gitignored — they are fetched assets,
like the Cricsheet data itself.

**Franchise badges** are original shield marks. Each carries a simplified landmark from
the team's own city — the Charminar for Hyderabad, Howrah Bridge for Kolkata, a gopuram
for Chennai, a kite for Gujarat — which ties the badge to the franchise and gives a fan
something they recognise, without imitating anybody's artwork. If you hold the rights to
the real crests, drop files at `frontend/public/teams/<SHORT>.svg` (or `.png`, `.webp` —
e.g. `CSK.svg`) and they are used instead automatically. See
`components/ui/team-crest.tsx` and `teamLogo()` in `lib/photos.ts`.

---

## Data model

| Entity | Notes |
|---|---|
| `Match` | Cricsheet id, date, season, venue, teams, result, match type. Re-ingesting is idempotent on the source id. |
| `Innings` | Batting and bowling side, innings number, super-over flag, chase flag. |
| `Delivery` | One row per ball with derived scoring flags: `is_legal`, `is_ball_faced`, `bowler_runs`, `is_bowler_wicket`, `phase`. The flags are computed once, at ingestion, from the same constants the analytics layer reads. |
| `Dismissal` | Kind, dismissed player, whether credited to the bowler. |
| `Player`, `Team`, `Venue` | Registries. `Player.name` is the Cricsheet scorecard form and `Player.full_name` the resolved readable one (null where no source supplied it). Team renames are tracked as aliases so a franchise's record stays continuous (RCB's Bangalore era is the same team as its Bengaluru era). |
| `MatchPlayer` | Squad membership per match, used for appearance counts and team history. |

---

## Analytics correctness

The scoring rules live in one module, `backend/app/analytics/constants.py`, and are
read by both the ingestion pipeline and the analytics layer, so a rule cannot drift
between how data is stored and how it is reported.

- **Legal deliveries.** Wides and no-balls do not advance the over. Overs are
  `legal balls ÷ 6`, displayed as `overs.balls`.
- **Balls faced.** Excludes wides; includes no-balls, because the batter can score
  off them.
- **Bowler-credited runs.** Batter runs plus wides plus no-balls. Byes, leg-byes and
  penalty runs are conceded by the fielding side, not the bowler.
- **Bowler-credited wickets.** Bowled, caught, caught and bowled, lbw, stumped, hit
  wicket. Run-outs, retirements and obstructing the field are dismissals but not the
  bowler's wickets — and the match-up view reports both counts separately.
- **Batting average.** Runs ÷ dismissals. Not-outs are excluded from the denominator.
  `retired hurt` and `retired not out` leave the batter not out; `retired out` is a
  dismissal with no bowler credited.
- **Phases.** Powerplay overs 1–6, middle 7–15, death 16–20, assigned by over number.
  A rain-shortened innings contributes fewer deliveries to the later phases rather
  than being rescaled, so phase statistics stay comparable across matches.
- **Super overs** are excluded from career and season statistics.

**Undefined is not zero.** A batting average with no dismissals, an economy with no
balls bowled, a strike rate off no balls faced — the API returns `null` and the UI
renders an em dash. This is enforced end to end and is the single most important
display rule in the project.

`GET /api/meta/metrics` serves the formula and qualification threshold for every
derived statistic; the UI renders them in tooltips and in the "How these numbers are
calculated" panel on each analysis page, so no figure is shown without its definition
reachable from the same screen.

### Tests

`backend/tests/test_scoring.py` runs miniature Cricsheet documents through the real
parser and the real aggregation code, with expected figures worked out by hand in each
docstring: extras handling, run-outs vs bowler wickets, not-outs, phase boundaries on
a shortened innings, empty-input table shapes, and the league-rate baseline used by the
auction module. If a scoring rule changes, they fail.

---

## Known data limitations

These are stated in the product, not buried here, because each one would otherwise be
easy to fake.

- **No bowling style or bowling arm.** Cricsheet ball-by-ball files carry neither. Stryk
  therefore publishes no "versus left-arm pace" or "versus leg spin" splits for the IPL;
  inferring a style from a name or a partial register would be invention. Named-bowler
  match-ups are offered instead, which is the thing the style split was a proxy for.
- **No player nationality.** Overseas-player composition and overseas slot limits cannot
  be computed, so the team page says so and the auction builder does not enforce a limit.
- **No auction prices.** There is no price information anywhere in Cricsheet. Stryk will
  not estimate one, because an estimate presented next to real statistics reads as a
  market fact. Prices load from an optional operator-supplied file at
  `data/raw/auction/prices.csv` (`player_name,season,price_inr,team,source`); without it
  the module reports `prices_available: false` and the budget and value-per-rupee
  features stay switched off.
- **Batting position is reconstructed** from the order players arrive at the crease, not
  read from a team sheet.
- **Player role is inferred from workload** (300+ balls faced and 300+ bowled is an
  all-rounder; otherwise whichever the player has done more of). It is an analytical
  label published with its thresholds, not an official designation.

### On the impact metrics

The auction module scores a player against what the league scored off the same number
of deliveries *in the same phases*: batting impact is `runs − (balls faced × league runs
per ball)`, bowling impact is `(legal balls × league runs per ball) − runs conceded`.
Wickets are reported alongside but are deliberately **not** folded in: converting a
wicket into runs requires an assumption about the value of a dismissal that this data
cannot supply, and a combined number would hide that assumption inside a single figure.
For the same reason batting and bowling impact are never summed into one rating.

Impact is a total, so it rewards longevity — the per-match column and the season filter
exist to make a two-season player comparable to a ten-season one.

---

## API

| Endpoint | Returns |
|---|---|
| `GET /health` | Dataset status and load time. |
| `GET /api/overview` | Summary, leaderboards, trends, distribution, insights. |
| `GET /api/players` | Directory: `q`, `role`, `sort`, `order`, `limit`, `offset`. |
| `GET /api/players/{id}` | Full profile with every split. |
| `GET /api/players/{id}/matchups` | Most-faced opponents (`as_role=batter\|bowler`). |
| `GET /api/compare?player=…&player=…` | Side-by-side profiles. |
| `GET /api/matchup?batter=…&bowler=…` | Head-to-head with reliability grading. |
| `GET /api/teams`, `/api/teams/{id}` | Team index and profile. |
| `GET /api/auction/pool` | Scored candidate pool and squad requirements. |
| `GET /api/meta/seasons\|teams\|venues\|metrics` | Filter vocabulary and metric definitions. |
| `GET /api/search?q=` | Players and teams. |
| `POST /api/admin/reload` | Re-read the fact table after an ingestion run. |

Every analytical endpoint accepts the same filters: `season` (repeatable), `team`,
`opposition`, `venue`, `phase` (repeatable), `innings`, `chasing`, `date_from`,
`date_to`, `include_super_over`. Interactive docs at <http://localhost:8000/docs>.

---

## Adding seasons or another competition

```bash
python scripts/fetch_cricsheet.py ipl
python scripts/ingest.py --seasons 2026     # incremental; existing matches are skipped
python scripts/fetch_player_names.py        # resolve names for any new players
python scripts/fetch_player_photos.py       # and portraits, if you use them
curl -X POST http://127.0.0.1:8000/api/admin/reload
```

Ingestion is idempotent on the Cricsheet match id, so re-running over the full
directory never duplicates a match. `--reset` drops and rebuilds. Validation warnings
are printed at the end of each run.
