# Authentication upgrade plan

The follow-up request adds Redis and Celery, authentication-priority queues, a durable encrypted email outbox, distributed provider quotas, bounded retry/backoff, safe failover and monitoring. This replaces the earlier simple-delivery approach while retaining the original identity-upgrade scope. Operational design/configuration is documented in `AUTHENTICATION_AND_EMAIL.md`.

Work is scoped to authentication, account settings, additive schema changes, tests and configuration/docs. Passport, resumes, jobs and existing UUIDs remain intact.

1. Checkpoint and baseline: preserve private source/database backups, verify existing tests/head, inspect existing routes/settings.
2. Identity/schema: retain user UUIDs and sessions; remove phone uniqueness; add a normalized-email expression index (abort safely on conflicts); add pending/active/deleted/disabled state, OTP challenges, database rate limits, OAuth attempts, recent-auth timestamps.
3. Email: extend the existing email adapter with SMTP and a transactional HTTP provider, fail clearly when unconfigured; six-digit HMAC-protected OTPs (5 minutes, 5 mistakes, 60-second resend), recovery delivery, verified email changes, account security notifications.
4. Social: replace the existing OAuth boundary with Google/GitHub/LinkedIn authorization-code adapters; browser-bound one-use state, PKCE where supported, validated OIDC signatures/claims/nonce, stable subjects. Explicit linking only after recent authentication; never grant access through an email match.
5. UI: optional phone/country selector, optional username compatibility, OTP/resend page, provider buttons with configuration state, account and connected-account settings, password/social reauthentication, email/phone changes and deletion confirmation. Keep unrelated pages intact.
6. Verification: real PostgreSQL migration and schema check; registration/OTP/provider/link/session/concurrency/data-preservation tests with test-only mail/provider mocks; frontend lint/type/build and startup checks. Document external credentials/approvals and every unverified live flow.

Main files: existing `app/models/user.py`, `schemas/auth.py`, `auth/normalization.py`, `services/authentication.py`, `services/sessions.py`, `api/routes/auth.py`, `integrations/email.py`, `integrations/oauth.py`, settings; new auth state/challenge/rate-limit modules and migration; existing frontend auth forms plus new settings/OTP components.

Phone country is selected explicitly (India shown as initial UI selection), never inferred secretly. Email normalization trims/casefolds without removing dots/plus tags. Password whitespace is preserved. Abandoned pending registrations may be replaced only through a newly delivered email challenge; verification applies the intended pending credentials atomically. Deleted/disabled accounts cannot be reactivated through registration.

External configuration: mail sender/provider credentials and OAuth client IDs/secrets/callback approvals must be supplied in the server environment, never this chat or frontend. No real messages or provider sign-ins are claimed without configuration and evidence.

Checkpoint: `.checkpoints/auth-upgrade-20261013/source.zip` SHA256 `4D279E912164BE7F3B97BC8C96243924388A129F36CB69D2D7DDA89EDDE034D4`; database dump SHA256 `732E893651BB94E526E4AF35FF42179D383CB8EEDE6C4AD9CE50734F07CDC124`.
