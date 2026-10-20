# Resume-first release

## Product flow

1. Visitors start at `/review`, without an account or a completed profile.
2. Upload a text-based PDF, DOCX, or UTF-8 TXT (3 MB maximum), or paste text.
3. Review/correct extracted content. Optional: paste a job description.
4. Run the readiness checks; expand any result to see its evidence and recommendation.
5. Edit and recheck, download PDF, or sign in to save a private editable resume.
6. Saved imports use existing owner-scoped resume/version tables. Restoring and duplicating preserve imported content. No schema migration is introduced.

## What evaluation actually does

The score is a published weighted checklist: contact (10), length (15), experience/projects section (20), education (10), skills section (10), quantified action-led lines (20), action-led writing (10), and supporting links (5). It is not an ATS simulator or hiring probability. Language recognition currently targets English headings and verbs. Skill coverage uses a finite, boundary-matched dictionary; unknown requirements, seniority, negation, proficiency, and eligibility need human review. The UI explains these limits.

No external AI key is needed. Existing unconfigured AI customization endpoints remain unavailable; the editor no longer shows an empty AI suggestions panel. No synthetic jobs, testimonials, evaluation results, credentials, or achievements are presented as real.

## Document handling

- PDF: verify signature, reject encryption and more than 10 pages, bound decoding work, stream sizes, page-tree traversal, and extracted text.
- DOCX: ZIP entry/expanded-size bounds; read document text without loading external resources or executing macros; reject XML entities/DTDs.
- Request middleware limits review bodies before multipart parsing; extracted text is limited to 60,000 characters and target descriptions to 20,000.
- Uploads may use temporary multipart spool storage during a request. Files are closed/discarded after extraction and never saved as documents.
- Public checks/export use the existing shared database rate-bucket mechanism (30 operations/hour per observed client address). An upload, check, and PDF export each count as an operation. Operators must verify their host's trusted-proxy address handling and size limits. The application does not blindly trust visitor-supplied forwarding headers; a shared proxy address can therefore share a bucket until trusted ingress is configured.
- Document text is not sent to external AI services. Analysis/export responses use `Cache-Control: no-store`.
- Saving is authenticated and reuses existing ownership checks. The source is marked `document_import`; extracted content is not silently treated as verified structured Career Passport records.
- A draft is put in tab-scoped session storage only when a visitor chooses to sign in to save it, and removed when restored. Start over clears the draft.

## Rendering fixes

The previous handwritten PDF generator emitted invalid `/Parent PAGES` references, did not wrap text, and replaced non-Latin characters with `?`. Export now uses ReportLab with packaged embedded Vera fonts, measured wrapping, automatic pagination, deterministic document metadata, and escaped paragraph input. Supported font glyphs depend on the packaged font; full coverage for every writing system is not claimed. PDF and HTML are independent renderings, not pixel-identical recreations of the uploaded file.

Preview HTML is displayed in a sandboxed iframe so document CSS cannot restyle the app. Selecting a historical version now also downloads that selected version. An explicitly empty hidden-section list correctly unhides all sections. Editor settings/content save in a single version transaction rather than two partially successful requests.

## UI and skills

Design direction: warm neutral surfaces, forest-green typography/actions, lime accents, Plus Jakarta Sans, clear navigation, and a real upload-first call to action. GSAP uses scoped `useGSAP`, `matchMedia` reduced-motion handling, transform/opacity animation, and cleanup on unmount. Core content is server-rendered and not hidden by base CSS.

### Shared-theme and spacing correction

The shared navigation no longer sits inside a `.product-site` container with `min-height: 100vh`; that wrapper reserved an entire empty viewport above workspace content. A dedicated application shell now keeps navigation and content adjacent. Shared CSS colour tokens and the existing workspace utility scales use the same forest/olive/warm-neutral palette as the homepage, including form controls and focus states. Authentication screens use that deliberate palette even when the device prefers dark mode. Their two-column presentation is scoped to `.auth-layout`, so account settings retain their normal single-column layout.

