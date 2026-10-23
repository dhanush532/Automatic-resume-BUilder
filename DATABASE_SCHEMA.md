# CareerPilot database schema

## Mock interview migration: `20261023_0010`

`interview_sessions` is an additive table keyed by UUID and owned by an existing
user (`ON DELETE CASCADE`). An optional resume reference uses `ON DELETE SET NULL`.
It stores role, minimized career context, job description, bounded interview
configuration, model, JSONB question/answer/evaluation turns, lifecycle status,
server elapsed time and optimistic revision. An owner/created-time index supports
private history. No webcam recordings or audio blobs are stored. See
[INTERVIEW_PLATFORM.md](INTERVIEW_PLATFORM.md) for endpoints and migration rollout.

## Authentication/email migrations

`20261013_0007` retains UUIDs, removes phone uniqueness, adds normalized-email uniqueness, account state, recent-auth timestamps, email challenges, OAuth attempts and shared API rate buckets. `20261013_0008` adds encrypted email deliveries with status/attempts/scheduling/leases/provider receipt/error category. `20261013_0009` normalizes historical email casing/whitespace without changing identities. None of the earlier migrations is rewritten. A UUID tombstone is retained only after an explicit owner-requested deletion.

## M6 additive migration: `20261013_0006`

`job_sources` adds attempt/success timestamps, safe error category, last count, lease UUID and lease expiry. `jobs` adds a constrained trust status independent of availability and a `(status,last_seen_at)` index. New `job_verification_events` records job FK, timestamp, trust status, reason and evidence URL, indexed by job/time. No previous rows or migrations are removed. Legacy job IDs and saves are retained during identity-key normalization updates. Existing model metadata was corrected to match already-created indexes, OAuth uniqueness and timezone-aware resume timestamps; those metadata corrections require no database mutation.

PostgreSQL is the production database. Alembic owns all schema changes. The versioned migrations establish the account foundation, sessions, normalized Career Passport, and Resume System; no ad-hoc DDL is required.

## Implemented migrations

```text
users 1 ── 0..1 profiles
  └── 0..1 user_preferences
```

`users` has normalized, unique email, username, and optional E.164 phone columns; role; activation state; and verified-email timestamp. `profiles` holds the initial Career Passport personal fields. `user_preferences` holds presentational preferences. Child records cascade only when their owning user is deleted.

`20260925_0002_auth_sessions` adds:

```text
users 1 ── * user_sessions
  ├── * login_events
  ├── * security_tokens
  └── * oauth_identities
```

`user_sessions` stores a unique HMAC token hash, lifecycle state, expiry/revocation timestamps, and limited device context. `login_events` records security-relevant events without password or raw-token data. `security_tokens` supports single-use, expiring email-verification and password-reset flows using only a token hash. `oauth_identities` enforces uniqueness of a provider subject and is ready for an explicit account-linking flow. No raw token or password belongs in a business-domain table.

`20260925_0003_career_passport` adds the Career Passport fields to `profiles` and creates:

```text
users 1 ── 0..1 career_preferences
      ├── * professional_links
      ├── * education
      ├── * user_skills ── 1 skills
      ├── * experiences ── * experience_skills ── 1 skills
      ├── * projects ── * project_skills ── 1 skills
      ├── * certifications
      ├── * courses
      ├── * achievements
      ├── * languages
      └── * open_source_contributions
```

All user-owned rows use UUID foreign keys with cascade-on-account-delete, indexes for owner-scoped lists, named uniqueness constraints, timestamps, and date/salary integrity checks. Skill definitions are reusable, while `user_skills` and the two relationship tables preserve ownership and prevent duplicate links.

`20260925_0004_resume_system` adds:

```text
resume_templates 1 ── * resumes
users 1 ── * resumes 1 ── * resume_versions
                         └── * resume_customizations
```

Templates are seeded as reusable metadata for Modern, Professional, Minimal, Student, Developer, Creative, and ATS-readable layouts. A resume stores its owner, name, type, selected template, and lifecycle status. Every version stores a version number, source, template, immutable JSON snapshot, creator, change summary, and optional restore parent. Customizations retain a base version, structured generated content, source-review changes, provider metadata, and review status. The optional `job_id` is intentionally not a foreign key until the future job system exists.

`20260925_0005_job_system` adds:

```text
job_sources 1 ── * jobs * ── 1 companies
                   └── * job_skills
users 1 ── * saved_jobs * ── 1 jobs
```

`job_sources` stores a source identity and non-secret configuration metadata independently from `jobs`. `jobs` are global records with a unique deterministic `identity_key`, optional source external ID, canonical/source/application URLs, normalized location and employment fields, source metadata, lifecycle status (`ACTIVE`, `CLOSED`, `EXPIRED`, or `UNVERIFIED`), and first/last-seen and last-verified timestamps. `companies` are reusable by normalized name. `job_skills` retains source-provided required/preferred labels. `saved_jobs` is the owner-scoped join with a database uniqueness constraint per user/job. No source or job rows are seeded because no legitimate live provider is configured.

## Planned logical domains

| Domain | Planned tables | Key relationship/invariant |
| --- | --- | --- |
| Career Passport | `profiles`, `career_preferences`, `professional_links`, `education`, `skills`, `user_skills`, `experiences`, `experience_skills`, `projects`, `project_skills`, `certifications`, `courses`, `achievements`, `languages`, `open_source_contributions` | Every user-owned row carries `user_id`; normalized skills link to experiences, projects, and user skills. |
| Resumes | `resume_templates`, `resumes`, `resume_versions`, `resume_customizations` | A resume has immutable Passport-derived versions; customization points to a future job and reviewed source evidence. |
| Job platform | `job_sources`, `companies`, `jobs`, `job_skills`, `saved_jobs` | Deterministic source/external ID, canonical URL, or normalized fallback identity prevents duplicate jobs. Source status and verification timestamps are retained. |
| Applications | `applications`, `application_events`, `cover_letters`, `cover_letter_versions` | Application status transitions are evented; submission evidence is stored only when a provider confirms it. |
| Messaging | `notifications`, `notification_preferences`, `email_connections` | Connections reference encrypted provider-token storage, never browser-accessible raw tokens. |
| Administration | `admin_audit_logs` | Sensitive admin actions retain non-secret actor/target/action metadata. |

## Integrity and query principles

- Use UUID primary keys, foreign keys, timestamps, and named unique constraints.
- Put uniqueness in the database: user identifiers, OAuth provider identity, job source/external ID, canonical application URL where appropriate, and join-table combinations.
- Index `(user_id, created_at)` for user-scoped lists; index job status, posted date, source ID, normalized location, and search vectors when the job platform arrives.
- Every user-owned query scopes by the authenticated owner on the server. Client-provided IDs are never sufficient authorization.
- JSON is reserved for provider metadata and validated structured AI output; Passport entities remain relational.
- Job ingestion is only through an authorized adapter. A source that cannot verify current availability must write `UNVERIFIED`; it must never be presented as confirmed active.
