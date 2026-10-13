# Authentication and email delivery

The existing UUID, Argon2id, HMAC session, Passport, resume and jobs architecture is retained. This upgrade adds OTP verification, official social-provider adapters, explicit account linking, account settings, and a PostgreSQL outbox processed by Redis/Celery.

## Configure real transactional email

The local environment selects Resend, but **no API key or sender has been supplied**. Registration deliberately returns 503 until a real provider is configured. Existing verified users can still sign in and use their data. No OTP is returned in an API response, printed in logs, or made available through a development bypass.

Edit the EXISTING `D:\resume\.env` locally; do not overwrite it or paste secrets into chat:

```dotenv
EMAIL_PROVIDER=resend
EMAIL_FROM=CareerPilot <accounts@your-verified-domain.example>
EMAIL_API_KEY=your-server-side-resend-key
EMAIL_FAILOVER_PROVIDER=
EMAIL_MAX_ATTEMPTS=4
EMAIL_PROVIDER_PER_SECOND=2
EMAIL_PROVIDER_PER_MINUTE=60
REDIS_URL=redis://localhost:6379/0
```

The values above are placeholders. In Resend, verify your sender domain and supply an API key authorized to send from it. Do not assume a test sender can send to arbitrary recipients. Configure limits for your actual provider plan; the application also honors quota rejection/backoff. No live sending or provider-account setup was performed during implementation.

Alternative or optional failover transport:

```dotenv
EMAIL_PROVIDER=smtp
EMAIL_FROM=accounts@your-verified-domain.example
SMTP_HOST=your-mail-server.example
SMTP_PORT=587
SMTP_USERNAME=your-smtp-user
SMTP_PASSWORD=your-server-side-secret
SMTP_TLS=starttls
# SMTP_TLS=ssl with SMTP_PORT=465 for implicit TLS
```

Set `EMAIL_FAILOVER_PROVIDER=smtp` only when its credentials are configured alongside primary Resend. Failover is disabled by default. Provider endpoints/SMTP configuration are administrator-owned, not user-supplied destinations.

## Run on Windows

Docker Desktop with its WSL2 backend is used for the Linux workers; native Windows Celery workers are not the production target. Docker is installed on this machine. On another machine, install/start Docker Desktop first and verify `docker info`.

```powershell
cd D:\resume\backend
uv sync
uv run alembic upgrade head
uv run alembic current
```

Then start infrastructure and workers from the repository root:

```powershell
cd D:\resume
docker compose --profile email up -d --build postgres redis email-worker email-scheduler
```

Two application terminals:

```powershell
cd D:\resume\backend
uv run uvicorn app.main:app --reload --port 8000
```

```powershell
cd D:\resume\frontend
npm run dev
```

Open http://localhost:3000/signup. Phone is optional. Select India (+91) to enter a ten-digit Indian number; international `+country-code` numbers also work. Phones are not unique or verified ownership identifiers. Username is optional and generated when absent. Successful registration shows the OTP form in the same browser.

Restart the API and recreate workers/scheduler after environment changes:

```powershell
cd D:\resume
docker compose --profile email up -d --force-recreate email-worker email-scheduler
```

Do not use `docker compose down -v` on existing data. Production builds can instead be run with `npm run build` then `npm run start`. Keep the application servers running. Avoid multiple dev/production servers writing the same `.next` directory.

## Delivery and failure behavior

