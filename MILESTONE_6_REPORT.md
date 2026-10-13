# Milestone 6 handoff — 2026-10-13

## MILESTONE

6 — Repository audit and job source integration.

## STATUS

Implemented and verified at database, API regression, frontend static-check/build, and local HTTP levels. The full authenticated browser journey remains untested. M7 has not started. This is not a production release or a guarantee of employer legitimacy.

## FEATURES IMPLEMENTED

- Audited the existing repository without rebuilding; recorded baseline and M6–M13 dependencies/acceptance criteria.
- Created private source and PostgreSQL checkpoints before changes. See `MILESTONE_6_AUDIT.md` for paths, checksums and restoration cautions.
- Enabled the documented free Arbeitnow API through the existing root `.env` and settings. No credentials, candidate data, scraping or applications are sent.
- Added an operator sync command, explicit country-host allowlist, bounded fetch/validation, durable lease, six-hour success cooldown and five-minute failure backoff. Failed batches retain previous jobs; partial snapshots never close missing listings.
- Live sync succeeded and persisted **737 unique listings**: **736 ACTIVE / LIKELY_LEGITIMATE**, **1 UNVERIFIED / SUSPICIOUS** (a fallible payment-language flag). There are **737 verification evidence records** and **0 duplicate identity keys**. These counts remained unchanged after the final tests.
- Enforced freshness on list/detail/saved/recommendation reads, with explicit trust separate from availability. Stale/expired/suspicious rows remain stored; unsafe or noncurrent application links are disabled.
- Fixed case-sensitive job identities, Unicode normalization, repeated-skill ingestion, non-finite salary values and unsafe outbound URLs. Existing same-source external IDs resolve first, retaining legacy job IDs and saves.
- Displayed source attribution, sync health, trust assessments, manual application wording, save errors and sign-in guidance. API validation errors are converted into readable messages.
- Reused one SQLAlchemy engine with bounded connection timeout; applied the existing explicit-origin guard across API mutations; escaped percent signs in Alembic URL configuration.
- Corrected model metadata to match pre-existing indexes, OAuth uniqueness and timezone-aware resume timestamps. No historical migration was edited or index removed.
- Isolated backend tests using outer transactions/savepoints so application commits and cleanup roll back. Scoped job assertions to tolerate the populated catalog.
- Updated Next.js/React and compatible PostCSS/ESLint dependencies; production audit now reports zero known vulnerabilities.

## FILES CREATED

| File | Purpose |
| --- | --- |
| `MILESTONE_6_AUDIT.md` | Baseline, findings, source decision and checkpoint details |
| `ROADMAP.md` | Dependency-aware M6–M13 plan |
| `MILESTONE_6_REPORT.md` | This evidence and handoff |
| `backend/app/services/arbeitnow.py` | Authorized, bounded public API adapter and plain-text normalization |
| `backend/app/services/job_verification.py` | Shared freshness/availability/trust policy |
| `backend/app/sync_jobs.py` | Operator-only sync CLI |
| `backend/alembic/versions/20261013_0006_job_discovery.py` | Additive source health and verification evidence migration |
| `backend/tests/test_job_discovery.py` | Feed, security, freshness, deduplication and failure regression tests |
| `frontend/components/jobs/source-health.tsx` | Attribution, sync health and sign-in notice |

Private generated checkpoint archives/database dump and local `.runtime` server logs were also created; both directories are ignored. `source-complete.zip` is the valid source checkpoint; the earlier one-file `source.zip` is not.

## FILES MODIFIED

