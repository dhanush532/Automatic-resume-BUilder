# Resume studio and supplied-document repair

## Reproduced issues

The supplied extracted PDF text had bullets on project headings, technologies,
status labels, and sentence continuations. Coursework & Achievements was being
treated as part of Projects. A page footer interrupted an unfinished sentence.
The raw source is retained privately under ignored `.runtime/`; the committed
test fixture is anonymized.

Import repair now recognizes title/technology/status sequences, rejoins bounded
lowercase, indented, and connector-led wrapping, recognizes the combined heading,
and removes explicit extraction page markers and indented page-number footers.
It preserves ongoing-work labels and existing claims. Short imported project
entries stay together where practical; oversized entries can still paginate.
Technology/status metadata appears below titles, before substantive bullets.
Bare LinkedIn/GitHub links now receive HTTPS PDF annotations.

## UI and hidden failures

- Resume studio header, restrained surfaces, theme-selection feedback, and scoped
  GSAP transitions with cleanup and reduced-motion support.
- Partial target-job input blocks creation instead of silently creating a master.
- Screenshot inspection revealed blank native PDF-plugin frames despite valid
  PDF bytes. A lazy-loaded PDF.js viewer now paints actual pages and a selectable
  text layer, including first-page thumbnails. Export still uses the same bytes.
- Browser tests now require painted canvases and text-layer content, not just a
  Blob URL, and exercise desktop/mobile/reduced-motion behavior.

## Tool research and installations

- [Microsoft Playwright MCP](https://github.com/microsoft/playwright-mcp): inspected
  official OpenCode configuration, npm engines/dependencies/lifecycle scripts and
  integrity metadata. Installed pinned `@playwright/mcp@0.0.83` in the npm tool
  cache and configured `.opencode/opencode.json` (ignored local development config).
  An actual stdio handshake exposed 25 tools, opened the public review page, and
  closed the browser successfully. Restart OpenCode to load the new integration.
  Isolated tool-dependency audit: zero vulnerabilities. This release depends on an
  upstream alpha Playwright build; it remains development tooling only.
- [Mozilla PDF.js examples](https://mozilla.github.io/pdf.js/examples/): added
  pinned `pdfjs-dist@4.10.38`, compatible with the existing Node 20 CI and React 19
  application. The latest major requires newer Node; no runtime upgrade was needed.
  The worker is bundled locally by Next.js, not fetched from a CDN, and evaluation
  support is disabled. The package has no lifecycle install scripts; installation
  used `--ignore-scripts`.
- Existing `gsap` and `@gsap/react` are reused; no second animation library.
- The final audit identified critical advisories affecting Next.js 15.5.27.
  Updated `next`, `@next/third-parties`, and `eslint-config-next` to the compatible
  **15.5.28 patch**, then pinned the patched `postcss-selector-parser` `^7.1.6`
  override used by Tailwind 3's build pipeline. The full npm audit is now clean,
  verified by a production build and the rendered-style browser suite.

## Follow-up hardening

- Job-targeted drafts now rank repaired projects whose extracted title is
  followed by technology or project-status metadata, instead of leaving those
  blocks in their original position.
- Provider-supplied rewrite requests must carry a non-empty string record ID and
  string section/field before any lookup, so malformed provider output cannot
  match an unidentified record or raise during tailoring.
- Creating a job-targeted draft is blocked while the editor has unsaved content;
  the UI explains that the draft uses the saved version instead of silently
  tailoring stale text.
- The PDF.js text layer is cancelled and tearing down safely on unmount, and
  thumbnail generation skips near-empty imported text.

## Verification performed

- Backend lint and full suite: **242 passed**, existing Starlette/httpx warning.
- Frontend lint, TypeScript, **10 unit tests**, production build on Next 15.5.28:
  passed. Full desktop/mobile browser suite: **24 passed**.
- Local PostgreSQL was offline during two attempts. Starting the existing Docker
  service restored connectivity; complete reruns passed. No schema/config change.
- Supplied text: generated all seven themes, **14 PDF pages**, rasterized and
  visually inspected all-page sheets. All reports passed bounds, line overlaps,
  project-heading occurrence/order, and blank-page checks. Private verification
  confirmed **3 projects / 13 substantive bullets**, preserved source words in
  the structured model, extracted dates/grades/status, and searchable PDF text.
- Anonymized tests cover title/bullet attachment, continuation repair, footer
  removal, metadata separation, preservation of independent action bullets,
  project ranking after repair, and malformed provider edits.

Corrected PDFs are local in `.runtime/supplied-corrected/`; Technical ATS is
`ats_readable.pdf`. None of the supplied personal details are added to Git.
This work fixes reproduced defects; it cannot establish that every unknown input
or all possible hidden platform defects are resolved.