Google, GitHub, and LinkedIn symbols are visible on login/signup. Providers are enabled only after configuration checks succeed; an unavailable provider is visibly labelled and cannot initiate an OAuth request. Existing authentication-required responses and access controls are unchanged. Browser regression tests cover header-to-content geometry, form colours/focus, device colour schemes, provider availability, and mobile overflow.

### Authentication and account regression fixes

Provider continuation on the login page now includes a visible terms/privacy disclosure and records agreement when that action starts a new account. Signup retains its explicit checkbox and checks it before redirecting to a provider. If an older or direct OAuth attempt has no agreement, the API returns the visitor to signup with an explanation instead of displaying a generic login failure. Existing linked accounts can still authenticate without creating a new registration consent record.

Invalid callbacks no longer clear another pending attempt's browser cookie. Cancellation, expired browser state, missing verified email, and provider configuration failures have safe recovery messages. Server logs contain internal reason codes/exception types, never provider response bodies, authorization codes, access tokens, or email addresses. Unsupported providers return 404. Verified-email checks and explicit account-linking requirements remain in effect.

Account settings now explicitly submit profile, reauthentication, email-change, password-change, and deletion forms when their action buttons are clicked; the shared Button intentionally defaults to a non-submit button. Imported resume edits reject whitespace-only content and strip null characters before database persistence.

Regression coverage includes browser-observed OAuth request consent, signup gating, safe failure feedback, and account form submission, plus server-side consent/cookie/ownership tests and GitHub token/profile/private-email exchange through an HTTP mock transport. A real user's external GitHub authorization still requires that user's provider interaction; mocked provider checks do not claim to authenticate a personal GitHub account.

Installed locally and consulted:

```text
npx --yes skills add https://github.com/greensock/gsap-skills --agent opencode --yes
npx --yes --package ui-ux-pro-max-cli uipro init --ai opencode
python .opencode/skills/ui-ux-pro-max/scripts/search.py "career resume productivity SaaS" --design-system -p "CareerPilot" --motion 6 --density 4
```

Skill catalogs are local development assets, ignored in Git. GSAP source revisions are recorded in `skills-lock.json`. Restart OpenCode to discover newly installed skills automatically; their relevant guidance was read directly for this implementation.

## Validation

```text
backend: uv run ruff check .
backend: uv run pytest
backend: uv run alembic check
frontend: npm run lint
frontend: npm run typecheck
frontend: npm test
frontend: npm run build
frontend: npm audit --omit=dev
frontend: npx playwright install chromium
frontend: npm run test:e2e
```

Browser tests exercise real local upload, validation, evaluation, job-description comparison, PDF download, sign-in draft restoration, mobile navigation, reduced motion, and horizontal overflow. They require local PostgreSQL with migrations applied. Tests use synthetic resume content. Backend regression tests cover document parsing, PDF round trips, HTML escaping, import editing/restoration, ownership, and existing authentication/workspace behavior.

At release validation, the production npm dependency audit reports zero vulnerabilities. The full audit still reports nine transitive development-tool advisories (Tailwind/ESLint glob parsing and PostCSS selector parsing); do not interpret the production-only result as a clean full development audit. These require a separately tested toolchain upgrade/upstream fixes rather than a forced incompatible dependency downgrade. Backend tests also report the existing Starlette/httpx test-client deprecation warning. Windows browser-test startup can log a Python asyncio connection-reset warning when navigation aborts a request; the actual browser flows are asserted independently.

## Vercel rollout

Push to the Git-connected production branch to trigger the existing frontend and backend Vercel projects. Both deployments must complete: deploying only the frontend leaves new `/api/v1/review/*` routes unavailable. Existing `NEXT_PUBLIC_API_BASE_URL=/api/v1` and `API_PROXY_ORIGIN` settings remain required. Dependencies are locked in `frontend/package-lock.json` and `backend/uv.lock`; no new secrets or DB migrations are required for review/import.

Production release checks: visit `/review`, upload a synthetic document, evaluate, export, then sign in with a configured provider and save/edit/restore a resume. Confirm the production database and ingress limits. Email delivery still requires the existing real provider/worker setup; OAuth configuration availability does not itself prove a completed real-user login. Production monitoring, backups, provider credentials, and a live deployment verification cannot be replaced by passing local tests.
