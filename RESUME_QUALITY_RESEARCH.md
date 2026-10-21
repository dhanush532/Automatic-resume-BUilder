# Resume quality: source review and implementation notes

## Scope and diagnosis

Application changes are confined to resume-content processing, tailoring,
evaluation, themes, preview controls, and export. No routes, database models,
authentication, provider implementations, framework versions, or runtime
dependencies were changed.

Reproduced against commit `8f8eada` before application edits:

- `render_pdf` sent every `document_import` directly to `_pdf_imported`, bypassing
  the six layout renderers. Modern/Sidebar/Creative imports had identical PDF
  sizes, while Minimal/Editorial differed only by typeface.
- `review_resume` treated any digit on an action-led line as impact. Two lines
  mentioning Python 3.12/Node.js 20 and years 2024/2025 passed the impact check.
- `find_skills` was also used as candidate evidence. “No experience with
  Kubernetes” incorrectly satisfied a Kubernetes requirement.
- `resume_content` interpreted a partial section order as an allowlist, silently
  dropping omitted qualifications instead of respecting `hidden_sections`.
- Custom pale accents could produce white-on-pale mastheads and pale text on white.
- The HTML bullet pseudo-element used a Python octal escape rather than a CSS
  Unicode escape. Failed thumbnail requests remained in “Rendering…” indefinitely.

## Reference repositories inspected

Public repositories were inspected through read-only source fetches and shallow
Git checkouts; no connected GitHub MCP or MagicPath tool was exposed. No external
repository install scripts or application code were executed.

