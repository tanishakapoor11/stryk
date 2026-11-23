# STRYK: from IPL analytics to a competition-agnostic platform

Status: Phase 1 (foundation) implemented. Phases 2–4 are planned, not built.
Source facts in this document were checked on 2026-11-24.

---

## 1. Existing architecture (before this change)

```
Cricsheet zip ──▶ scripts/fetch_cricsheet.py ──▶ data/raw/ipl_json/*.json
                                                       │
                  scripts/ingest.py ─▶ app/ingestion/cricsheet.py (parse_match, pure)
                                                       │  rows
                                                       ▼
                         SQLite / PostgreSQL (create_all, no migrations)
                         team · venue · player · match · match_player
                         innings · delivery (denormalised fact) · dismissal
                                                       │  read once
                                                       ▼
                     app/analytics/store.py  ─ in-memory pandas Dataset (cached)
                     metrics · players · teams · overview · matchups · auction
                                                       │
                     app/api/router.py (FastAPI, /api/*, loose JSON)
                                                       │  server-side fetch
                                                       ▼
                     Next.js RSC pages (/, /players, /compare, /matchups, /teams, /auction)
```

Already competition-agnostic, and kept:

- `Match.match_type`, `Match.gender` and `Match.event_name` are stored for every match.
- Phase boundaries are per format (`PHASE_DEFINITIONS` has T20 and ODI).
- Player ids are Cricsheet's global registry ids, so one person is one row across
  every competition Cricsheet covers.
- Super overs, D/L results, ties decided by eliminator, and no-results are parsed.
- Scoring rules live in one place (`constants.py`) and are covered by 27 hand-worked tests.

## 2. IPL-specific assumptions found

| Where | Assumption | Effect if a second competition is ingested |
|---|---|---|
| `models.Team.name` unique | A team name identifies one team | "India" men and "India" women collapse into one team |
| `ingestion/cricsheet.py` `TEAM_CANONICAL`, `TEAM_SHORT` | IPL franchise renames and short names hard-coded | Not wrong for other teams, but IPL-only config living in code |
| `models` docstring, `Match.season` | A season is the calendar year of the first match | BBL 2023/24 would be split across two "seasons" |
| `analytics/store.py` | One global ball table, every analytic runs over all of it | IPL, internationals and women's cricket would be pooled into one career record |
| `teams.list_teams` | "Active" = played in the latest season in the whole dataset | Meaningless across competitions |
| `overview.summary` | `"source": "Cricsheet ball-by-ball IPL data"` | Wrong label |
| `scripts/ingest.py` | Default directory `ipl_json` | Only IPL ingestable without flags |
| `auction.py` | Squad template is a T20 franchise XI; prices in INR | Fine for IPL, not general (left as an IPL-scoped feature) |
| `frontend/lib/teams.ts`, `team-crest.tsx` | Colours and crests for IPL franchises only | Others fall back to neutral slate (already safe) |
| `frontend top-bar` | Subtitle "IPL ball-by-ball"; nav has no competition concept | No way to reach anything but IPL |
| `frontend` copy | "Every ball of the IPL, since 2008" etc. | Copy only |
| No `Competition`, `Season`, `Country` tables | – | Nothing to browse, no coverage, no standings |

## 3. Schema changes (Phase 1)

New tables: `country`, `competition`, `season`, `points_system`, `tournament_stage`,
`tournament_group`, `competition_team`, `player_team`, `match_official`,
`data_source`, `source_dataset`, `external_id`.

Changed tables:

- `team`: unique key becomes `(name, gender)`; adds `team_type`, `gender`,
  `country_id`, `is_national_team`, `is_active`, `logo`.
- `player`: adds `date_of_birth`, `country_id`, `playing_role`, `image`, `is_active`
  (nullable, never guessed; no Phase 1 source supplies them).
- `match`: adds `competition_id`, `season_id`, `stage_id`, `group_id`, `status`,
  `data_level`, `source_id`, `external_id`. `season` (int) and `event_name` stay for
  compatibility with existing analytics and URLs.

Deliberately **not** created yet: `PointsTableEntry`, `PlayerMatchStats`,
`TeamMatchStats`. Standings are derived from results with the competition's points
system, and per-match stats are derived from deliveries. Tables for them arrive with
the first provider that supplies them without ball-by-ball data (Phase 2), so there
are no empty tables pretending to hold data.

