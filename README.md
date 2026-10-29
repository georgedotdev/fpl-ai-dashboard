# AI FPL Assistant

Paste a Fantasy Premier League team ID and get your situation, then (in later stages) the best transfers, captain, bench order and chip timing, each explained in plain English.

![Architecture](docs/fpl_ai_architecture.svg)

The system is split into a **prediction brain** (how many points will each player score?), an **optimization brain** (given my squad and the rules, what should I do?) and an **explanation layer** (a language model that explains the optimizer's choice and never makes it). They connect through one interface: an expected-points matrix of player × gameweek. Full spec: [docs/fpl_ai_project_spec.md](docs/fpl_ai_project_spec.md). Decisions and their reasons: [DECISIONS.md](DECISIONS.md).

## Status

| Stage | What | State |
|---|---|---|
| 1 | Data layer: team ID → squad, bank, free transfers, chips | **Done (local)** |
| 2 | Optimizer end to end on a baseline predictor (no ML) | **Done (local)**: transfers, captain, bench, chip timing |
| 3 | Trained prediction model behind the same interface | Not started |

## What works now

- `GET /manager/{team_id}` rebuilds a manager's situation from public FPL endpoints only. There's no login and no password.
- Values FPL doesn't publish are **derived and labelled as such**:
  - **Free transfers**: replayed gameweek by gameweek from the transfer history, and checked against FPL's own hit charges. You can correct the result (`PATCH /manager/{team_id}/state`).
  - **Selling prices**: purchase price plus half of any rise, rounded down.
  - **Chips left**: from the chips you've played and the season's chip windows.
- Every rule (budget, squad shape, club limit, transfer cap, hit cost, chip windows) lives in [`backend/app/rules/2026_27.toml`](backend/app/rules/2026_27.toml) and is checked against the live API on every refresh.
- A scheduled ingest stores players, teams, gameweeks and fixtures, plus a daily price snapshot for price trends.
- **Recommendations** (`GET /recommendations/{team_id}?horizon=5`): an integer linear program (HiGHS) plans transfers, hits, captain, starting XI, bench and **chip timing** (Wildcard, Free Hit, Triple Captain, Bench Boost) over the next 1 to 8 gameweeks. It returns the best plan and an alternative, each with its expected gain over doing nothing and the facts behind every move, plus play-or-save advice for every chip still held.
- **Predictions** come from a transparent baseline: form and season scoring rate, × fixture difficulty, × availability (including return dates parsed from injury news). They sit behind one `XPMatrix` interface, so the Stage 3 model can replace them without touching anything else.
- **Explanations** (`GET /recommendations/{team_id}/explanation`): a few plain-English sentences on why, written only from the plan's facts by a **local** language model (Ollama, no API key or per-use cost) or by templates. Every number is checked against the facts in code before it's shown; a draft that fails falls back to the template.
- **No team ID? No problem.** The team box accepts the number or any FPL link; the team is remembered on the device; the page installs to a phone's home screen; and a squad can be **entered by hand** (`/manual/*` endpoints) when the ID can't be found. The FPL app doesn't show team IDs and FPL has no name search, so these are the ways in.
- **Best XI** (`GET /best-xi`): the strongest squad for the next gameweek from every player within the budget, a Free Hit team whatever you own. The home pitch switches between it and your XI.
- **Design:** a dark theme in FPL's own palette, the team on a pitch as FPL-style player cards, and everything else in rows that expand in place. Mockups of the options considered are in `design/mockups/`.
- **Dashboard views:** player list with prices, price changes and xP (`/players`); fixture difficulty ticker (`/fdr`); best captains (`/captaincy`); best players for the coming fixtures (`/picks/best-by-fixtures`).

## Run it locally

You need Python 3.12, Node 20 or later, and Docker.

```bash
docker compose up -d
```

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"   # macOS/Linux: .venv/bin/pip
.venv/Scripts/alembic upgrade head
.venv/Scripts/python -m app.ingest.run
.venv/Scripts/uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

**Optional: local language model for explanations.** Install [Ollama](https://ollama.com), pull a small instruction model (for example `ollama pull llama3.2:3b`), and start the API with `FPLAI_LOCAL_MODEL=llama3.2:3b`. Without it, explanations come from templates.

Open http://localhost:5173 and enter a team ID: it's the number in the address of your FPL Points page. The API docs are at http://localhost:8000/docs.

Tests: `cd backend && .venv/Scripts/pytest`.

## Deploy (free: Cloud Run, Cloudflare Pages, Neon, GitHub Actions)

The hosted site runs the same predictions and optimizer as a local run. The one difference is the "Why" text: it comes from the templates, because there's no local language model on the server (see D-018).

| Part | Where | Cost |
|---|---|---|
| API | Google Cloud Run, built from `backend/Dockerfile` | Free allowance; scales to zero when idle |
| Website | Cloudflare Pages, built from `frontend/` | Free |
| Database | Neon Postgres | Free plan |
| Data refresh | GitHub Actions (`.github/workflows/ingest.yml`) | Free |

The first visit after a quiet spell takes several seconds while the API starts up; after that it's fast.

### 1. Database (Neon)

1. Create a project at neon.tech (a region near the API, e.g. London or Frankfurt).
2. Copy its connection string (`postgresql://…?sslmode=require`).
3. In this GitHub repo: Settings → Secrets and variables → Actions → New repository secret, name `FPLAI_DATABASE_URL`, value the connection string. The scheduled data refresh starts working from its next run (or run "Ingest FPL data" by hand from the Actions tab).

### 2. API (Cloud Run)

1. Create a Google Cloud project, and add a billing account (required even within the free allowance).
2. **Set a budget alert first:** Billing → Budgets & alerts → a £1 budget with an email alert.
3. Cloud Run → Create service → "Continuously deploy from a repository" → connect this GitHub repo, branch `main`, build type **Dockerfile**, source location `/backend/Dockerfile`.
4. Settings:
   - Region: `europe-west2` (London).
   - Authentication: **Allow unauthenticated invocations** (it's a public website).
   - Billing: **request-based** (CPU only while handling requests). Minimum instances `0`, maximum instances `1`.
   - Memory `1 GiB`, CPU `1`, request timeout `60` seconds.
   - Variables:
     - `FPLAI_DATABASE_URL` = the Neon connection string
     - `FPLAI_CORS_ORIGINS` = `["https://<your-project>.pages.dev"]` (fill in after step 3)
     - `FPLAI_CORS_ORIGIN_REGEX` = `^https://([a-z0-9-]+\.)?<your-project>\.pages\.dev$` (so Cloudflare preview links work too)
5. Deploy, then open `https://<service-url>/health`: it should report `"database": "ok"`. Every push to `main` now redeploys the API.

### 3. Website (Cloudflare Pages)

1. Cloudflare dashboard → Workers & Pages → Create → Pages → connect this GitHub repo.
2. Build settings:
   - Root directory: `frontend`
   - Build command: `npm run build`
   - Output directory: `dist`
   - Environment variable: `VITE_API_URL` = the Cloud Run service URL (no trailing slash)
3. Deploy. Every push to `main` now redeploys the site.
4. Put the `*.pages.dev` address into the API's `FPLAI_CORS_ORIGINS` (step 2) and redeploy the API.

### Running it locally with your own model

Nothing changes for local runs. Put `FPLAI_LOCAL_MODEL=llama3.2:3b` (or any model you've pulled with Ollama) in `backend/.env`, start Ollama, and run the API as in "Run it locally": the "Why" text is then written by your model. The hosted site never sets it.

## Layout

```
backend/app/
  fpl/        the only code that talks to FPL: caching, rate limiting, retries, validation
  rules/      per-season game rules + checks against the live API
  manager/    ManagerState, its builder, and the free-transfer / chip / selling-price derivations
  prediction/ the prediction brain: XPMatrix interface + the baseline predictor
  optimization/ the optimization brain: the ILP solver and plan building
  explanation/ the explanation layer: facts, templates, local model, number check
  insights.py dashboard views (player list, fixture ticker)
  db/         tables (SQLAlchemy); migrations in backend/migrations (Alembic)
  ingest/     scheduled refresh + daily price snapshot (python -m app.ingest.run)
  main.py     HTTP API (FastAPI)
frontend/     React + Vite + TypeScript + Tailwind
.github/      CI (tests + build) and the scheduled ingest
```

## Honest limits

- **Free transfers and selling prices are estimates.** The exact values are only visible when logged in to FPL. The derivation re-syncs whenever FPL's hit charges disagree with it, and you can always override it.
- **Transfers made since the last deadline aren't public** until the next deadline passes, so the squad shown is the one at the last deadline.
- **The baseline predictor is deliberately simple.** Its fixture multipliers are hand-set, it knows nothing about underlying stats, minutes or set pieces, and FPL's team strength ratings are empty this season. Stage 3 replaces it with a trained model.
- **The FPL API is unofficial** and changes without notice. Everything goes through one validated client, so a change fails loudly in one place.
