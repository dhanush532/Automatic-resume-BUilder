import { expect, test } from "@playwright/test";

const resume = `Alex Morgan
alex@example.com | https://github.com/alex
Summary
Software engineer focused on reliable, accessible applications.
Experience
Built Python APIs for 200 users and reduced response time by 30%.
Developed React dashboards for a support team of 15 people.
Led a team of 4 engineers to deliver a customer portal.
Education
BSc Computer Science, Example University
Skills
Python, React, SQL, Docker
Projects
Created an accessible job tracking workspace.`;

test("landing navigation, responsive layout, and reduced-motion content", async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Good experience.");
  await expect(page.getByRole("link", { name: "Give my resume a check" })).toBeVisible();
  await expect(page.locator(".hero-copy h1")).toHaveCSS("opacity", "1");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  if (info.project.name === "mobile") {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await expect(page.getByRole("navigation", { name: "Mobile navigation" })).toBeVisible();
    await page.getByRole("button", { name: "Close navigation" }).click();
  }
  for (const section of await page.locator(".scroll-reveal").all()) { await section.scrollIntoViewIfNeeded(); await expect(section).toHaveCSS("opacity", "1"); }
  await page.locator(".site-header").scrollIntoViewIfNeeded();
  await page.screenshot({ path: `test-results/landing-${info.project.name}.png`, fullPage: true });
  await page.getByRole("link", { name: "Give my resume a check" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("A stronger resume");
  expect(errors).toEqual([]);
});

test("real upload, evaluation, job comparison, export and sign-in handoff", async ({ page }, info) => {
  await page.goto("/review");
  await page.getByLabel("Upload your resume").setInputFiles({ name: "alex-resume.txt", mimeType: "text/plain", buffer: Buffer.from(resume) });
  await expect(page.locator("#resume-text")).toHaveValue(resume);
  await page.getByText("Have a role in mind?").click();
  await page.getByLabel("Job description", { exact: true }).fill("We need Python and React experience. Kubernetes is required.");
  await page.getByRole("button", { name: "Show me the improvements" }).click();
  await expect(page.getByRole("heading", { name: "Your next improvements" })).toBeVisible();
  await expect(page.getByText("Kubernetes", { exact: true })).toBeVisible();
  await expect(page.getByText("Not detected — include only if true")).toBeVisible();
  for (const panel of await page.locator(".result-reveal").all()) { await expect(panel).toHaveCSS("opacity", "1"); }
  await page.locator(".site-header").scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: `test-results/review-${info.project.name}.png`, fullPage: true });
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download PDF" }).click();
  expect((await download).suggestedFilename()).toBe("resume.pdf");
  await page.getByRole("button", { name: "Save to my resumes" }).click();
  await expect(page.getByText("Sign in to save your resume.")).toBeVisible();
  await page.locator(".save-panel").getByRole("link", { name: "Sign in", exact: true }).click();
  await page.goto("/review");
  await expect(page.locator("#resume-text")).toHaveValue(resume);
  await expect(page.getByText("Your unsaved text was restored", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Start over" }).click();
  await expect(page.locator("#resume-text")).toHaveValue("");
});

test("invalid uploads give actionable feedback", async ({ page }) => {
  await page.goto("/review");
  await page.getByLabel("Upload your resume").setInputFiles({ name: "fake.pdf", mimeType: "application/pdf", buffer: Buffer.from("invalid pdf content") });
  await expect(page.locator(".workspace-alert")).toContainText("not a valid PDF");
  await expect(page.getByRole("button", { name: "Show me the improvements" })).toBeDisabled();
});
