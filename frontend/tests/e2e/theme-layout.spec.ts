import { expect, test } from "@playwright/test";

test("workspace content follows the header without an empty viewport", async ({ page }, info) => {
  for (const path of ["/resumes", "/passport", "/jobs", "/saved-jobs", "/resumes/new", "/settings/account"]) {
    await page.goto(path);
    const header = page.locator(".site-header");
    const main = page.locator("#main-content > main");
    await expect(header).toBeVisible();
    await expect(main).toBeVisible();
    const headerBox = await header.boundingBox();
    const mainBox = await main.boundingBox();
    expect(mainBox!.y - (headerBox!.y + headerBox!.height), path).toBeLessThanOrEqual(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), path).toBe(true);
    if (path === "/jobs") {
      await expect(page.getByRole("button", { name: "Search", exact: true })).toHaveCSS("background-color", "rgb(23, 60, 50)");
      await page.screenshot({ path: `test-results/jobs-theme-${info.project.name}.png`, fullPage: true });
    }
    if (path === "/passport") await expect(page.getByText("Authentication is required.", { exact: true })).toBeVisible();
  }
});

test("auth pages share the homepage palette in light and dark device modes", async ({ page }, info) => {
  await page.route("**/api/v1/auth/capabilities", async route => {
    await route.fulfill({
      json: { email_delivery_configured: true, providers: [{ name: "google", configured: false }, { name: "github", configured: true }, { name: "linkedin", configured: false }] },
      headers: { "Access-Control-Allow-Origin": "http://localhost:3000", "Access-Control-Allow-Credentials": "true" },
    });
  });
  for (const colorScheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme });
    for (const path of ["/login", "/signup", "/forgot-password", "/reset-password"]) {
      await page.goto(path);
      await expect(page.locator(".auth-layout")).toHaveCSS("background-color", "rgb(248, 249, 245)");
      const input = page.locator(".auth-form-content input:not([type=checkbox])").first();
      await expect(input).toBeVisible();
      await expect(input).toHaveCSS("background-color", "rgb(255, 255, 255)");
      await expect(input).toHaveCSS("color", "rgb(28, 48, 43)");
      await input.focus();
      await expect(input).toHaveCSS("border-color", "rgb(23, 60, 50)");
      if (["/login", "/signup"].includes(path)) {
        await expect(page.getByRole("button", { name: "Continue with Google", exact: true })).toBeVisible();
        await expect(page.getByRole("button", { name: "Continue with GitHub", exact: true })).toBeEnabled();
        await expect(page.getByRole("button", { name: "Continue with LinkedIn", exact: true })).toBeVisible();
        await expect(page.getByRole("button", { name: "Continue with Google", exact: true })).toBeDisabled();
        await expect(page.getByRole("button", { name: "Continue with LinkedIn", exact: true })).toBeDisabled();
        await page.screenshot({ path: `test-results/${path.slice(1)}-${colorScheme}-${info.project.name}.png`, fullPage: true });
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${path} ${colorScheme}`).toBe(true);
    }
  }
});
