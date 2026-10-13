# CareerPilot architecture

## Milestone 6 extension

The earlier M1–5 description below is historical. `arbeitnow.py` implements the existing source-adapter boundary; `app.sync_jobs` is an operator-only CLI enabled through the existing settings system. No parallel config service or queue is introduced. API calls are bounded and made outside database transactions; a durable source lease prevents concurrent jobs. A fully validated batch is atomically upserted. Availability/freshness is evaluated consistently by `job_verification.py` on list, detail, saved and recommendation reads. `job_verification_events` preserves observations, while `job_sources` holds latest sync health. Aggregator evidence never guarantees employer identity. The frontend exposes source attribution, health, trust and manual-link restrictions. Matching/AI/application automation remain later milestones in `ROADMAP.md`.

## Milestones 1–5 scope

This repository contains the Milestone 1 foundation, Milestone 2 authentication/session management, Milestone 3 Career Passport, Milestone 4 Resume System, and the Milestone 5 real-job foundation: a Next.js frontend, a FastAPI backend, PostgreSQL migration tooling, normalized account/professional/resume/job tables, deterministic templates, and provider-neutral integration boundaries. It deliberately does **not** claim to provide configured email delivery, Google OAuth, external AI, file storage, or a live job feed.

## Runtime layout

```text
Browser
  └─ Next.js frontend (frontend/, port 3000)
       └─ HTTPS API calls with credentials
            └─ FastAPI (backend/, port 8000)
                 ├─ PostgreSQL via SQLAlchemy/Alembic
                 ├─ server-side session/auth services
                 ├─ owner-scoped Career Passport CRUD
                 ├─ owner-scoped Resume System CRUD and versioning
                 ├─ source-traceable global jobs and owner-scoped saved jobs
                 ├─ authorized-source adapter, normalization, sync, and matching boundaries
                 ├─ deterministic HTML/PDF rendering
                 ├─ provider-neutral AI boundary (unavailable until configured)
                 └─ future worker queue adapter
```

The frontend never receives provider secrets. Browser authentication uses server-side session records and HTTP-only cookies; protected API dependencies resolve the cookie token server-side and enforce identity and resource ownership before reads or writes.

## Career Passport boundary

`/api/v1/passport` is authenticated through the existing session dependency. Profile, preferences, education, links, skills, experience, projects, certifications, courses, achievements, languages, and open-source contributions are stored as normalized PostgreSQL entities. Every query includes the authenticated user ID; relationship skill IDs are checked against that same owner. The Passport is the authoritative user-entered source of truth, and the frontend never invents entries or completeness data.

## Resume boundary

`/api/v1/resumes` creates immutable, owner-scoped resume versions from Career Passport snapshots. The first saved Passport detail automatically creates one idempotent draft master resume; additional job-specific resumes can still be created manually. A selected template controls rendering and is stored on each version. Resume editing changes only a resume snapshot; it never mutates Career Passport rows. Customization suggestions are structured, source-evidence-linked, pending review, and cannot be approved when their evidence is no longer present. PDF rendering is deterministic and independent of any AI provider.

## Job system boundary

`/api/v1/jobs` reads global jobs imported by an authorized source adapter. Jobs are never owned by a user; `saved_jobs` is the only user-specific relationship in this milestone. `JobSourceAdapter` is the provider-neutral interface for official/licensed APIs and authorized feeds. The sync service normalizes provider labels, upserts reusable companies, computes a deterministic source identity key, replaces source-provided skills, and preserves first/last-seen and verification timestamps. A complete source snapshot marks previously active jobs `UNVERIFIED` when they disappear instead of deleting them.

The development registry contains no adapter and the database migration seeds no sources or jobs. This is intentional: no fake vacancy is presented as real. A configured adapter must provide an official application URL, source URL, external identifier or deterministic fallback identity, and an explicit verification status. Matching is deterministic and explainable (skills 50%, role 20%, location 10%, employment 10%, salary 10%, with unavailable criteria excluded and remaining weights renormalized); it is not a hiring prediction. Skill gaps use exact normalized names plus a small explicit alias map and report ambiguous labels separately.

## Authentication boundary

```text
Browser form
  └─ POST /api/v1/auth/* (credentials included)
       ├─ Pydantic request validation and normalization
       ├─ Argon2id password service
       ├─ PostgreSQL users / user_sessions / login_events
       ├─ HMAC-hashed session and one-time security tokens
       └─ HTTP-only SameSite=Lax cookie (raw session token only)
```

Raw session, verification, and reset tokens exist only while being issued or consumed. PostgreSQL stores an HMAC-SHA-256 reference, never the raw token. Email delivery and OAuth are provider interfaces; without valid provider configuration they explicitly report unavailable rather than fabricate a message, sign-in, or account link.

## Directory structure

```text
frontend/                 Next.js App Router user interface
  app/                    routes, metadata, global styles
  components/ui/          reusable, accessible primitives
  lib/                    shared client utilities
backend/                  FastAPI application
  app/api/                route composition and endpoint modules
  app/core/               settings and database primitives
  app/models/             SQLAlchemy models
  app/workers/            queue provider boundary
  tests/                  API and domain tests
  alembic/                versioned database migrations
docs/                     future implementation-specific guides
resume_templates/         future server-rendered resume templates
```

## Architectural rules

- The Career Passport remains authoritative; a resume customization is a derived version, never a hidden profile edit.
- Feature routes will depend on explicit service/repository interfaces rather than placing business rules in HTTP handlers.
- Any AI output is structured, validated, attributed to inputs, and treated as a suggestion rather than a source of profile facts.
- Authentication business rules live in `backend/app/auth/` and `backend/app/services/`; HTTP routes compose them without implementing security logic inline.
- Job integrations implement a source adapter. Only authorised sources are surfaced as real jobs.
- Long-running work enters a configured queue adapter. A missing queue configuration must be reported, not simulated.
- Files are referenced by storage keys and served through an authorization-checked storage service; large binaries do not belong in PostgreSQL.

## Explicitly unconfigured integrations

Google OAuth, transactional email delivery, an AI provider, object storage, a background-job broker, and job-source APIs require real credentials/configuration. Their environment-variable contracts are in [`.env.example`](.env.example); no integration currently fakes a result, and no live job source is configured in this environment.
