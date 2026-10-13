# Deploy CareerPilot publicly with Vercel

Repository: https://github.com/dhanush532/Automatic-resume-BUilder

This guide deploys the Next.js frontend and FastAPI API as **two Vercel projects**, using hosted PostgreSQL and Redis plus the existing Redis/Celery worker and scheduler on a long-running Linux host (Render is one option). Vercel's newer Celery/Vercel Queues adapter uses a different broker; this project intentionally retains its requested Redis architecture. Review provider plans and charges before provisioning anything. No cloud resources were created by uploading the repository.

Visitors do not create OAuth developer apps or supply keys. The site operator configures a provider once; visitors then use its icon. For a new social account, they accept the terms checkbox and click the icon without filling name, email, phone, or password. Only providers you configure become available. Live provider login remains a deployment smoke test, not a guarantee based on populated environment fields.

## 1. Import the frontend

1. Sign in to https://vercel.com and choose **Add New → Project**.
2. Import `dhanush532/Automatic-resume-BUilder`. Authorize access to this repository if necessary.
3. Name the frontend project, for example `careerpilot-web` (choose an available name).
4. Set **Root Directory** to `frontend`, **Framework Preset** to Next.js, **Install Command** to `npm ci`, and **Build Command** to `npm run build`. Leave the output directory at its Next.js default.
5. Set `NEXT_PUBLIC_API_BASE_URL=/api/v1` for Production. Do not put OAuth, database, email or authentication secrets in frontend environment variables.
6. Deploy and record the stable **production** HTTPS domain, not the commit-specific preview URL. Examples below use `https://your-web-project.vercel.app`; replace it everywhere with your actual domain.

At this stage the UI is online, but account/API features are not ready until the remaining steps are complete. An availability error here is expected, not successful deployment of the complete platform.

## 2. Provision production PostgreSQL and Redis

- Create a managed PostgreSQL database and a managed Redis-compatible TCP broker. Keep production data separate from your local development database.
- Both must be reachable by the Vercel API and your workers. A Render private/internal URL is not reachable from Vercel; choose the provider's appropriate external TLS connection URL. Protect network access, require authentication/TLS, and review connection limits. A REST-only Redis endpoint is not a Celery TCP broker.
- Use the PostgreSQL connection URL with the SQLAlchemy driver prefix `postgresql+psycopg://`, retaining the provider credentials/host/database and required TLS parameters such as `sslmode=require`.
- Use the Redis provider's TLS URL. For a `rediss://` broker, configure certificate verification (for example the provider URL with `ssl_cert_reqs=required` in its query parameters). Never disable certificate verification to make it connect.
- Do not upload connection URLs to GitHub or put them in a `NEXT_PUBLIC_` variable. Provider consoles and deployment secret settings are the place for these values.

## 3. Import the backend as a second Vercel project

Import the same repository again, name it separately (for example `careerpilot-api`), set **Root Directory** to `backend`, and select FastAPI. The project declares `app.main:app` in `pyproject.toml`; let Vercel install the Python dependencies and manage its Python build/output defaults. Do not run database migrations as the Vercel build command.

Add these Production environment variables in the backend project:

```dotenv
APP_ENV=production
FRONTEND_ORIGIN=https://your-web-project.vercel.app
BACKEND_ORIGIN=https://your-web-project.vercel.app
API_PREFIX=/api/v1
SESSION_COOKIE_SECURE=true
AUTH_SECRET=GENERATE_A_NEW_PRIVATE_RANDOM_VALUE
DATABASE_URL=YOUR_HOSTED_SQLALCHEMY_DATABASE_URL
REDIS_URL=YOUR_HOSTED_TLS_REDIS_URL
GITHUB_CLIENT_ID=YOUR_PRODUCTION_OAUTH_CLIENT_ID
GITHUB_CLIENT_SECRET=YOUR_PRODUCTION_OAUTH_CLIENT_SECRET
EMAIL_PROVIDER=resend
EMAIL_FROM=YOUR_VERIFIED_SENDER_ADDRESS
EMAIL_API_KEY=YOUR_PRIVATE_RESEND_KEY
```

These are instructions/placeholders, not working credentials. Generate a unique AUTH_SECRET from at least 32 random bytes; do not deploy the example's `replace-with-a-long-random-secret`. Use exactly the same secret in the API, worker and scheduler. Do not change your local secret as a side effect of production setup: rotation invalidates existing sessions and encrypted pending payloads.

`BACKEND_ORIGIN` deliberately names the **frontend public domain** in this topology: it constructs the browser's OAuth callback URL, which will be forwarded to the real API. The API's actual separate Vercel URL is used only as the proxy target in step 5. Do not mix these up.

Email credentials can be omitted temporarily to test GitHub social registration with verified provider email; email/password registration, OTP resend and recovery will not work until real transactional delivery is configured. Google/LinkedIn IDs and secrets may remain blank until registered. Configure failover only when the secondary transport is really provisioned.

Deploy and record the API's stable production HTTPS URL. The API is a serverless deployment; PostgreSQL remains its persistence layer, not Vercel's temporary filesystem.

## 4. Apply migrations and start the existing workers

From a trusted operator environment with this source installed, set `DATABASE_URL` to the hosted production database **for that migration session only**, then run from `backend`:

```text
uv sync --frozen
uv run alembic upgrade head
uv run alembic current
uv run alembic check
uv run python -c "from sqlalchemy import text; from app.core.database import get_engine; connection=get_engine().connect(); print(connection.execute(text('SELECT 1')).scalar_one()); connection.close()"
```

