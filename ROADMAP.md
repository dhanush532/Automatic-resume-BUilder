# Dependency-aware implementation roadmap

Milestones 1–5 are preserved. Baseline and limitations: `MILESTONE_6_AUDIT.md`. Only M6 is authorized for this increment; do not silently advance to M7.

## M6 — Repository audit and authorized discovery (current)

- Modify: settings, jobs models/services/schemas/routes, jobs frontend/types, tests, package manifests/locks, setup/security docs; narrowly repair database pooling and mutation-origin coverage.
- New modules: Arbeitnow adapter, verification/freshness policy, operator sync CLI, focused integration tests; additive migration `20261013_0006` for verification evidence and source health.
- APIs: extend existing jobs/detail/saved/recommendations/source-info responses; preserve auth and existing paths. No unauthenticated sync endpoint.
- UI: source attribution/health, freshness and separate verification labels, manual source-link wording, suspicious-link restrictions.
- Safety: fixed HTTPS API host, no redirects/scraping, bounded fetches, safe text rendering, no candidate data shared, durable sync lease/cooldown, atomic ingestion, unchanged historical migrations.
- Tests: recorded/mock feed transport, pagination/error handling, normalization/idempotency, freshness, evidence, origin restrictions, actual migration and PostgreSQL regression suite; frontend static/build checks and local HTTP/browser smoke where available.
- Acceptance: real authorized listings ingested, repeated ingestion produces no duplicates, failed/partial fetch cannot close unseen jobs, stale/suspicious jobs excluded from default recommendations, attribution visible, existing checks pass. Report any unmet item explicitly.

## M7 — Intelligent matching (depends on M6)

- Files: `backend/app/services/job_matching.py`, `backend/app/schemas/jobs.py`, jobs routes/components; new eligibility/ranking/evaluation modules and fixtures.
- DB: additive preference/work-authorization consent fields only if required; no guessed eligibility.
- APIs/UI: eligibility and explainable ranking in existing match/recommendations views.
- Security/tests: job text is untrusted; deterministic constraints, unknown handling, currency/period-aware salary comparisons, multilingual skill aliases, labeled offline evaluation dataset.
- Acceptance: measured ranking quality, reproducible reasons, no unsupported eligibility claims; backend/frontend regressions pass.

## M8 — Resume intelligence (depends on M7)

- Files: existing resume/passport services/models/schemas/components; new fact-validation and configured-provider modules.
- DB: additive fact-source and AI-usage records; preserve resume/version IDs.
- APIs/UI: tailoring, unsupported-claim review, user approval, ATS-readable exports.
- Security/tests: trace every claim, no invented qualifications, local/mock provider tests, outage fallback, Unicode/export validation, costs disabled until explicitly configured.
- Acceptance: traceable reviewed tailoring and export fidelity demonstrated without paid calls.

## M9 — Application management (depends on M6–8)

- New models/migration/services: applications, attempts, events, approvals and confirmations; canonical cross-source job aliases.
- APIs/pages: `/applications`, `/applications/[id]`, `/application-queue`; preserve existing routes and add `/career-passport` alias when navigation expands.
- Security/tests: ownership, consent, unique/idempotency keys, durable transitions, unknown outcome reconciliation, pause/cancel. No live submission.
- Acceptance: preparation is never displayed as submission; approval and duplicate/uncertain-result tests pass.

## M10 — Authorized integrations (depends on M9 and provider permission)

- New policy/capability registry, adapter modules, sandbox integration tests; additive integration capabilities table.
- APIs/UI: explicit mode and permission status, handoff/resume, manual fallback.
- Security/tests: no CAPTCHA bypass, credential harvesting, stealth, or blind retries; external submission requires separate authority. Unknown/sensitive answers require user confirmation.
- Acceptance: permission-checked sandbox success/failure/verification paths, no real applications in tests.

## M11 — Tracking and notifications (depends on M9–10)

- New tracking/notification models, workers and dashboard components; additive events and consent storage.
- APIs/pages: `/dashboard`, `/notifications`, confirmed vs user-reported status; OAuth email only after explicit user authorization.
- Security/tests: redacted logs, delivery retry/idempotency, consent revocation, no inference of rejection from silence.
- Acceptance: evidence-linked history and tested notifications without unauthorized messages.

## M12 — Security and scalability (depends on M6–11)

- Files: core auth/security/config, infrastructure, worker/metrics modules, retention/export/deletion services; `/settings`, `/privacy`.
- DB: narrowly justified indexes and policy/audit records; safe migrations and backups.
- Security/tests: threat model, cross-user access, CSRF/SSRF/XSS, upload limits/scanning, TLS/at-rest storage deployment controls, secrets, per-user limits, load tests. Redis/queue only when measurements justify them.
- Acceptance: documented security review, bounded resource use, recoverable failures, controlled deployment checklist; no automatic production deployment.

## M13 — Release validation (depends on all earlier milestones)

- New end-to-end/security/accessibility suites and release/runbook documentation; no planned schema changes unless defects require additive fixes.
- Tests: complete journeys, responsive layouts, error recovery, provider permissions, migration/backup restore, dependency audit, user consent and cancellation.
- Acceptance: evidence-backed release candidate and explicit known limitations, followed by separate deployment approval.