| File(s) | Why |
| --- | --- |
| `.env` | Changed only `JOB_SOURCE_CONFIG` from blank to `arbeitnow`; credentials and `DATABASE_URL` retained |
| `.env.example` | Documented source opt-in and freshness setting |
| `.gitignore` | Excluded private checkpoints and runtime logs |
| `backend/app/core/config.py` | Validated source setting and freshness window in the existing settings system |
| `backend/app/core/database.py` | Cached engine and five-second connection timeout |
| `backend/alembic/env.py` | Safely escaped `%` for ConfigParser while retaining application settings |
| `backend/app/api/router.py` | Shared explicit-origin mutation guard |
| `backend/app/models/jobs.py` | Source health fields, trust status, freshness index and verification-event model |
| `backend/app/models/user.py` | Declared existing indexes and OAuth uniqueness |
| `backend/app/models/passport.py` | Declared existing user FK indexes |
| `backend/app/models/resume.py` | Matched existing timezone-aware timestamps |
| `backend/app/services/job_sources.py` | Stable identity/normalization, safe URLs, deduplication, lease/cooldown and atomic sync/evidence |
| `backend/app/schemas/jobs.py` | Added trust, manual mode, outbound-link availability and source health fields |
| `backend/app/api/routes/jobs.py` | Applied freshness consistently and reported actual adapter configuration |
| `backend/tests/conftest.py` | Rollback/savepoint protection and dependency overrides for all test clients |
| `backend/tests/test_jobs.py` | Source-scoped queries and populated-catalog-safe assertions |
| `backend/pyproject.toml`, `backend/uv.lock` | Declared existing HTTP client as a runtime dependency |
| `frontend/components/jobs/jobs-page.tsx` | Trust/attribution/health, link restrictions, save errors and corrected failed-load state |
| `frontend/lib/api.ts` | Readable structured validation errors |
| `frontend/package.json`, `frontend/package-lock.json` | Next.js 15.5.27, React/React DOM 19.0.8, ESLint 9.39.5 and patched PostCSS 8.x override |
| `frontend/eslint.config.mjs` | Excluded framework-generated `next-env.d.ts`; application source remains linted |
| `frontend/next-env.d.ts` | Automatically regenerated by Next.js to include route types; not manually authored |
| `README.md` | Local startup, provider enablement, sync operation and limitations |
| `ARCHITECTURE.md` | M6 service/transaction boundaries |
| `DATABASE_SCHEMA.md` | New schema fields/events and metadata corrections |
| `IMPLEMENTATION_PLAN.md` | Linked the current roadmap and corrected historical live-source status |
| `SECURITY.md` | Actual M6 controls and remaining deployment/security boundaries |

## DATABASE MIGRATIONS

`uv run alembic upgrade head` succeeded against real PostgreSQL. Current revision is `20261013_0006 (head)`. `uv run alembic check` reports **No new upgrade operations detected**. The original five migrations were compared with the source checkpoint and remain unchanged.

No existing user data or job history was deleted. Two exact temporary accounts created during an early failed isolation run were retained and reversibly disabled. Automatic approval review rejected their deletion under the user's preservation rule; the safer disable operation succeeded. Subsequent test data rolls back automatically.

## API ENDPOINTS

Existing authenticated routes remain intact. Extended responses on `/api/v1/jobs`, `/jobs/{id}`, `/saved-jobs`, `/job-recommendations` include effective freshness/trust and manual link availability. `/api/v1/jobs/sources` adds configured/enabled state and latest sync health. Company and matching endpoints remain available. Sync runs through `uv run python -m app.sync_jobs arbeitnow`; no public ingestion endpoint was added.

## TESTS EXECUTED / TEST RESULTS

