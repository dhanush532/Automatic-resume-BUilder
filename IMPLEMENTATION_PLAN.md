# CareerPilot implementation plan

Milestones 1–5 below are historical. [ROADMAP.md](ROADMAP.md) supersedes the old future numbering with M6–M13. Current evidence: [MILESTONE_6_AUDIT.md](MILESTONE_6_AUDIT.md) and [MILESTONE_6_REPORT.md](MILESTONE_6_REPORT.md).

## Milestone 1 — Foundation

- [x] Empty repository inspected; no user code or database setup existed.
- [x] Next.js, TypeScript, Tailwind, and reusable UI primitives created.
- [x] FastAPI, Pydantic settings, SQLAlchemy model base, and safe health endpoint created.
- [x] PostgreSQL Docker configuration and Alembic baseline migration created.
- [x] Environment contract and core architecture/database/security documentation created.
- [x] Provider-neutral background-job interface declared without pretending a worker is configured.
- [x] Dependencies installed; linting, type checks, backend tests, production build, migration SQL rendering, and local runtime smoke tests passed.

## Completed: Milestone 2 — Authentication and sessions

- [x] Registration validation and normalization for full name, email, username, E.164 phone, password confirmation, and terms acceptance.
- [x] Argon2id password hashing and generic credential failures.
- [x] Server-side persistent sessions with HMAC-hashed tokens, expiry, activity refresh, revocation, current/logout-other/logout-all flows, and HTTP-only SameSite cookies.
- [x] Email-verification/password-reset token services with expiry and one-time consumption; no delivery is claimed without an email provider.
- [x] Security events, ownership-scoped session/event routes, account-deletion/OAuth-disconnect foundations, login rate limiting, and same-site mutation checks.
- [x] Google OAuth provider interface without a simulated provider.
- [x] Auth screens, verification/reset states, and security-settings sessions/history UI.
- [x] Real PostgreSQL migration and automated API tests completed.
- [ ] Production operational setup: set a unique `AUTH_SECRET`, configure HTTPS cookie settings, install a shared rate-limit store, and configure an authorised email/OAuth provider.

## Completed: Milestone 3 — Career Passport

- [x] Normalized PostgreSQL Passport schema and live Alembic migration `20260925_0003_career_passport`.
- [x] Authenticated aggregate Passport endpoint plus owner-scoped CRUD for profile, preferences, links, education, skills, experience, projects, certifications, courses, achievements, languages, and open-source contributions.
- [x] Server-side ownership checks, relationship validation, URL/date/salary/enum validation, uniqueness constraints, and destructive delete behavior.
- [x] Responsive Passport page with editable sections, loading/empty/error/success states, accessible labels, completeness indicator, and delete confirmation.
- [x] Integration tests for CRUD, validation, duplicate handling, unauthenticated access, User A/User B isolation, and deletion behavior.
- [x] Real PostgreSQL migration, backend tests/Ruff, and frontend lint/typecheck/build verification.

## Completed: Milestone 4 — Resume System

- [x] Normalized PostgreSQL migration `20260925_0004_resume_system` with seeded reusable templates.
- [x] Owner-scoped resume CRUD, Master/Job-specific types, immutable version numbering, restore, duplicate, delete, and intentional template switching.
- [x] Career Passport snapshot mapping with source IDs; resume edits never overwrite Passport data.
- [x] First saved Career Passport detail automatically creates one idempotent draft master resume; additional resumes remain user-controlled.
- [x] Deterministic template preview and text-searchable PDF export with page breaks.
- [x] Structured customization review records, source-evidence validation, explicit approve/reject flow, and provider-neutral AI boundary that reports unavailable without credentials.
- [x] Resume list, creation, editor, preview, version-history, restore, deletion, and review UI routes.
- [x] Real PostgreSQL integration tests for CRUD, template validation, snapshots, versioning, restore, duplicate/delete, PDF content, AI validation, review flow, and User A/User B isolation.
- [x] Backend pytest/Ruff and frontend lint/typecheck/production build verification.

## Current state: Milestone 5 — Real Job System

- [x] Normalized PostgreSQL migration `20260925_0005_job_system` for sources, reusable companies, global jobs, source skills, and owner-scoped saved jobs; no fake rows are seeded.
- [x] Provider-neutral authorized-source adapter, normalization, verification, deterministic identity, idempotent sync, and stale-source handling boundaries.
- [x] Authenticated paginated job browse/search/filter/detail, reusable company reads, save/unsave/list saved jobs, and job-source visibility endpoints.
- [x] Deterministic explainable matching, skill-gap comparison with explicit normalization rules, and recommendation endpoint.
- [x] Responsive `/jobs`, `/jobs/[id]`, and `/saved-jobs` pages with source/status/verification visibility, filters, pagination, official application links, and loading/empty/error states.
- [x] Integration tests for source identity, normalization, company/job deduplication, idempotent sync, stale verification, search/filter/pagination, saved-job ownership, matching, skill gaps, recommendations, and authentication boundaries.
- [x] M5 originally had no live source; M6 adds the configured Arbeitnow public API.

## Ordered future milestones

1. **Authentication:** password hashing, rate-limited signup/login, verification/reset flows, server-side sessions, security events, OAuth account linking, RBAC, and authorization tests.
2. **Career Passport:** owner-scoped CRUD for structured education, skills, experience, projects, credentials, links, preferences, and genuine completeness rules. **Completed.**
3. **Resume engine:** curated HTML/CSS templates, master resumes, immutable versions, preview/PDF pipeline, and download authorization. **Completed.**
4. **AI customization:** provider abstraction, structured requirement extraction, input-grounded matching, missing-requirement reporting, reviewable derived versions, and validation. **Not started as an external provider; boundary and review architecture only.**
5. **Job platform:** authorized-source adapters, normalization, de-duplication, verified status, search, filters, companies, and pagination. **Completed in Milestone 5.**
6. **Matching and notifications:** explainable matching, skill gaps, queue-backed synchronization, notifications, and preference enforcement. **Not started.**
7. **Applications:** saved jobs, application state machine, cover-letter versions, confirmation gates, and provider result recording. **Not started.**
8. **Administration and hardening:** protected admin tooling, audit logs, performance, accessibility, user-data export/deletion, and deployment runbooks. **Not started.**

## Definition of done for each milestone

Each milestone requires database migrations, server-side ownership checks, backend/frontend validation, empty/loading/error states, relevant unit and integration tests, type checks, linting, and documentation updates. External services are only enabled with their real credentials and explicit operational configuration.
