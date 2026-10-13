# CareerPilot security baseline

## Authentication and email upgrade

See [AUTHENTICATION_AND_EMAIL.md](AUTHENTICATION_AND_EMAIL.md) for OTP browser binding, normalized email uniqueness, explicit social identity linking, recent-auth checks, encrypted outbox delivery, bounded retries, and operational limitations. Live email and OAuth credentials remain unconfigured; passing local tests is not a production security certification.

## M6 safeguards and remaining boundaries

This is not a production security certification. Next.js was updated to 15.5.27, React to 19.0.8; a compatible PostCSS 8.x override removes the vulnerable transitive version. Re-audit before deployment. Development-tool advisories and upstream deprecations remain tracked in the milestone report.

Ingestion uses a fixed HTTPS API host, no redirects, no user-controlled fetch destinations, bounded response size/time/pages, and no automatic retries. Listing links have an exact host allowlist. No candidate data is transmitted. External descriptions are plain text, escaped by React, never instructions or executable content. Provider presence does not prove employer identity; payment-language detection is a fallible heuristic. No application execution integration exists.

All mutation routes now share the existing explicit-origin guard. SameSite/HTTP-only cookies remain necessary; production CSRF/CSP/TLS review is still required. Company-name grouping is not identity verification.

Original migration files are unchanged. The new migration is additive. Metadata now declares pre-existing indexes/constraints/timezones so autogeneration will not propose dropping them. Sync leases and ingestion use short transactions; HTTP runs without row locks. Failed batches keep jobs and store a redacted error category. Tests use rollback transactions. Private checkpoint database dumps must never be published.

## Foundation controls

- Configuration is environment-driven. `.env` is ignored and `.env.example` contains placeholders only.
- Backend secrets are modeled as non-repr configuration fields; frontend code has no secret configuration.
- SQLAlchemy is the sole database access layer; future repositories use parameterized queries and owner scoping.
- CORS permits only the configured frontend origin and explicitly lists credentials, methods, and headers.
- Initial table design uses UUIDs, foreign keys, database uniqueness constraints, and cascade behavior only for direct user-owned profile data.
- The health endpoint reveals configuration state, not credentials, database details, stack traces, or secret values.

## Required before authentication is enabled

The Milestone 2 authentication baseline now uses Argon2id hashing with constant-time verification. Sessions, verification tokens, and reset tokens are cryptographically random; only an HMAC-SHA-256 reference is stored. Verification/reset tokens expire and are atomically marked used. Browser sessions are HTTP-only and SameSite=Lax, and `SESSION_COOKIE_SECURE=true` is required in production.

Login failures are generic and rate-limited in-process by IP/identifier. Explicit cross-site browser mutations are rejected by origin checking. Sensitive actions require an active server-side session; password change and account deletion additionally require password confirmation. Security events redact passwords and tokens.

Before public production deployment, replace the development `AUTH_SECRET`, use a distributed rate-limit store, configure HTTPS plus trusted-proxy/security headers/CSP, and implement OAuth authorization-code/PKCE callbacks with encrypted provider-token storage where tokens are needed.

## Authorization standard

Every protected endpoint resolves identity from its server-side session, verifies the role/permission needed, and filters target resources by owner before reading or modifying them. IDs from URLs, forms, and request bodies are identifiers, not authorization. Tests must cover User A attempting to access each User B resource class.

Career Passport routes follow this rule directly: the authenticated session supplies `user_id`, list queries filter by it, item updates/deletes require both row ID and owner ID, and experience/project skill relationships reject skill IDs not owned by the same user. The frontend does not make ownership decisions.

Resume routes apply the same owner filter to resumes, versions, PDFs, previews, and customization reviews. Version snapshots contain only Passport-derived data plus explicitly user-authored presentation overrides. Customization evidence must reference current Passport source IDs, provider metadata rejects credential-like keys, and approval requires an explicit user action. Resume deletion cascades only resume records; it cannot delete Career Passport data.

Job routes treat jobs, companies, source metadata, verification state, and application URLs as global source-owned data. No normal user endpoint can create, update, verify, or rewrite a job. Browse, match, recommendations, and company reads require an authenticated session; save/unsave operations scope the `saved_jobs` row by the authenticated user ID. Cross-user saved-job access is rejected by owner filtering. Source adapters are backend-only and must use an official/licensed API or authorized feed; secrets and source configuration never enter frontend bundles.

## Data handling

Passwords, API keys, raw session tokens, OAuth tokens, reset tokens, and provider secrets must not enter logs, analytics, error responses, exports, or frontend bundles. Files require allowlisted media/document types, size limits, malware scanning before availability, isolated storage keys, and authorization-checked downloads. Account deletion revokes active credentials before data deletion/anonymization begins.
