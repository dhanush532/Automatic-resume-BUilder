# Authentication and email upgrade verification — 2026-10-13

Implemented against the existing CareerPilot architecture; M7 has not started. Setup and operational boundaries are in [AUTHENTICATION_AND_EMAIL.md](AUTHENTICATION_AND_EMAIL.md).

## Verified

- `uv run ruff check .`: passed.
- `uv run pytest`: 102 passed against real local PostgreSQL; one upstream Starlette TestClient deprecation warning. Tests isolate changes with rollback transactions.
- `uv run alembic upgrade head`: applied migrations 0007–0009 successfully. `uv run alembic current`: `20261013_0009 (head)`. `uv run alembic check`: no new operations detected.
- SQLAlchemy `SELECT 1`: returned 1.
- Frontend `npm run lint`, `npm run typecheck`, `npm run build`: passed; signup, login and signin are present in the production build.
- Docker Redis, email worker and scheduler built and started. Real Redis rate limiter accepted two permitted slots and rejected a third. A deliberately expired test message reached EXPIRED with zero provider attempts and erased payload through the real Celery worker.
- Backend capabilities and frontend signup/login/signin responded HTTP 200. The frontend was rebuilt with the development server stopped to resolve a mixed development/production cache. Existing job catalog retained 737 rows.

Sandbox-only attempts could not access PostgreSQL/Docker/local HTTP; permitted local-access runs passed. No real outbound email, account deletion, OAuth login, or application submission was performed.

## Changed files and purpose

Paths below are relative to `D:\resume`. Historical migrations and existing Passport/resume/job workflows were retained.

- Configuration/runtime: `.env.example`, `docker-compose.yml`, `backend/pyproject.toml`, `backend/uv.lock`, `backend/Dockerfile`, `backend/.dockerignore`, `backend/app/core/config.py`. Added environment-driven transports, Redis/Celery dependencies and Linux workers. Existing local `.env` selects Resend and localhost Redis only; credentials are not recorded here.
- Database: `backend/app/models/user.py`, `backend/app/models/__init__.py`, `backend/app/models/account_security.py`, `backend/alembic/env.py`, and `backend/alembic/versions/20261013_0007_account_security.py`, `20261013_0008_email_outbox.py`, `20261013_0009_normalize_existing_emails.py`. Added normalized email uniqueness, optional non-unique phone, pending accounts, recent authentication, OTPs, rate buckets, OAuth attempts and encrypted outbox.
- Security/core: `backend/app/auth/normalization.py`, `crypto.py`, `shared_limits.py`, `logging.py`; `backend/app/services/authentication.py`, `sessions.py`, `account_security.py`, `email_challenges.py`, `email_delivery.py`; `backend/app/schemas/auth.py`; `backend/app/main.py`. Added explicit phone country normalization, browser-bound hashed OTPs, shared throttling, safe validation/logging and bounded delivery state transitions.
- Routes/providers: `backend/app/api/router.py`, `backend/app/api/routes/auth.py`, `account.py`, `social_auth.py`; `backend/app/integrations/email.py`, `oauth.py`; `backend/app/workers/email.py`, `backend/app/email_monitor.py`. Added real transport adapters, secure social flows, explicit linking, settings/recovery and priority queue processing. Dispatcher tasks remain immediately claimable; uncertain retries stay pinned to the original provider.
- Tests: `backend/tests/conftest.py`, `test_account_upgrade.py`, `test_email_delivery.py`, `test_social_auth.py`, `test_identity_concurrency.py`. Added rollback-safe regression, concurrency, expiry, outage, quota, failover and OAuth tests; automatic tests cannot send real email.
- Frontend: `frontend/lib/api.ts`; `frontend/components/auth/auth-shell.tsx`, `signup-form.tsx`, `login-form.tsx`, `forgot-password-form.tsx`, `token-form.tsx`, `otp-form.tsx`, `social-buttons.tsx`; `frontend/components/security/security-center.tsx`, `account-settings.tsx`; `frontend/app/signup/page.tsx`, `verify-email/page.tsx`, `signin/page.tsx`, `settings/page.tsx`, `settings/account/page.tsx`, `settings/connected-accounts/page.tsx`, `globals.css`. Added optional phone/country input, OTP delivery/retry feedback, account settings and accessible icon-only Google/GitHub/LinkedIn buttons shared by signup/login; signin aliases login.
- Documentation: `README.md`, `DATABASE_SCHEMA.md`, `SECURITY.md`, `AUTH_UPGRADE_PLAN.md`, `AUTHENTICATION_AND_EMAIL.md`, this report. Documented configuration, checkpoints, startup, privacy and verified versus unverified behavior.

## Still requires operator configuration

Real Resend API key and verified sender, or SMTP credentials; real Google/GitHub/LinkedIn app credentials and approved callbacks. Missing providers remain disabled, and unavailable email configuration produces a safe error without bypassing verification.

Provider acceptance is not proof of inbox delivery. Workers prevent expired-code handoff, but cannot control provider delivery time after acceptance. Production delivery webhooks, real inbox/OAuth browser tests, DNS, TLS, secret rotation, Redis protection, monitoring alerts and deployment security review remain operator work. Full authenticated browser journeys have not been verified.

## Follow-up: preview and social availability repair

A later user-started development server and the production preview shared `.next`, causing missing JavaScript chunks and a client-side exception despite HTTP 200 page responses. The identified CareerPilot preview processes were restarted as one development preview on port 3000. `frontend/next.config.ts` now isolates development output in `.next-dev`; `.gitignore` and `frontend/eslint.config.mjs` exclude generated output. Next.js generated the corresponding development types entry in `frontend/tsconfig.json` and `frontend/next-env.d.ts`.

`frontend/components/auth/social-buttons.tsx` always renders the three known icons, keeps unchecked providers disabled, bounds the availability request to eight seconds, and offers a retry if it fails. `README.md` documents preview modes and unavailable providers. No backend or credential changes were needed.

Frontend lint/type checking passed. An initial sandbox production-build attempt hit filesystem EPERM; the local-access build passed. Signup/login/signin each returned HTTP 200, included three accessible social buttons, and all referenced JavaScript assets returned HTTP 200. Browser signup and login rendered successfully and completed the real backend capabilities check. The icons remain disabled because provider credentials are absent; no live OAuth login was claimed.
