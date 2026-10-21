import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";

const id = "00000000-0000-4000-8000-000000000123";
const cors = { "Access-Control-Allow-Origin": "http://localhost:3000", "Access-Control-Allow-Credentials": "true" };
const templates = [
  { id: "theme-one", name: "Technical ATS", display_name: "Technical ATS", template_key: "ats_readable", description: "Linear document", ats_safe: true },
  { id: "theme-two", name: "Elegant Editorial", display_name: "Elegant Editorial", template_key: "professional", description: "Editorial gutter", ats_safe: true },
];
let pdf: string;

test.beforeAll(() => {
  // Use a real application-generated PDF, not an invalid placeholder document.
  pdf = execFileSync("uv", ["run", "python", "-c", "import sys,base64; sys.path.insert(0,'tests'); from resume_quality_fixture import quality_snapshot; from app.services.pdf import render_pdf; print(base64.b64encode(render_pdf(quality_snapshot(False),'ats_readable')).decode())"], { cwd: resolve(process.cwd(), "../backend"), encoding: "utf8" }).trim();
});

test("editor previews actual PDF bytes and preserves content while changing presentation", async ({ page }) => {
  const previews: { template_id: string; include_pdf: boolean; ats_safe?: boolean; edits: { summary_override?: string; design?: { font: string } } }[] = [];
  await page.route("**/api/v1/resumes/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/templates")) return route.fulfill({ headers: cors, json: templates });
    if (path.endsWith("/preview")) {
      previews.push(route.request().postDataJSON());
      return route.fulfill({ headers: cors, json: { pdf_base64: pdf, html: "Not used for document preview" } });
    }
    return route.fulfill({ headers: cors, json: { id, name: "Document QA", template_id: templates[0].id, template: templates[0], latest_version: { id: "version-one", version_number: 1, content_snapshot: { profile: { headline: "Engineering student", bio: "Original evidence summary." }, resume_meta: {} } } } });
  });
  await page.goto(`/resumes/${id}`);
  const frame = page.getByTitle("Live resume preview", { exact: true });
  await expect(frame).toHaveAttribute("src", /^blob:/);
  await expect(frame).not.toHaveAttribute("srcdoc");
  const actualBytes = await page.evaluate(async () => {
    const src = document.querySelector<HTMLIFrameElement>('iframe[title="Live resume preview"]')!.src;
    const bytes = new Uint8Array(await (await fetch(src.split("#")[0])).arrayBuffer());
    return btoa(Array.from(bytes, byte => String.fromCharCode(byte)).join(""));
  });
  expect(actualBytes).toBe(pdf);
  await page.getByRole("textbox", { name: "Summary", exact: true }).fill("Edited and verified evidence summary.");
  await page.locator('input[name="theme"]').nth(1).check();
  await page.getByRole("combobox", { name: "Typeface", exact: true }).selectOption("serif");
  await expect.poll(() => previews.some(item => item.template_id === "theme-two" && item.edits.summary_override === "Edited and verified evidence summary." && item.edits.design?.font === "serif" && item.include_pdf)).toBe(true);
  await expect(page.getByRole("textbox", { name: "Summary", exact: true })).toHaveValue("Edited and verified evidence summary.");
  const download = page.getByRole("link", { name: "Download PDF", exact: true });
  await expect(download).toHaveAttribute("href", /^blob:/);
  const event = page.waitForEvent("download");
  await download.click();
  expect((await event).suggestedFilename()).toBe("resume.pdf");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("preview failures are visible and cannot download an out-of-date draft", async ({ page }) => {
  let fail = false;
  await page.route("**/api/v1/resumes/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/templates")) return route.fulfill({ headers: cors, json: templates });
    if (path.endsWith("/preview")) return fail
      ? route.fulfill({ status: 422, headers: cors, json: { detail: "Document rendering failed for this draft." } })
      : route.fulfill({ headers: cors, json: { pdf_base64: pdf } });
    return route.fulfill({ headers: cors, json: { id, name: "Document QA", template_id: templates[0].id, template: templates[0], latest_version: { id: "version-one", content_snapshot: { profile: { bio: "Verified evidence." }, resume_meta: {} } } } });
  });
  await page.goto(`/resumes/${id}`);
  const download = page.getByRole("link", { name: "Download PDF", exact: true });
  await expect(download).toHaveAttribute("href", /^blob:/);
  fail = true;
  await page.getByRole("textbox", { name: "Summary", exact: true }).fill("A newly edited draft.");
  await expect(page.getByRole("alert").filter({ hasText: "Document rendering failed for this draft." })).toBeVisible();
  await expect(download).toHaveAttribute("aria-disabled", "true");
  await expect(download).not.toHaveAttribute("href");
  fail = false;
  await page.getByRole("button", { name: "Retry document previews", exact: true }).click();
  await expect(download).toHaveAttribute("href", /^blob:/);
  await expect(page.getByRole("alert").filter({ hasText: "Document rendering failed for this draft." })).toHaveCount(0);
});