| Repository / inspected commit | Source examined | Applied ideas |
|---|---|---|
| [Kiranism/cvtailor](https://github.com/Kiranism/cvtailor), `d6d6d78c4d3c16344d790e690abb3f989530b92d` | README, `src/server/services/ai-resume.ts`, `resume-guidance.ts`, `src/features/resume/templates/templateNine.tsx` | Section-aware tailoring, validated provider output, separate entry headings and metadata, actual-PDF preview workflow |
| [subho57/resume-tailor](https://github.com/subho57/resume-tailor), `2f716b7eb61d6b1bc1c884e4a95a494583d1eaec` | README, `src/render.ts` | Separate content/theme contracts, preserve canonical sections omitted from ordering, defensive handling of generated content |
| [chijiang/resume-editor](https://github.com/chijiang/resume-editor), `616b5b930a690480ce81e0999ec0b3572d95cbec` | README, `scripts/generate_pdf.py`, `assets/css/minimal.css` | Reusable document themes, explicit A4 layout, restrained heading/technology hierarchy, local/offline export |

These projects use MIT licenses. This implementation adapts design/architecture
ideas independently; it does not vendor their application source. Their
React-PDF, DOCX/LibreOffice, and Playwright/Python stacks were not installed.
Suggestions to invent likely skills, require metrics in every bullet, or present
keyword coverage as hiring suitability were deliberately not adopted.

## MiniMax skills and compatibility

Inspected [MiniMax-AI/skills](https://github.com/MiniMax-AI/skills) at
`60aaae52bb2af8162732751a4332f62a5fef518b`:

- README and `.opencode/INSTALL.md`, including Windows installation notes.
- `skills/frontend-dev/SKILL.md` and its script/dependency entry points.
- `skills/minimax-pdf/SKILL.md`, `design/design.md`, and `scripts/make.sh`.

The project-local `.opencode/skills/frontend-dev/SKILL.md` and
`.opencode/skills/minimax-pdf/SKILL.md` installations were verified byte-identical
to the inspected source. Existing matching installations were reused; the
project-scoped installation copies only these two folders if absent. The folders
remain ignored development tooling, not production application dependencies.
OpenCode discovers this standard skill layout; no plugin or MCP configuration is
needed. Quit and restart OpenCode after installing skills to refresh discovery.

Applied guidance: coherent typography/spacing tokens, a single restrained accent,
readable foreground contrast, explicit loading/error/retry states, offline document
rendering, and inspection of actual rendered PDFs. Document-sized type scales are
used rather than poster/cover typography. The skills' media-generation scripts,
API-key configuration, global Playwright install, `make.sh fix`, and automatic
pip installers were not run. The application already has ReportLab, pypdf, React
19, Next.js 15, Tailwind 3, and Playwright test tooling; no replacement is needed.

## Targeted implementation

- `resume_document.py` recognizes explicit imported headings and short
  title-plus-bullet project boundaries without inferring employers, dates, or facts.
  Ambiguous prose stays together. Long preambles move into document flow rather
  than becoming an unbreakable masthead.
- Clearly structured imports now use the same themes as profile-based resumes.
  Original imported text remains stored and editable. Unstructured text retains
  the conservative readable-text fallback.
- Imported project blocks can be reordered for a target job without moving
  bullets between projects or rewriting ongoing work into completion.
- Candidate evidence screening excludes explicit lack of experience and future
  learning plans; requirement detection still uses the full skill dictionary.
  This is bounded English-language screening, not a semantic guarantee.
- Provider output of an unexpected shape is rejected without discarding the
  grounded draft. Per-record skill evidence is retained in `job_target`.
- Generated summaries select intact candidate-authored bio sentences and verified
  skills/project names rather than copying an achievement bullet a second time.
- Creative Modern now uses open typography and vertical accents rather than
  repeating Modern Professional's filled bars. Pale custom colors retain readable
  foregrounds. Existing theme keys and ATS alternative are preserved.
- Filled section headings use smaller internal/external gaps, avoiding a separate
  Education page in the short tailored fixture without reducing body type size.
- Evaluation displays evidence and actionable feedback rather than a score ring;
  legacy API score fields remain compatible. Dates, versions, and future targets
  are excluded from impact evidence.
- Live preview and thumbnail failures are visible and retryable. Invalid imported
  text reports its minimum length instead of showing an endless update state.

## Verification and reproducibility

From `backend`, use the existing QA harness with optional ephemeral PyMuPDF:

```text
uv run --with pymupdf python ../scripts/resume-pdf-qa.py ../.runtime/resume-research-long
uv run --with pymupdf python ../scripts/resume-pdf-qa.py ../.runtime/resume-research-short --short
uv run --with pymupdf python ../scripts/resume-pdf-qa.py ../.runtime/resume-research-imported --imported
uv run --with pymupdf python ../scripts/resume-pdf-qa.py ../.runtime/resume-research-light --short --light-accent
uv run --with pymupdf python ../scripts/resume-pdf-qa.py ../.runtime/resume-research-backend --short --target backend
uv run --with pymupdf python ../scripts/resume-pdf-qa.py ../.runtime/resume-research-ml --imported --target ml
```

Each run creates real PDFs, individual page PNGs, all-page contact sheets and a
JSON report. Checks cover evidence occurrence, marker reading order, text bounds,
line overlaps, blank pages, and links. Backend regressions also extract PDF text
with pypdf, check source immutability and theme-independent content, and cover
imported project relevance, unknown provider output, contrast, negative skill
mentions, partial ordering, and long preambles. Generated files remain ignored
under `.runtime/`.

### Completed checks

- `uv run ruff check . ../scripts/resume-pdf-qa.py`: passed.
- `uv run pytest --tb=short`: **227 passed**, one existing Starlette/httpx
  test-client deprecation warning. The existing local Docker/PostgreSQL service
  was started for transaction-isolated tests; its configuration/schema was not
  changed.
- `npm run lint`, `npm run typecheck`, `npm test`: passed (**10 unit tests**).
- `npm run build`: passed.
- `npm run test:e2e`: **22 passed**, desktop and mobile, including actual-PDF
  editor/download checks, error/retry recovery, and real upload/review/export.
  Editor API transport is mocked in its dedicated browser tests; the PDF bytes
  used there are generated by the application's real renderer.
- `npm audit --omit=dev`: **zero vulnerabilities** in production dependencies.
- Final visual QA: **42 PDFs / 82 pages**, all seven stored templates under all
  six scenarios above. Every page was rasterized and reviewed in all-page contact
  sheets, with representative full-size inspection. All reports passed marker
  uniqueness/order, text bounds, line-overlap, blank-page and link checks.
  The Modern/Student tailored short documents were regenerated and reinspected
  after the final spacing correction; both are now one page.
- `git diff --check`: passed.

The current provider boundary remains unchanged. The configured implementation
still reports external AI unavailable; grounding/ranking fallback is explicitly
labelled rather than being presented as a live model. These checks establish the
tested document fixtures and local flows, not universal ATS compatibility or a
completed production login/deployment.
