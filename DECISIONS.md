# Decisions

A running log of project decisions and the reasoning behind them, newest at the bottom. Each entry records the context, what was decided, why, what else was considered, and what follows from it. Spec references point to `fpl_ai_project_spec.md`.

---

## D-001: Tech stack

- **Date:** 2026-10-25
- **Status:** Decided (closes spec §8.1; partly closes §8.2)

**Context.** The prediction (ML) and optimization (integer linear programming) libraries we need are Python. The product must be deployed live cheaply, needs scheduled ingestion jobs (data refreshes, daily price snapshots), and is a portfolio piece, so a polished, recognisable stack matters.

**Decision.**

| Layer | Choice |
|---|---|
| Backend | Python + FastAPI (Pydantic for request/response and FPL response validation) |
| Frontend | React + Vite + TypeScript, styled with Tailwind CSS |
| Database | PostgreSQL |
| Scheduled jobs | GitHub Actions cron workflows that run the Python ingestion scripts against the database |

**Why.**

- Python on the backend keeps the ML and optimizer in the same process as the API: no second service or language boundary.
- FastAPI + Pydantic gives typed models and schema validation, which is what the "one FPL client module with response validation" rule needs, plus free OpenAPI docs a reviewer can click through.
- React + TypeScript is the frontend stack recruiters recognise most readily, and gives full control over a clean, mobile-friendly dashboard.
- Postgres is the standard relational choice and has free hosted tiers.
- GitHub Actions cron is free and lives in the repository, so the schedule is versioned and visible alongside the code.

**Alternatives considered.**

- *Single FastAPI app with server-rendered pages (Jinja + HTMX + Tailwind).* One language, one deploy, fastest to Stage 2; rejected because it gives a weaker frontend signal and makes rich interactive views (sortable tables, fixture ticker) harder.
- *FastAPI on Google Cloud Run + Cloud Scheduler.* Near-zero cost and good cloud credibility; rejected because of extra setup (Docker, IAM, secrets) and cold starts working against the "results within a few seconds" goal.

**Consequences.**

- Two deploy targets (API and frontend). The API must allow CORS from our own frontend origin only.
- The cron jobs run on GitHub's machines, so the database must be reachable from the internet: in practice, a hosted Postgres.
- GitHub's scheduled workflows are best-effort: runs can start late under load, and GitHub disables schedules in public repositories after 60 days without repository activity. Ingestion must therefore be idempotent and tolerate a missed or late run.
- **Still open (spec §8.2):** which hosts to use for the API and the frontend. The database host is decided in D-004.

---

## D-002: Repository location and local tooling

- **Date:** 2026-10-25
- **Status:** Decided

**Decision.** The code lives in a git repository at `C:\Users\georg\dev\fpl-ai`, outside OneDrive. The planning documents are copied into `docs/`. The backend uses Python 3.12 in a plain `venv` with `pyproject.toml`. The frontend uses npm. The local database is Postgres 16 in Docker (`docker-compose.yml`).

**Why.** OneDrive syncing `node_modules` and `.venv` (tens of thousands of files) causes file locks during installs and wastes sync bandwidth. A plain `venv` needs nothing new installed. Docker gives everyone the same database version locally.

---

## D-003: No user accounts; state keyed by FPL team ID

- **Date:** 2026-10-25
- **Status:** Decided (closes the accounts half of spec §8.8; mini-league features are still open)

**Decision.** There is no sign-up or login. User corrections (for now, the free-transfer count) are stored against the FPL team ID.

**Why.** Pasting a team ID is the whole demo; a sign-up step would lose recruiters before they see anything. FPL team IDs are already public.

**Consequences.** Anyone can set an override for any team ID. That's acceptable because an override only changes what *that* page shows, and overrides only apply to the gameweek they were made for (see D-008). Revisit this if overrides ever affect anything shared.

---

## D-004: Neon for hosted Postgres

- **Date:** 2026-10-25
- **Status:** Decided (partly closes spec §8.2). Not yet set up: this needs the owner to create the account.

**Decision.** Production data lives in Neon's hosted Postgres. GitHub Actions (D-001) writes to it on a schedule.

**Why.** It has a free tier, standard Postgres, and is reachable from GitHub's runners. Setting it up during Stage 1 means daily price snapshots start building up now: price history can't be backfilled later.

**Consequences.** The connection string is a GitHub Actions secret (`FPLAI_DATABASE_URL`) and is never committed. The engine uses `pool_pre_ping`, because Neon closes idle connections.

