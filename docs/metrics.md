# Metric reference — what each number means, and where it stops meaning it

Every derived statistic in Stryk is listed here with its formula, what it is good for,
and what it cannot tell you. The same formulas are served live at
`GET /api/meta/metrics` and rendered in the UI, so this document and the product cannot
disagree.

---

## 1. The rules underneath everything

These are implemented once, in `backend/app/analytics/constants.py`, and read by both
the ingestion pipeline and the analytics layer.

| Rule | Decision |
|---|---|
| Legal delivery | Not a wide, not a no-ball. Only legal deliveries advance the over. |
| Ball faced (batter) | Excludes wides. **Includes no-balls** — the batter can score off them. |
| Runs conceded (bowler) | Batter runs + wides + no-balls. **Excludes** byes, leg-byes, penalties. |
| Wicket (bowler) | bowled, caught, caught and bowled, lbw, stumped, hit wicket. |
| Dismissal (batter) | The above plus run out, obstructing the field, retired out, timed out, hit the ball twice. |
| Not out | `retired hurt` and `retired not out` leave the batter not out. |
| Phase | Powerplay 1–6, middle 7–15, death 16–20, by over number. |
| Super over | Excluded from all career and season statistics. |

The two dismissal rows matter more than they look. A batter run out off a bowler's
delivery has been dismissed, and that fact belongs in the batter's average and in the
match-up record — but it is not that bowler's wicket. The match-up view reports
`dismissals` and `bowler_dismissals` as separate numbers for exactly this reason.

---

## 2. Batting

| Metric | Formula | Reads as |
|---|---|---|
| Runs | Sum of runs off the bat | Excludes all extras, including leg-byes run off the batter's pads. |
| Balls faced | Deliveries faced excluding wides | |
| Average | Runs ÷ dismissals | How long the batter survives. **Undefined with no dismissals** — shown as `—`, never 0. |
| Strike rate | Runs ÷ balls faced × 100 | How fast. Says nothing about how long. |
| Boundary % | (4s + 6s) ÷ balls faced × 100 | How often the batter finds the fence. |
| Dot % | Balls with no run off the bat ÷ balls faced × 100 | Pressure absorbed. A ball that ran for leg-byes is still a dot *for the batter*. |
| Boundary run % | Boundary runs ÷ total runs × 100 | **The most diagnostic batting number here.** |

### Why boundary run % earns its place

Strike rate alone cannot distinguish two batters at 140: one who hits a boundary every
fourth ball and blocks the rest, and one who rotates strike relentlessly and clears the
rope occasionally. The first collapses when the field is set and the boundary dries up;
the second does not. Boundary run % separates them — a batter taking 70%+ of their runs
in boundaries is dependent on them.

**Where it stops:** it is role-blind. A number 7 striking at 180 off 15 balls *should*
be boundary-dependent; that is the job. Read it against the phase splits, not alone.

### Average vs strike rate

These measure different things and cannot be traded off against each other without a
stated role. A top-order batter averaging 45 at 130 and a finisher averaging 22 at 170
are not rankable on either number. This is why the comparison page tints the leading
cell in each row but never produces an overall verdict.

---

## 3. Bowling

| Metric | Formula | Reads as |
|---|---|---|
| Overs | Legal balls ÷ 6, shown `overs.balls` | |
| Runs conceded | Batter runs + wides + no-balls | Byes and leg-byes are the keeper's problem. |
| Wickets | Dismissals credited to the bowler | |
| Economy | Runs conceded ÷ overs | Containment. |
| Average | Runs conceded ÷ wickets | Cost per wicket. **Undefined with no wickets.** |
| Strike rate | Legal balls ÷ wickets | How often the bowler strikes, independent of cost. |
| Dot % | Legal deliveries conceding nothing ÷ legal balls × 100 | Pressure created. |

### Why economy must be read with phase

An economy of 8.5 is poor in the powerplay and good at the death. Comparing two bowlers
on career economy without knowing when they bowl is the most common error in T20
analysis, and it systematically flatters powerplay specialists and punishes death
bowlers. Every bowling view in Stryk carries the phase split beside the career line, and
the team page compares each phase against the league's rate for that same phase under
the same filters.

### Strike rate vs average

A bowler with a low strike rate and a high average takes wickets but is expensive doing
it — a wicket-taking option, not a containing one. The pairing identifies role; neither
number does on its own.

---

## 4. Qualification thresholds

A rate statistic on a tiny denominator is noise. Every leaderboard states its threshold
in its own response:

| Board | Minimum |
|---|---|
| Batting strike rate | 500 balls faced |
| Batting average | 20 innings |
| Bowling economy | 500 balls bowled |
| Bowling average | 20 wickets |
| Season-level rates | 150 balls |
| Auction candidate pool | 120 balls faced or bowled |

The pool threshold is deliberately the loosest: finding a player is a different task
from crowning one.

---

## 5. Match-ups — the honest version

A batter–bowler head-to-head is the most requested and most abused statistic in T20.
Across an entire IPL career, a batter typically faces a given bowler **20 to 60
deliveries** — one to ten overs, spread over a decade in which both players changed.

Stryk grades every match-up before showing a single number:

| Grade | Balls | Meaning |
|---|---|---|
| none | 0 | They have not met under these filters. |
| insufficient | < 12 | Not reportable. |
| indicative | 12–29 | One boundary or one dismissal moves every rate materially. |
| readable | 30+ | Still a small sample; read it as a tendency, not a fact. |

The grade sits **above** the statistics, not in a footnote, and the phase and season
tables tint any cell built on fewer than 12 balls.

### Reading against baseline

A raw match-up number is uninterpretable. A strike rate of 110 is a bowler's success
against a 150 batter and a bowler's failure against a 95 one. The match-up page
therefore shows every headline metric next to that batter's own overall figure and the
difference between them. The question is never "what did the batter do", it is "what did
the batter do *differently*".

### What is deliberately absent

No "versus left-arm orthodox" or "versus right-arm pace" splits. Cricsheet ball-by-ball
files contain no bowling style and no bowling arm. Those splits could be faked by
joining against an external register, but coverage would be partial and silently wrong
for exactly the fringe players where the split would be most interesting. A named-bowler
match-up is the honest version of the same question.

---

## 6. Team phase profile

Each phase is shown as the team's run rate, the league's run rate for that phase under
the same filters, and the difference. The team balance radar normalises this: 100 is
league average, batting axes are the team's rate as a share of the league's, and bowling
axes are inverted so that outward always means stronger.

This is league-relative by design. A death-overs run rate of 10.2 means nothing in
isolation — against a league average of 9.6 it is a strength, against 11.0 it is the
reason the team loses close games.

**Where it stops:** it does not adjust for venue or opposition. A team playing half its
matches at a high-scoring ground will read as a stronger batting side than it is.

---

## 7. Auction impact

| Metric | Formula |
|---|---|
| Batting runs above league | `runs − (balls faced × league runs per ball, matched on phase)` |
| Bowling runs saved | `(legal balls × league runs per ball, matched on phase) − runs conceded` |
| Per match | The above ÷ matches played |

The yardstick is phase-matched: a death specialist is measured against the death-overs
league rate, not a global one. The two sides of the ledger use different league rates —
batting against runs off the bat, bowling against runs actually debited to bowlers —
because those are the two quantities each is responsible for.

### Three deliberate refusals

1. **Wickets are not converted into runs.** Doing so requires an assumption about what a
   dismissal is worth, and folding that assumption into a single figure hides it. Wickets
   are reported alongside instead.
2. **Batting and bowling impact are never summed.** They are measured against different
   baselines and are not on a common scale.
3. **No valuation is produced.** Impact measures on-field contribution. It is not a
   price, not a market value, and not an opinion about what a player should cost.
   Auction prices, when present, come from an operator-supplied file and are displayed
   as the historical figures they are.

**Where it stops:** impact is a *total*, so it rewards longevity. A ten-season
contributor will out-score a two-season one who was better per match. Use the per-match
column or filter to recent seasons when that matters — and remember that both are
backward-looking, which is a poor guide to a 29-year-old's next three years.

---

## 8. Scoring shape and the over profile

Two views exist because a rate hides its mechanism.

**Scoring shape** splits every ball faced by what it produced, and reports two different
shares for each outcome: the share of *balls*, and the share of *runs* those balls
produced. The gap between the two is the finding. Virat Kohli hits a four off 12% of his
deliveries and takes 36% of his runs from them; a batter at the same strike rate who
never misses a single has a completely different pair of rings. Both totals reconcile
exactly with the career balls-faced and runs figures on the same page.

**The over profile** breaks the innings into its twenty overs. Phase splits answer "is
this a death-overs player"; this answers *which over*. Bar height is the rate, because
that is the question being asked and a reader takes height as "better"; sample size is
carried by opacity instead, so the two encodings do not compete. An over with fewer than
20 balls has no rate it has earned and is drawn as an empty outline rather than given a
number. For a bowler the scale is inverted, so a tall bar is always the good end.

**Where they stop:** both are career aggregates under the current filters, so a player
who changed their game mid-career shows the average of two different players. Narrow to
recent seasons when that matters.

---

## 9. Plain-language reads

Each player page opens with a few short statements — "Hard to dismiss", "Most dangerous
in the death overs" — before any table. They exist so that a reader who does not do this
for a living gets the gist first.

Three rules keep them honest:

1. Every read carries the figure it came from, so it can be checked against the tables
   below it.
2. Every read is derived from that player's **own** splits. Nothing is compared against
   a league average here, because a read that quietly depends on a baseline is a claim
   the page is not showing you.
3. A read only appears above a minimum sample (120 balls faced or bowled), and the
   phase reads require 60 balls in the phase before that phase can be called a player's
   best or worst.

They are a summary, not a verdict. "Scores quickly" at a 145 strike rate says nothing
about whether that is the right tempo for the role, and the tables are there for that.

---

## 10. The display rule that matters most

**Undefined is never zero.**

A batting average with no dismissals, an economy with no balls bowled, a strike rate off
no balls faced: the API returns `null` and the interface renders an em dash. A zero in
any of those cells would be a false statement about a player, and it is the single
easiest way for an analytics product to quietly lie.
