# CareerPilot mock interview platform

## Existing architecture and integration

- Next.js 15.5.28 App Router, React 19, TypeScript, npm/package-lock, Tailwind 3,
  shared Button/Card/Input components and the existing sage/forest workspace palette.
- FastAPI, Pydantic 2, SQLAlchemy, PostgreSQL, Alembic, uv/uv.lock, httpx,
  pypdf and the existing upload limits/extractor. No second framework, database,
  authentication system, PDF parser, chart package or media wrapper was installed.
- Existing HTTP-only sessions, same-site mutation enforcement and
  `require_authenticated_request` protect every interview operation. Google,
  LinkedIn and password login continue through their existing flows.
- Existing resume versions are read only after checking ownership. Interview
  context is an independent snapshot; editing/deleting a resume does not rewrite
  interview history. Deleting an account cascades to its interviews.
- Existing resume AI remains its existing unavailable-provider/grounded-rules
  boundary. Interviews use a separate, real Gemini REST integration. There are
  no canned interview questions or fabricated scores when credentials are absent.

## Research: actual source downloads

All five URLs cloned successfully with `git clone --depth 1`, into separate
directories beneath `%LOCALAPPDATA%\Temp\opencode\interview-*`. No repository
installation scripts or dependency installations were run.

| Repository / checked commit | Actual source inspected | Findings / adaptation |
| --- | --- | --- |
| [ad-Dinesh/ai-mock-interviewer](https://github.com/ad-Dinesh/ai-mock-interviewer) `1f758812151fdee8c859623d1f14b47180943165` | `package.json`, `utils/schema.ts`, `lib/Prompt.ts`, `app/api/generate/route.ts`, `components/ui/RecordAnswer.tsx`, Drizzle migrations | Next 16/Clerk/Neon/Drizzle; interview + answer tables, Gemini question batch, react-webcam and speech wrapper. Adopted persisted interview/turn separation concept, not its new auth/database or automatic answer submission. |
| [KaranChandekar/ai-interview-prep](https://github.com/KaranChandekar/ai-interview-prep) `0488fa46d7e2cf97e0a0f5fa20ed543d9b0d2bd6` | `package.json`, `src/lib/{ai,schemas,difficulty,speech,scoring}.ts`, interview/evaluate/report API routes, results page | AI SDK 6/Google/Zod, streamed chat, bounded schema scores, recent-score difficulty adjustment, browser speech; results rely on sessionStorage. Reimplemented schema/rubric/difficulty ideas in Pydantic and server-side persistence, rather than trusting client-supplied scores. |
| [harsha8966/ai-interview-react](https://github.com/harsha8966/ai-interview-react) `35aba34bbec9b1dd40d3ba268f42eb097ca0fee0` | `package.json`, `src/components/interview/RecordAnswerSection.jsx`, `QuestionsSection.jsx`, `utils/schema.js`, `server/index.js` | Vite/React 18/Express/Clerk/Drizzle, native speech recognition and camera stream, Gemini proxy. Reimplemented explicit stream controls, editable transcript and text fallback; retained our server-owned records rather than browser database writes. |
| [mockmate-app/mockmate](https://github.com/mockmate-app/mockmate) `75563f12ec2137e71fa5ef4f2de734ef363d947a` | frontend manifest, live room, backend `agents/{question_generator,interview_engine,feedback_compiler}.py`, backend routing/config, `LICENSE` | Next 16/Better Auth, FastAPI, Gemini Live/ADK/Vertex, Firestore/PubSub, audio WebSockets. Useful participant/speaking/transcript and topic-coverage patterns. Reimplemented a turn-based flow compatible with existing serverless hosting. Did not import cloud infrastructure, billing or posture/frame analysis. |
| [abdul-mujeer/Ai-Interview-Assistant](https://github.com/abdul-mujeer/Ai-Interview-Assistant) `ebb2aeee672e2282fa49e3ba635e78d4c82312cd` | frontend manifest, `backend/services/{resume_parser,gemini_service,database}.py`, interview/resume routes and schemas, `components/VoiceRecorder.tsx` | Next/FastAPI/MongoDB, skill-aware prompts, PDF extraction, per-answer feedback and improvement plan. Its VoiceRecorder contains simulated transcription and provider errors can become numeric scores; neither behavior was adopted. Reused our existing real PDF extractor; provider failures remain explicit errors. |

No test/spec files were found by targeted test/spec filename searches in these
five shallow checkouts; their package scripts did not provide test commands.
Four repositories had no visible LICENSE file. MockMate has MIT copyright
2026 MockMate. No upstream code/assets were vendored or copied into this feature;
implementation is original, using the architectural ideas above. Thus no copied
source license notices were removed. This document attributes research sources.

## Tooling and compatibility decisions

**Coding-agent skill:** reviewed the actual Vercel skill source, then installed
`vercel-react-best-practices` using the documented skills CLI:

```powershell
$env:DISABLE_TELEMETRY='1'
npx --yes --ignore-scripts skills@1.7.4 add vercel-labs/agent-skills --skill vercel-react-best-practices --agent opencode --yes
```

Source checkout: `vercel-labs/agent-skills` at
`063bee94c3f4df8453406c830b0a7df0f2860278`. Installation is in ignored
`.agents/skills/vercel-react-best-practices`; `skills-lock.json` tracks its source
and hash. The CLI requires Node >=22.20; local Node 24 supports it. It is not an
application/CI dependency (CI can remain on Node 20). Restart OpenCode to load
the newly installed skill automatically. Reviewed guidance was used for
parallel independent fetches, scoped components and media-effect cleanup.

**Application dependencies:** none added. Vercel AI SDK + Zod were evaluated;
they would duplicate the existing Python AI/API validation boundary. Existing
httpx + Pydantic perform bounded REST requests and structured-output validation.
Existing pypdf parses uploaded PDFs. Native getUserMedia/SpeechRecognition/
speechSynthesis handle browser media. Accessible SVG and native meters provide
charts. Existing Playwright/pytest cover the feature. No npm application
lockfile update was necessary.

**External API:** Gemini Developer API, configured only on the backend. Direct
ai.google.dev documentation retrieval failed with transport errors in this
environment; request/response structure was cross-checked against official
`googleapis/python-genai` source and its structured JSON configuration, with
REST-transport contract tests. Documentation for setup/quotas remains:
https://ai.google.dev/gemini-api/docs and https://ai.google.dev/gemini-api/docs/rate-limits.

**GitHub integration:** reviewed the official GitHub MCP remote-server docs at
https://github.com/github/github-mcp-server/blob/main/docs/remote-server.md.
It requires an authenticated client setup; no credentials or new account were
provisioned, and no unauthorized integration was enabled. Existing Git and
Playwright tools were sufficient. No ChatGPT plugin was installed through npm.

## Functionality and boundaries

- `/interviews`: select a saved resume or upload a text PDF / paste resume text;
  role, optional job description, six interview types, difficulty 1–5, duration
  5–90 minutes and 1–20 total questions (including follow-ups).
- `/interviews/[id]`: one question at a time, spoken question control, local
  webcam preview, microphone dictation with visible final/interim transcripts,
  editable text fallback, timer, progress, pause/resume/end, saved transcript.
- `/interviews/[id]/report`: score 0–100; accuracy/completeness, relevance,
  clarity; per-question strengths, weaknesses, corrections, sample answer and
  revision recommendations. History includes recent-score chart and pagination.
  Retake makes an independent session and generates a new first question.
- Gemini questions incorporate minimized resume evidence, role, job description,
  prior answers and a suggested follow-up. Recent scores adjust difficulty within
  bounds; near-duplicate questions and wrong requested categories are rejected.
- Evaluation JSON is Pydantic-validated and range-bounded. Score is the equal
  mean of accuracy, relevance and clarity. Overall report is the mean over
  **submitted answers**, with answered/planned counts shown; unanswered questions
  are not silently assigned zero or treated as passed.
- Missing keys, bad credentials/model, malformed/incomplete AI output, quota,
  timeout and network errors are explicit. AI failures never become fake scores.
  Provider timeouts return 504 and temporary provider outages return 503. A
  deployment awaiting the interview migration returns an actionable 503 for
  interview routes; existing resume/auth routes remain independent.
  Evaluation is saved before generating the next question, so a failed follow-up
  cannot discard the preceding answer. Identical answer retries are idempotent.
- Optimistic revisions prevent concurrent writes from silently overwriting
  sessions. Browser drafts are question-bound, so a progress reload cannot apply
  an old answer to a different question. Unsubmitted text is memory-only and can
  be lost on leaving/reloading the page; a beforeunload guard is included.
- Server elapsed time enforces duration, including time after closing the tab.
  A pause stops elapsed time. Expiry is reconciled by reads and mutations; there
  is no always-running background worker required to expire sessions.
- All session endpoints enforce server-side ownership, including retake/delete.
  AI/upload requests use a shared database rate bucket (100/hour/account).
  Interview responses are no-store. No API key is exposed to the browser.
- Only career section evidence (max 16,000 characters) goes into resume context;
  header/name/contact and professional links are omitted. Common email, phone
  and URL patterns are redacted from evidence, job description and AI-bound
  answers. Redaction is best-effort, not guaranteed anonymization.
- No MediaRecorder, audio/file storage or webcam-frame transmission is used.
  Camera is local only. Browser dictation may use the browser vendor's external
  service; the UI/privacy page explains this. Scores never use appearance,
  facial expressions, personality, honesty or intelligence.

## Backend endpoints

All routes below are under `/api/v1` and require the existing authenticated
session. Mutations also inherit the existing same-site/CSRF checks.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/interviews/capabilities` | Configured flag and model; never returns key |
| POST | `/interviews/extract` | Existing PDF extractor, <=3 MB, no file retained |
| GET | `/interviews?offset=0` | Owner-only history, 50/page |
| POST | `/interviews` | Authorized resume source, generate first question, save session |
| GET | `/interviews/{id}` | Saved state and computed report |
| POST | `/interviews/{id}/answers` | Validate current question, evaluate and persist answer |
| POST | `/interviews/{id}/next` | Adaptive next question; safe when a question is already pending |
| POST | `/interviews/{id}/control` | `{ "action": "pause" | "resume" | "end" }` |
| POST | `/interviews/{id}/retake` | New independent session with same settings/context |
| DELETE | `/interviews/{id}` | Delete session, answers and report |

## Configure and run

1. Obtain your own Gemini Developer API key through Google AI Studio, under an
   eligible free-tier project/model/region. Check current terms, data handling
   and quota eligibility before sending personal data. Free access is **not
   unlimited**; RPM/TPM/daily limits and available models can change. No billing,
   external account or paid service was enabled by this implementation.
2. Add to the existing private backend environment (not a `NEXT_PUBLIC_` variable):

   ```dotenv
   GEMINI_API_KEY=your-own-key-here
   GEMINI_INTERVIEW_MODEL=gemini-3.8-flash
   ```

   Keep the key blank to disable interview generation. Select a currently
   available, structured-output-capable Gemini model for your account if the
   default model is unavailable. Restart the backend after changing settings.
3. Review the additive migration
   `backend/alembic/versions/20261023_0010_interviews.py`. It creates one table;
   it does not rewrite existing resume/auth records. It was applied and checked
   against the existing **local development PostgreSQL only**. Production
   migration/deployment remains a separate authorized operation.
4. From `backend`:

   ```powershell
   uv sync
   uv run alembic upgrade head
   uv run uvicorn app.main:app --reload --port 8000
   ```

   From `frontend`, in another terminal:

   ```powershell
   npm ci
   npm run dev
   ```

5. Sign in through the existing login and open http://localhost:3000/interviews.
   Camera/microphone need HTTPS or localhost. Chrome/Edge typically support Web
   Speech dictation; availability and network requirements vary. Use text when
   dictation or permissions are unavailable. Spoken questions require a user
   click and a browser speech-synthesis engine.

For Vercel, add Gemini variables to the **backend** project, review/apply the
migration through your authorized database workflow, then deploy backend and
frontend. Existing same-origin API proxy configuration remains in use. This is
a turn-based REST interview with browser speech, not Gemini Live bidirectional
audio/WebSocket streaming, which would require different hosting and quotas.

## Verification

- Full backend suite: **269 passed** (27 new interview tests); existing
  Starlette/httpx deprecation warning only. Ruff passed.
- Frontend lint, TypeScript, production build and **10 unit tests passed**.
  Full Playwright suite: **36 passed**, including **12 new interview browser
  cases** across desktop/mobile. Full npm audit: **0 vulnerabilities**.
  Room/report screenshots were inspected for desktop/mobile layout.
- Publication/credential audit passed against all proposed files using a
  temporary Git index; the user's actual staging index was left unchanged.
- Local reviewed migration applied; `uv run alembic check`: no pending drift.
- New browser scenarios exercise configuration, submissions, follow-up, reports,
  camera tracks/cleanup, permission denial, text retention, pause/resume,
  transcript controls, missing-key behavior, history, retake and multi-tab drafts.
- Camera/microphone tests use Chromium fake media devices, not physical hardware.
  Speech recognition/synthesis events are controlled in browser tests; no live
  test audio is sent to browser speech services. API transport is stubbed for
  browser state-machine tests. Backend tests use real auth, database transactions,
  actual PDF parsing and mocked Gemini HTTP transport.
- The operator subsequently configured a local Gemini key and requested
  `gemini-3.8-flash`. Google's model catalog listed it for content generation;
  both the example and default model were updated to match. A synthetic live
  structured-question probe timed out, and a second minimal generation probe
  returned HTTP 503. Therefore successful live question/evaluation generation
  is **not yet verified**; these failures are surfaced, not replaced with mocks.
  Physical camera/microphone and real browser speech-service quality also need
  user-device testing. Model feedback is coaching, not an authoritative technical
  reference; reports explicitly say to check suggestions.

The local `.env` key remains ignored and is not published. A local key does not
automatically configure Vercel: the backend project must have its own protected
environment variable. Production migration and environment configuration must be
completed through the authorized operator workflow before activation.

## Main files

- `backend/app/{models,schemas}/interview.py`
- `backend/app/services/interview_ai.py`
- `backend/app/api/routes/interviews.py`, API router registration
- `backend/alembic/versions/20261023_0010_interviews.py`
- `backend/app/core/config.py`, `.env.example`
- `frontend/app/interviews/**`, `frontend/components/interviews/**`
- `frontend/components/site-header.tsx`, `frontend/app/privacy/page.tsx`
- `backend/tests/test_interviews.py`, `frontend/tests/e2e/interviews.spec.ts`
- `skills-lock.json`, this report
- `README.md`, `DATABASE_SCHEMA.md`