1. The API saves an encrypted message and OTP HMAC in the same PostgreSQL transaction as the pending account/challenge. The broker task contains only an opaque delivery UUID.
2. After commit, the API attempts a broker publish. Broker failures leave a queued outbox row; the request does not crash because Redis is unavailable. Celery Beat dispatches due rows every five seconds when the broker recovers.
3. Authentication messages use `emails_auth` priority 0. Security notices use `emails_default` priority 6. Redis emulates priorities; dedicate workers to `emails_auth` for stronger isolation. Worker prefetch is one.
4. Workers claim rows using a 90-second lease and short database transactions. HTTP delivery happens outside locks. Redis atomically enforces per-provider second/minute limits across workers.
5. Retry state/next-attempt times live in PostgreSQL, not long broker countdowns. Four attempts by default; exponential delays start at 5, 10, 20 seconds with small jitter, capped at 120 seconds. Provider Retry-After may extend the wait. No retry is scheduled past expiry.
6. Resend retries reuse the same idempotency key and are pinned to the provider that might have accepted the message, including after failover. Ambiguous SMTP outcomes/worker interruptions become `UNCERTAIN`; they are not blindly resent. Failover occurs only after definite nonacceptance (such as quota rejection), with a configured alternative and its own rate slot. Drain/reconcile pending or uncertain requests before moving credentials to a different provider account.
7. A worker checks expiry and whether a challenge was consumed, superseded or locked out immediately before handoff. A 30-second remaining-lifetime margin avoids near-expiry dispatch, and transports check again before sending. Expired/superseded payloads are cleared. OTP verification always enforces its five-minute expiry, even if an external provider delivers late.

The application can prevent expired codes from being submitted to a provider; it cannot guarantee delivery time or inbox placement after a provider accepts an email. `ACCEPTED` means provider acceptance, not inbox delivery or user reading. Provider delivery/bounce webhooks and end-to-end inbox verification are not implemented/verified in this increment.

Delivery states: `QUEUED`, `SENDING`, `RETRYING`, `ACCEPTED`, `FAILED`, `EXPIRED`, `CANCELLED`, `UNCERTAIN`. Terminal message ciphertext is erased. A queued code that expires during an outage is discarded, never sent on recovery. Users can request a new code after 60 seconds. A new challenge invalidates the previous one. A browser receipt is required for OTP confirmation/resend to prevent activating an account with an attacker-chosen password.

Five incorrect OTP attempts exhaust a challenge. Account/email/IP request limits, including login, are stored transactionally in PostgreSQL, so they work across API workers even during Redis outages. Existing login limit/window settings are retained. Provider send quotas use Redis and fail closed when its rate store is unavailable.

## Monitoring and scaling

```powershell
cd D:\resume\backend
uv run python -m app.email_monitor
cd D:\resume
docker compose --profile email ps
docker compose logs --tail 50 email-worker email-scheduler
docker compose --profile email exec -T email-worker uv run --no-sync celery -A app.workers.email:celery_app inspect ping --timeout=5
```

The monitor prints aggregate states, oldest pending age and broker reachability, never message content or recipients. Alert on increasing oldest age, `FAILED`/`UNCERTAIN`, quota/rate-store errors, and worker heartbeat loss. The receipt-bound pending-delivery endpoint and owner-scoped account history expose safe status/retry information.

Scale workers only within database and provider capacity:

```powershell
docker compose --profile email up -d --scale email-worker=3 email-worker
```

Run one scheduler. The database row lease and provider idempotency protect against duplicate broker deliveries; SMTP cannot guarantee exactly-once delivery after a crash. Redis uses append-only persistence and `noeviction`; PostgreSQL remains the recovery source. In production protect Redis with authentication, TLS/private networking, capacity monitoring and backups. Development exposes Redis only on loopback. Container workers derive the PostgreSQL host override from the existing DATABASE_URL credentials; no second database credential system is introduced.

## Google / GitHub / LinkedIn

Set server-side client IDs/secrets in the existing environment:

```dotenv
BACKEND_ORIGIN=http://localhost:8000
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
```

Register exact callbacks:

- Google: `http://localhost:8000/api/v1/auth/oauth/google/callback`
- GitHub: `http://localhost:8000/api/v1/auth/oauth/github/callback`
- LinkedIn: `http://localhost:8000/api/v1/auth/oauth/linkedin/callback`