Migrations move to Alembic (`backend/migrations`). Revision `0001` is the
pre-expansion schema; `0002` adds the above and backfills an existing IPL database
in place. A database created by the old `create_all` path is detected and stamped at
`0001` before upgrading.

## 4. Competition, season and coverage model

- **Catalogue as data, not code.** `backend/app/catalog/*.json` lists countries,
  competitions (type, gender, country, governing body, formats, season naming,
  points system, source dataset) and points systems. Adding a competition is a JSON
  entry plus an ingest, with no new page or endpoint.
- **Resolution.** Each ingested match is matched to a competition by rules in the
  catalogue (`event` name + gender + team type + format). Bilateral internationals
  resolve to a per-gender, per-format competition (e.g. *Women's ODIs*). An unknown
  event becomes a `OTHER` competition flagged `is_catalogued = false`: it is shown, but
  with no invented metadata.
- **Seasons.** `season_naming` per competition: `calendar_year` (IPL, whose Cricsheet
  labels "2007/08" and "2020/21" are wrong for the year played) or `source_label`
  (BBL "2023/24"). Stages come from `event.stage` (league vs knockout); groups from
  `event.group`.
- **Coverage.** Data levels 1–5 as specified. Each match stores its level; seasons and
  competitions report `ball_by_ball`, `scorecard`, `results`, `metadata`,
  `not_ingested` (a source has it, we have not imported it) or `unavailable` (no
  source we use publishes it).

## 5. Reused, not rewritten

- All analytics modules: they now receive a **scoped dataset** (one competition set,
  validated to a single gender and format) instead of the global one, so they cannot
  mix men's and women's or T20 and Test records. Default scope is the configured
  default competition (`ipl`), so every existing URL behaves as before.
- Leaderboards (`overview.leaderboards`) power competition and season leaders.
- Frontend: `Card`, `Badge`, `Table`, `PageHeader`, `states`, filter URL conventions,
  team colour system, `api()` client.

## 6. Phases

| Phase | Scope | Status |
|---|---|---|
| 1 Foundation | Schema + migrations, catalogue, provider abstraction, competition resolver, coverage, scoped analytics, standings engine with configurable points rules, competition/season APIs, competition directory, reusable competition and season pages, women's hub, coverage indicators | **This change** |
| 2 Core coverage | Ingest internationals (Tests/ODIs/T20Is, men and women), ICC events, WPL, WBBL, The Hundred, county and Sheffield Shield. Match page and scorecards. Series entity for bilateral tours. Replace the in-memory store for scale | Planned |
| 3 Global expansion | PSL, BBL, SA20, CPL, ILT20, MLC, BPL, LPL; more domestic and women's | Planned |
| 4 Intelligence | Cross-competition scouting, global comparison, Table Lab (scenarios, simulation) | Planned |

## 7. Breaking changes and risks

- **Database migration required.** Run `python scripts/migrate.py` (or any ingest),
  then `POST /api/admin/reload`. The migration is in place and keeps all data.
- **Team identity key changed** to `(name, gender)`. Team ids for existing IPL teams are
  unchanged.
- **Analytics default scope.** Endpoints without `competition=` now mean "the default
  competition", not "everything in the database". With only IPL ingested this is
  identical; after Phase 2 ingests, it is what prevents pooled careers.
- **Scale.** The in-memory store holds ~300k IPL deliveries (~60 MB). All of Cricsheet is
  ~23,000 matches, which is roughly 30–40× more. Scoped views are cached, but loading
  everything into memory will not survive Phase 2; materialised per-competition
  aggregates are the planned replacement.
- **Sources not available.** Cricsheet does not publish the Ranji, Duleep or Vijay
  Hazare Trophies, the World Test Championship as a competition, or U19 World Cups.
  They appear in the catalogue as `unavailable` until a licensed source is added.
- **Upcoming and live fixtures** are not in any Phase 1 source. Season pages say so
  instead of showing an empty fixture list.

## 8. Source coverage registry

`backend/app/catalog/sources.json` records, per source: licence, attribution,
update frequency, data level, and every dataset it publishes with the match count
seen on the date checked. Cricsheet: ODC-By 1.0 (attribution required), ball-by-ball
(level 4), updated continuously, 52 datasets / 23,241 matches as of 2026-11-24.