---

## D-005: Money is stored as whole numbers of tenths of £1m

- **Date:** 2026-10-25
- **Status:** Decided

**Decision.** Every price, bank and budget value is an integer in FPL's own unit (`now_cost: 85` is £8.5m), from the API client through to the database and the HTTP API. Only the frontend formats it as £m.

**Why.** The selling-price rule ("half of any rise, rounded down to £0.1m") and the budget constraint are exact integer arithmetic. Floats would introduce rounding errors in exactly the places a reviewer will check.

---

## D-006: Game rules in a TOML file, checked against the live API

- **Date:** 2026-10-25
- **Status:** Decided

**Decision.** Each season's rules live in `backend/app/rules/<season>.toml`, versioned in git. The spec's schema sketch suggested a `season_rules` table; a file in the repo is simpler and gets reviewed like code. FPL's `bootstrap-static` exposes some rules (squad size, club limit, budget, sell-on fee, banked-transfer cap, position counts, chip windows). Every ingest and every manager request compares these against the config and reports any mismatch as a warning. **Chip windows come from the live API** when it lists them; the config is the fallback.

**Why.** FPL changes rules most summers. Checking automatically turns a silent rule change into a visible warning.

**Spec corrections found while doing this:**

- The spec says the first set of chips "expires at the GW19 deadline". The API says the first set is playable **in** GW19 (`stop_event: 19`), and Wildcard and Free Hit open from GW2, not GW1.
- The spec says the API gives only the current price plus this gameweek's change. It now also returns `price_change_percent`, `price_change_hourly_rate` and `price_change_projections`. These are undocumented; to be investigated before we show them.
- In 2026/27 every team's `strength` is `null`, and its attack and defence strengths are `0`. They can't be used as model features; fixture difficulty is the usable signal.

---

## D-007: How free transfers are derived

- **Date:** 2026-10-25
- **Status:** Decided

**Decision.** We replay the manager's season from their first gameweek:

1. They have one free transfer after the first gameweek.
2. Each gameweek: subtract the transfers made, add one, and cap the total at 5.
3. In Wildcard and Free Hit weeks, banked transfers are kept.

FPL's recorded hit charge for each gameweek is used as a check. If FPL charged a different number of hits than our count implies, we re-sync to what the charge proves and record it as a warning.

**Open detail (re-verify):** whether the usual +1 still arrives after a Wildcard or Free Hit week. It's a config flag (`gains_free_transfer = true`), and the derived value's note says when it was relied on.

**Why.** The exact number is login-only. The hit-charge check is the strongest public evidence available, and the user can always override.

---

## D-008: User overrides apply only to the gameweek they were made for

- **Date:** 2026-10-25
- **Status:** Decided

**Decision.** A free-transfer override stores the gameweek it was set for. Once that deadline passes, it's ignored with a warning, and the derived value is shown again.

**Why.** A correction for GW9 is wrong by definition in GW10. Silently carrying it forward would make the app confidently wrong.

---

## D-009: HiGHS (via `highspy`) as the optimization solver