Expect migration head `20261013_0009`, no new Alembic operations, and SELECT 1 output `1`. Never log the DATABASE_URL. Do not mistakenly run these against localhost and count that as a cloud migration. Clear the temporary environment override afterwards.

Use a long-running Linux container host for two services. On Render, create two **Background Worker** services connected to this repository, using **Docker** runtime and **Root Directory** `backend` (Dockerfile `./Dockerfile`). There is no public HTTP port for either service:

| Service | Command |
| --- | --- |
| Email worker | Use Dockerfile's default command, or `uv run --no-sync celery -A app.workers.email:celery_app worker --loglevel=INFO --queues=emails_auth,emails_default --concurrency=2` |
| Email scheduler | Docker command override: `uv run --no-sync celery -A app.workers.email:celery_app beat --loglevel=INFO --schedule=/tmp/careerpilot-celerybeat` |

Set `APP_ENV=production` and the **same production** `DATABASE_URL`, `REDIS_URL`, `AUTH_SECRET`, email provider credentials/sender and rate/retry settings on both services. Workers do not need OAuth client secrets. Leave `DATABASE_HOST_OVERRIDE` unset; it is for local Docker networking, not cloud routing. Run one scheduler only. Size provider quotas for the actual plan, monitor queue lag and database connection use, and configure alerts. The worker handles expired/superseded codes, bounded retries and quota/outage states; do not replace it with sending OTPs synchronously from requests.

## 5. Connect the frontend to the API

In the **frontend Vercel project**, add these Production values:

```dotenv
NEXT_PUBLIC_API_BASE_URL=/api/v1
API_PROXY_ORIGIN=https://your-api-project.vercel.app
```

`API_PROXY_ORIGIN` must be the actual API deployment's HTTPS origin, with no path, credentials, query string or fragment. Do not point it at the frontend itself. Redeploy the frontend; both browser API URLs and rewrite destinations are build-time configuration.

The browser calls `https://your-web-project.vercel.app/api/v1/...`; Next.js forwards it to the separate API. Host-only HttpOnly cookies therefore stay on the frontend domain, including the OAuth browser-binding cookie and session cookie. Do not point the browser directly at an unrelated API domain: its cross-site SameSite cookies would break this setup. Keep `FRONTEND_ORIGIN` and callback construction on the exact stable frontend origin, and keep Secure cookies enabled.

## 6. Configure production social sign-in

Create a separate production GitHub OAuth app to preserve localhost testing. Its homepage is your public frontend URL. Its exact **Authorization callback URL / Redirect URL** is:

```text
https://your-web-project.vercel.app/api/v1/auth/oauth/github/callback
```

Put that app's client ID/secret into the **backend project**, never frontend code. Redeploy the backend after changing environment values. Other users use this same application through the GitHub icon; they do not perform developer setup.

If enabling the others, register these on their respective developer apps:

```text
https://your-web-project.vercel.app/api/v1/auth/oauth/google/callback
https://your-web-project.vercel.app/api/v1/auth/oauth/linkedin/callback
```

Configure Google's audience/consent for the intended public users, rather than leaving only developer test accounts accessible. LinkedIn requires its Sign In with LinkedIn using OpenID Connect product permissions. Matching an existing email does not automatically merge accounts; the owner must sign in to the existing account and explicitly connect the provider in settings.

## 7. Verify before inviting people

1. Visit the frontend `/signup`, `/login`, `/signin`, and `/api/v1/auth/capabilities`. The proxy should respond successfully and show only the configured providers available. A health/capabilities response alone does not verify the database.
2. Use a separate browser profile and your own test GitHub account. Accept the terms on signup, click the icon, complete provider authorization yourself, and confirm a Passport appears. Refresh, sign out, and sign in again; the same account/UUID and data must remain.
3. Verify that a second account cannot read the first account's Passport/resumes/settings. Check recent-auth controls and provider linking; do not test by deleting real user accounts.
4. Once real email is configured, verify delivery through the worker, expiry, resend cooldown, password recovery and safe outage/retry feedback. Provider acceptance is not proof of inbox arrival.
5. Use `uv run python -m app.email_monitor` in the production environment for aggregate outbox state and Redis reachability. Never inspect/log plaintext OTP payloads or provider credentials.
6. Verify the production domain is intentionally accessible to visitors; keep development/preview deployments separate. Review privacy/terms, retention, backups, cost alerts and deployment security before accepting real user data.

Check trusted-proxy/client-IP handling before scaling shared IP rate limits; do not blindly trust spoofable forwarded headers. Keep auth query strings and request bodies out of hosting/edge logs too: the application's redaction does not configure third-party platform logging.

Repository upload and local checks are **not** a completed public deployment. Live Vercel builds, cloud migrations, cookies/OAuth consent and inbox tests remain to be performed on the configured services. Local Passport/resume/job records are not automatically uploaded with the source.

Official references: [Vercel Next.js](https://vercel.com/docs/frameworks/full-stack/nextjs), [Vercel build/root settings](https://vercel.com/docs/builds/configure-a-build), [Vercel environment variables](https://vercel.com/docs/environment-variables), [Vercel FastAPI](https://vercel.com/docs/frameworks/backend/fastapi), [Next.js rewrites](https://nextjs.org/docs/app/api-reference/config/next-config-js/rewrites), [Render workers](https://render.com/docs/background-workers), [Render Celery](https://render.com/docs/deploy-celery), [GitHub OAuth apps](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app).
