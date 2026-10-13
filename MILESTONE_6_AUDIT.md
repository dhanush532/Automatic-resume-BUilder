# CareerPilot audit — 2026-10-13

## Baseline (before changes)

- Existing Next.js / FastAPI / PostgreSQL architecture retained. This directory has no Git repository.
- Frontend: lint, TypeScript check, and production build passed.
- Backend: Ruff passed; 25 pytest tests passed (one upstream TestClient deprecation warning).
- PostgreSQL initially unavailable because Docker Desktop and the existing container were stopped. Started both, without replacing volumes/configuration. Application `SELECT 1` returned `1`; Alembic reported `20260925_0005 (head)`.
- Initial database checks timed out; the successful results above are reruns after restoring PostgreSQL.
- npm production audit found 4 vulnerable dependency entries: 1 critical and 3 high. Next.js 15.2.4 requires an update; same-major patch target confirmed from npm: 15.5.27.

## Findings

1. Authentication, passport CRUD, first-save master resumes, templates, versions, preview/export, source-neutral jobs and saved jobs exist and have backend tests. Passing tests do not establish production readiness.
2. No real job source is configured. Existing source rows alone are incorrectly treated as proof of an available adapter. No sync operator command, durable source health, or rate limit exists.
3. Freshness is not enforced on reads. Missing listings lose verification only when explicitly performing a complete sync. No durable verification history exists.
4. Job identity normalization lowercases case-sensitive external IDs and URL paths and removes meaningful URL punctuation. Company normalization drops non-ASCII names. Repeated skills can violate uniqueness.
5. Tests commit into the configured database and some job assertions assume it is empty. Before live ingestion, isolate test transactions and scope job assertions.
6. Passport/resume mutation routes lack the explicit same-origin guard used by auth/saved jobs. Cached SQLAlchemy engine reuse is missing.
7. Matching is a preliminary heuristic, not validated eligibility or semantic ranking; salary currency/period handling and score explanation need M7 work.
8. Master resumes are created on initial profile entry, not continuously synchronized. AI is an unavailable-provider boundary; full claim tracing and Unicode/ATS export evaluation remain M8 work.
9. Real mail delivery, OAuth configuration, application workflows, notification delivery, consent/revocation, privacy export/deletion, operational monitoring, and deployment controls remain incomplete. No real submission is permitted in this milestone.
10. Frontend has static checks but no existing automated browser suite. Native PostgreSQL was not required; existing Docker installation was used.

## Checkpoint

Local only: `.checkpoints/milestone6-20261013/source-complete.zip` (113 source/config/example files; generated dependencies and secret environment files excluded).

SHA-256: `02BD5A3A780C418CE858AAA5C439BA66BEB9A0118D2353C55F7FDFB648EB6A6E`.

Database: `.checkpoints/milestone6-20261013/database.dump` (PostgreSQL custom-format dump; contains private data; do not publish).

SHA-256: `B1F2BA6FCB73A5E57B8DFA4CDF70F6BFFC4CA67BDA87B2B570FE8BAEC64F8684`.

The earlier `source.zip` attempt contains only one file and is NOT the source checkpoint. Use `source-complete.zip`. Restore archives into a separate directory/database first; never overwrite live user data without approval. Secret `.env` files remain untouched in their original locations.

## Source decision

Use Arbeitnow's free documented API for initial discovery (mostly Germany/Europe, not global coverage), preserve its listing URLs and display attribution. No API key, paid service, browser scraping, or application submission.

- API documentation: https://www.arbeitnow.com/blog/job-board-api
- API permission/attribution terms (section 11): https://www.arbeitnow.com/terms
- Remotive was considered but not selected: its public API forbids gating listings behind signup/email collection, incompatible with existing authenticated browsing: https://github.com/remotive-com/remote-jobs-api/blob/main/README.md
- Security advisory: https://nextjs.org/blog/security-update-2025-12-11

Provider availability is evidence of a listing, not independent proof of employer identity. Never label aggregated listings guaranteed legitimate or automatically submitted.
