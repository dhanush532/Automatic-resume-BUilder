# CareerPilot

Public deployment: [DEPLOYMENT_VERCEL.md](DEPLOYMENT_VERCEL.md). Import `frontend` and `backend` as separate Vercel projects; PostgreSQL, Redis and the existing Celery worker/scheduler also need hosted services. Never upload `.env` or database backups.

Authentication/email upgrade setup: [AUTHENTICATION_AND_EMAIL.md](AUTHENTICATION_AND_EMAIL.md). Phone is now optional and non-unique, local numbers use a selected country, and registration uses browser-bound email OTPs. Redis/Celery process an encrypted database outbox. Real Resend sender/key and OAuth app credentials still need configuration; these integrations are not claimed live-verified.

CareerPilot is a career workspace built around a user-owned **Career Passport**. Milestones 1–5 are preserved; M6 adds Arbeitnow discovery, freshness and verification evidence. See [MILESTONE_6_AUDIT.md](MILESTONE_6_AUDIT.md), [ROADMAP.md](ROADMAP.md), and [MILESTONE_6_REPORT.md](MILESTONE_6_REPORT.md). This is local development software, not a production-ready autonomous application agent.

## Prerequisites

- Node.js 20+ and npm
- Python 3.11+
- Docker Desktop (recommended for PostgreSQL) or a compatible PostgreSQL 16+ server

## Run locally

1. For a NEW checkout only, copy `.env.example` to `.env`; never overwrite an existing `.env`. Set a unique authentication secret before any production-like use.
2. If absent, install Docker Desktop for Windows with its WSL2 backend and complete setup. Start Docker Desktop; verify `docker info`. Start PostgreSQL with `docker compose up -d postgres`, or `docker compose start postgres` for the existing stopped container. Never use `docker compose down -v` against your data.
3. In `backend`, create/install the Python environment with `uv sync --all-groups`.
4. Apply schema migrations with `uv run alembic upgrade head`.
5. Start the API with `uv run uvicorn app.main:app --reload --port 8000`.
6. In `frontend`, run `npm install`, then `npm run dev`.

The UI is at `http://localhost:3000`; API documentation is at `http://localhost:8000/api/v1/docs`. Keep both server terminals running. Connection refused means a server is not listening. Health reports configuration, not connectivity. Existing verified accounts can browse `/jobs` and `/saved-jobs`. Mail delivery remains unconfigured; newly registered real users cannot receive verification email yet. Do not bypass their verification.

Use one frontend preview on port 3000. `npm run dev` uses `.next-dev`; `npm run build` / `npm run start` use `.next`, so a development preview cannot overwrite production JavaScript assets. Stop the current port-3000 preview before switching modes. Social icons remain visible if the API is unavailable; retry the availability check after the backend is restored. Disabled providers require server-side credentials, not a browser login workaround.

## Authorized discovery (M6)

Set `JOB_SOURCE_CONFIG=arbeitnow` in the EXISTING root `.env` (blank disables ingestion). Keep `DATABASE_URL` unchanged. In `D:\resume\backend` run:

```powershell
uv run alembic upgrade head
uv run alembic current
uv run python -m app.sync_jobs arbeitnow
```

The local environment was enabled during M6. The operator command reads the [free public API](https://www.arbeitnow.com/blog/job-board-api), with attribution required by [API terms](https://www.arbeitnow.com/terms). No scraping, personal-data transmission, paid calls or application submissions. Listing hosts are explicitly allowlisted: `www.arbeitnow.com`, `www.arbeitnow.co.uk`, `www.arbeitnow.fr`, `www.arbeitnow.ch`; HTTP requests only go to the `.com` API.

Sync is manual; no scheduler is installed. Successful syncs have a six-hour cooldown; failures a five-minute backoff. A durable ten-minute lease prevents concurrent runs. Each batch is bounded to three pages, five MB per page, and 5,000 unique jobs. Validation/fetch failures retain prior jobs. Partial snapshots never imply unseen jobs are closed. Do not repeatedly retry provider blocks.

`JOB_FRESHNESS_HOURS=72` sets read-time freshness. Stale, expired and suspicious rows and saved-job history remain stored. Availability and trust are separate; this aggregator adapter never assigns `VERIFIED`. Employer identity and final application destinations are not independently verified. Stale/suspicious jobs have no enabled application link. Missing structured salary/skills/eligibility stay unknown. Coverage is initially European, not comprehensive. Same-source deduplication preserves IDs/saves; cross-platform canonical linking is deferred.

## Quality checks

```text
frontend: npm run lint
frontend: npm run typecheck
frontend: npm run build
backend:  uv run ruff check .
backend:  uv run pytest
backend:  uv run alembic check
frontend: npm audit --omit=dev
```

Existing APIs and routes are preserved. `GET /api/v1/jobs/sources` distinguishes configured/enabled adapters and shows source health. Job responses add trust, manual application mode and link availability. No public sync endpoint exists. Email/reset delivery and Google/GitHub/LinkedIn authentication are implemented but require real provider credentials before use. External AI and application submission remain unconfigured/unimplemented. M7 has not started.

Tests use real development PostgreSQL with per-test transactions/savepoints; application commits are rolled back. Mock integrations never submit real applications. Local `.checkpoints/` archives/database dumps are private and ignored; never publish them.

See [ARCHITECTURE.md](ARCHITECTURE.md), [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md), [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), and [SECURITY.md](SECURITY.md) for the current design and boundaries.