Google needs a web OAuth client and configured consent/test users. GitHub needs an OAuth app with minimal `read:user user:email` permissions. LinkedIn needs the approved “Sign In with LinkedIn using OpenID Connect” product; use a registered HTTPS callback if its portal rejects local HTTP, and change BACKEND_ORIGIN consistently. Do not bypass certificate warnings. These credentials/approvals and live callback tests remain outstanding.

Flows use one-use, browser-bound state; encrypted server-side PKCE verifiers; fixed official token/API/JWKS endpoints; strict RS256 signature, issuer, audience, expiry and nonce validation. Google/GitHub use S256 PKCE; this LinkedIn adapter uses its documented confidential-client OIDC flow without assuming undocumented PKCE support. GitHub uses its numeric ID and verified email API, including private email. LinkedIn's optional/unverified email is never treated as verified; new registration fails safely when proof is absent. LinkedIn sign-in does not verify employment history or real-world identity.

Email matches never grant access or merge accounts. An existing account must sign in and explicitly link a provider after recent authentication. Stable provider subjects are globally unique. Linking/email changes preserve the UUID and associated records. Disconnect cannot remove the last usable method. Social-only users can add a password through the verified email recovery flow. Password/social reauthentication is required for sensitive changes; existing session activity does not refresh the recent-auth timestamp.

Account settings: `/settings`, `/settings/account`, `/settings/connected-accounts`; existing `/settings/security` remains. New email is not activated until OTP proof and a database uniqueness check succeed. Email/password changes revoke sessions.

## Identity and deletion policy

Emails are trimmed/lowercased consistently with PostgreSQL `lower(btrim(email))`; dots and plus tags remain. A functional unique index handles concurrent writers. Historical casing was normalized without changing IDs. Conflicting historical emails cause the unique-index migration to abort rather than merge/delete accounts.

Pending registrations cannot log in. After the generation cooldown, a legitimate owner can restart registration; replacement credentials are applied only after email proof in that browser. Resend retains the intended password hash across short code expiry. After the browser receipt expires, restart registration. Pending fields contain hashes, not plaintext passwords, and old transient payloads are cleared after 24 hours. Disabled accounts cannot be reactivated this way.

Explicit account deletion requires recent authentication, confirmation, and password confirmation for password users. It removes only the caller's profile/Passport/resume/saved-job/challenge/session/provider records, scrubs personal security-event fields, and retains a nonpersonal `DELETED` UUID tombstone. Global jobs/companies/templates/skills and other users remain. The original email becomes available for a fresh verified account with a NEW UUID; the deleted UUID cannot be reassigned or silently reactivated. No real account deletion was performed during development; deletion tests use rollback transactions.

## Security/verification boundaries

OTP HMACs are domain-separated and salted with challenge UUIDs. Outbox bodies and PKCE material use authenticated encryption derived from AUTH_SECRET. Never log settings dumps, bodies, OAuth tokens, codes or provider error response text. Access-log query strings on auth routes are redacted; validation errors omit raw inputs. Rotate AUTH_SECRET only with a reviewed plan to drain/expire pending messages; rotation also invalidates existing HMAC sessions/challenges. Server env files/backups remain private.

Production still requires HTTPS, secure cookies, trusted proxy/edge rate controls, secrets management, privacy/retention review, operational alerts and live provider validation. Six-digit OTPs are verification, not MFA. Full authenticated browser journeys, accessibility/dark-mode review and delivery/bounce webhooks remain separate release checks. Automated provider mocks are defined only under `backend/tests`.

Official references: [Resend send API](https://resend.com/docs/api-reference/emails/send-email), [Celery Redis](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html), [Celery task reliability](https://docs.celeryq.dev/en/stable/userguide/tasks.html), [Google OIDC](https://developers.google.com/identity/openid-connect/openid-connect), [GitHub OAuth/PKCE](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps), [LinkedIn OIDC](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2).