- **Date:** 2026-10-25
- **Status:** Decided (replaces the spec's suggestion of PuLP or OR-Tools)

**Decision.** The optimizer builds its integer linear program with `highspy`, the Python interface to the HiGHS solver.

**Why.** PuLP 4.x (the current release) no longer ships a solver and has rewritten its modelling API; pinning PuLP 2.x would mean depending on an old line from day one. HiGHS is a leading open-source MIP solver (MIT licence), installs as one wheel, and its Python API builds models as readable expressions. On live data one solve takes about 0.8 s.

---

## D-010: Planning horizon defaults

- **Date:** 2026-10-25
- **Status:** Decided by the owner (closes spec §8.7)

**Decision.** Transfers are planned 5 gameweeks ahead by default; captaincy looks 1 gameweek ahead. Later gameweeks are weighted ×0.85 per week. The user can choose 1–8 gameweeks in the dashboard.

**Why.** Five weeks is long enough to see fixture swings and returning injuries, and short enough that predictions still mean something. It's the standard among FPL planning tools.

---

## D-011: Stage 2 baseline predictor

- **Date:** 2026-10-25
- **Status:** Decided

**Finding.** FPL's `ep_next` is exactly form × chance of playing (all 321 available players with form matched). It ignores fixtures and covers one gameweek only, so it can't drive multi-week planning on its own.

**Decision.** `xP = scoring rate × availability × Σ fixture factor`:

- **Scoring rate:** 50% form, 50% season points per team match. Using team matches (not appearances) builds in rotation risk.
- **Availability:** FPL's chance of playing for the next gameweek. For later gameweeks, the return date parsed from the news text ("Expected back 8 Nov", "Suspended until 1 Nov"). Players out with no return date stay out; doubtful players recover after a week.
- **Fixture factor:** a hand-set multiplier per FPL difficulty (1: ×1.2 … 5: ×0.8). Blank gameweeks score 0; doubles are summed.

**Why.** It's transparent and can be checked by hand. The multipliers are a guess, labelled as one; Stage 3 replaces the whole predictor behind the same `XPMatrix` interface. Injuries are weighed through availability, never through "if injured, sell" rules.

---

## D-012: Optimizer formulation and tuning

- **Date:** 2026-10-25
- **Status:** Decided. The numbers below are tunable defaults, not research results.

**Decision.** One multi-gameweek integer program decides squad, starting XI, captain and transfers for each gameweek in the horizon. Free transfers are modelled exactly: banked up to the cap, hits only for transfers beyond the free ones, and no paying a hit to bank a transfer. Budget is bank plus estimated selling prices. Club limit and squad/XI shapes come from `season_rules`.

- Bench players' points count at a small weight (0.1 outfield, 0.03 goalkeeper), because they only score through auto-subs.
- Each free transfer still banked at the end of the horizon is worth 1.5 points; without this, the plan would spend every transfer in the last week on tiny gains.
- The candidate pool is owned players, plus the best 6 GKP / 15 DEF / 15 MID / 10 FWD by discounted xP, plus the 3 cheapest available per position. On live data, widening DEF/MID to 25 gave the identical plan at twice the solve time.
- Prices are assumed constant over the horizon.
- One alternative plan is found by forbidding the best plan's first-week purchases and solving again (two alternatives made a cold request too slow). A "no transfers, no chips" solve gives each plan's expected gain.
- Vice-captain and bench order are chosen after the solve, by expected points.
- Results are cached for 10 minutes per identical input. A cold request takes about 5–6 s; a cached one 0.25 s.

---

## D-013: Chip timing inside the optimizer, with an opportunity cost

- **Date:** 2026-10-25
- **Status:** Decided. The par values are hand-set defaults, not fitted.

**Decision.** Chips are decision variables in the same integer program as transfers, not a separate scenario loop:

- **Triple Captain:** the captain's points count once more.
- **Bench Boost:** the bench's points count in full.
- **Wildcard:** that week's transfers are free and banked free transfers are untouched.
- **Free Hit:** that week gets its own squad (same budget, same squad and club rules), and the base squad is frozen and returns the week after.

The rules that limit chips come from `season_rules`: each chip's window, at most one chip per gameweek, and no back-to-back Free Hits. Which chip behaves how is also config (`free_transfer_chips`, `reverting_chips`, `captain_bonus_chips`, `bench_boost_chips`).

**Opportunity cost.** Inside a 5-week horizon any chip gain looks free, so without a counterweight the solver would play every chip at once. Playing a chip therefore costs its *par* value, roughly what it's worth if saved for a good week later in its window:

| Chip | Par (xP) |
|---|---|
| Triple Captain | 12 |
| Bench Boost | 12 |
| Free Hit | 12 |
| Wildcard | 20 |

The full cost applies while 4 or more gameweeks of the window remain after the week; it shrinks linearly to 0 in the window's last gameweek. So a chip about to expire is used rather than wasted.

**Why scenarios weren't used.** The spec suggested comparing "play this week" against "save it". That's what the opportunity cost does, inside one solve instead of one solve per chip per week (20 solves was far too slow).

**Tuning note.** With a Triple Captain par of 10, the solver played it on an ordinary single gameweek (the best captain was worth 10.1 xP). Saved Triple Captains usually land on double gameweeks, so the par was raised to 12.

**Output.** Every chip still held gets one line of advice:

- **Play it this week / in GWx:** shown with its expected gain. For Triple Captain and Bench Boost the gain is computed directly; for Wildcard and Free Hit it's computed by re-solving without the chip.
- **Save it.**
- **Not playable in this horizon.**

**Limits.** A Wildcard's benefit lasts beyond the horizon, so a 5-week view undervalues it. The planner mostly recommends one when a squad is badly broken or the window is closing.