| Check | Actual final result |
| --- | --- |
| Application SQLAlchemy `SELECT 1` command | Printed `1` |
| `uv run alembic upgrade head` | Exit 0 |
| `uv run alembic current` | `20261013_0006 (head)` |
| `uv run alembic check` | No new upgrade operations detected |
| `uv run pytest` with live catalog present | **55 passed**, one upstream TestClient deprecation warning, 15.84 seconds |
| `uv run ruff check .` | All checks passed |
| `npm run lint` | Exit 0 |
| `npm run typecheck` | Exit 0 |
| `npm run build` | Exit 0, production routes compiled/generated |
| `npm audit --omit=dev` | Found 0 vulnerabilities |
| Live `python -m app.sync_jobs arbeitnow` | Success, ingested 737, complete snapshot false |
| Persisted catalog/evidence/duplicate checks after tests | 737 jobs, 737 events, 0 duplicate identities |
| Local `/jobs` HTTP request | 200 |
| API health with frontend Origin | 200, allow-origin `http://localhost:3000`, credentials `true` |
| Browser smoke | Jobs UI rendered with attribution and filters; signed-in flow was not completed; tab binding later failed |

Earlier failures were diagnosed and rerun: stopped Docker caused connection timeouts; unexpected provider country links caused a fully rolled-back batch; a test assumed its dated job must appear in the recommendation pool; generated Next.js declarations triggered source lint. Final successful results above supersede those failed attempts. Backend matching for the fixture is independently exercised; recommendation assertions check active results and score ordering without assuming an empty database.

## SECURITY CHECKS

Tests cover provider 301/403/429/500 errors, no provider cookies/authorization, safe fixed-host pagination, private/credential-bearing/unsafe URLs, lookalike domains, text extraction, payment flags, failed-batch preservation, partial snapshot behavior, cooldown/lease/disabled source blocking, freshness/expiry, suspicious-job exclusion, source configuration and cross-site passport/resume mutations. Existing ownership/auth/session/profile/resume tests passed. Postgres best-practices guidance informed short sync transactions and indexes.

The full development dependency audit still reports **9 entries (7 high, 2 moderate)** through build-tool dependencies including braces, Tailwind, ESLint's Next plugin and selector parsers. No forced framework/Tailwind major upgrade was performed. Production audit is clean, but this does not eliminate future vulnerabilities. Full hardening remains M12.

## KNOWN LIMITATIONS

- One provider, initially European coverage; three-page batches do not cover the entire catalog. Source freshness is evidence of presence, not independent employer verification. Payment flags can be false positives. Provider authorization/terms must be reviewed again before public deployment.
- Sync is operator initiated; no recurring scheduler/worker was installed. Run after the configured cooldown; provider schema/host changes fail closed. With sync stopped, rows become stale after 72 hours by default.
- Deduplication is verified for the existing same-source identity model. Cross-platform canonical linking and application-level duplicate prevention remain later work.
- The existing recommender uses only 500 recent jobs and preliminary heuristics. Hard eligibility/semantic ranking/evaluation remain M7. Missing source salary/skills/qualifications remain unknown.
- Automatic first-save master resumes are preserved; continuous synchronization, claim tracing, configured AI and ATS/Unicode export validation remain M8.
- Real mail delivery, OAuth, application execution and notifications remain unavailable. Use an existing verified account for protected pages; newly registered real users cannot receive verification mail yet.
- Authenticated API routes were regression-tested; a complete signed-in browser journey, responsive/accessibility matrix and automated frontend suite were not established in M6. The browser tool lost its tab binding during the final smoke check.
- One upstream TestClient warning and the listed development dependency advisories remain. Checkpoint restore was not rehearsed against a separate database; backups were created and hashed.
- Existing Docker Compose credentials are development defaults; controlled deployment still needs secrets/TLS/operational hardening. There is no Git repository, so the local checkpoint is the recovery baseline.

## NEXT MILESTONE

M7 — Intelligent job matching, after separate instruction to proceed. See `ROADMAP.md` for its files, data changes, tests and acceptance criteria.

## LOCAL PREVIEW

Frontend: http://localhost:3000/jobs — sign in through http://localhost:3000/login using an existing verified account.

Backend documentation: http://localhost:8000/api/v1/docs.

The local servers were started as hidden loopback processes and verified with HTTP requests. If they stop or the computer restarts, follow `README.md` to restart Docker/PostgreSQL and both server terminals.
