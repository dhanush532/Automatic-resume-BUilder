import { expect, test, type Page } from "@playwright/test";

const cors = { "Access-Control-Allow-Origin": "http://localhost:3000", "Access-Control-Allow-Credentials": "true" };

async function capabilities(page: Page) {
  await page.route("**/api/v1/auth/capabilities", route => route.fulfill({ headers: cors, json: {
    email_delivery_configured: false,
    providers: [{ name: "google", configured: false }, { name: "github", configured: true }, { name: "linkedin", configured: false }],
  } }));
}

test("provider sign-in from login includes disclosed registration consent", async ({ page }) => {
  await capabilities(page);
  let payload: { mode: string; terms_accepted: boolean } | undefined;
  await page.route("**/api/v1/auth/oauth/github/start", async route => {
    payload = route.request().postDataJSON();
    await route.fulfill({ headers: cors, json: { authorization_url: "https://provider.example/authorize" } });
  });
  await page.route("https://provider.example/authorize", route => route.fulfill({ body: "Test-only provider page" }));
  await page.goto("/login");
  await expect(page.getByText("By continuing with a provider,", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Continue with GitHub", exact: true }).click();
  await page.waitForURL("https://provider.example/authorize");
  expect(payload).toEqual({ mode: "login", terms_accepted: true });
});

test("signup checks consent before leaving for the provider", async ({ page }) => {
  await capabilities(page);
  let requests = 0;
  await page.route("**/api/v1/auth/oauth/github/start", async route => {
    requests += 1;
    expect(route.request().postDataJSON().terms_accepted).toBe(true);
    await route.fulfill({ headers: cors, json: { authorization_url: "https://provider.example/authorize" } });
  });
  await page.route("https://provider.example/authorize", route => route.fulfill({ body: "Test-only provider page" }));
  await page.goto("/signup");
  await page.getByRole("button", { name: "Continue with GitHub", exact: true }).click();
  await expect(page.getByText("Accept the terms and privacy policy before continuing with a provider.", { exact: true })).toBeVisible();
  expect(requests).toBe(0);
  await page.locator('input[name="terms_accepted"]').check();
  await page.getByRole("button", { name: "Continue with GitHub", exact: true }).click();
  await page.waitForURL("https://provider.example/authorize");
  expect(requests).toBe(1);
});

test("OAuth errors explain recovery without hiding login options", async ({ page }) => {
  await capabilities(page);
  await page.goto("/login?oauth_error=authentication_failed&reason=session_expired");
  await expect(page.getByText("Your sign-in attempt expired", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue with GitHub", exact: true })).toBeEnabled();
  await page.goto("/login?oauth_error=authentication_failed&reason=verified_email_required");
  await expect(page.getByText("Your provider did not share a verified email address.", { exact: false })).toBeVisible();
});

test("account settings buttons actually submit profile and reauthentication forms", async ({ page }) => {
  await capabilities(page);
  let fullName = "Test Account";
  let profileRequests = 0;
  let reauthRequests = 0;
  await page.route("**/api/v1/auth/me", route => route.fulfill({ headers: cors, json: {
    id: "00000000-0000-4000-8000-000000000001", full_name: fullName, username: "testaccount", email: "test@example.com", email_verified: true, phone: null,
  } }));
  await page.route("**/api/v1/auth/oauth-identities", route => route.fulfill({ headers: cors, json: { password_available: true, providers: [] } }));
  await page.route("**/api/v1/auth/account", async route => {
    expect(route.request().method()).toBe("PATCH");
    fullName = route.request().postDataJSON().full_name;
    profileRequests += 1;
    await route.fulfill({ headers: cors, json: {} });
  });
  await page.route("**/api/v1/auth/reauthenticate", async route => {
    expect(route.request().postDataJSON()).toEqual({ password: "Test-only-password!123" });
    reauthRequests += 1;
    await route.fulfill({ status: 204, headers: cors });
  });
  await page.goto("/settings/account");
  await page.getByLabel("Full name", { exact: true }).fill("Updated Test Account");
  await page.getByRole("button", { name: "Save details", exact: true }).click();
  await expect(page.getByText("Account details updated.", { exact: false })).toBeVisible();
  expect(profileRequests).toBe(1);
  expect(fullName).toBe("Updated Test Account");
  await page.getByLabel("Current password for reauthentication", { exact: true }).fill("Test-only-password!123");
  await page.getByRole("button", { name: "Confirm password", exact: true }).click();
  await expect(page.getByText("Identity confirmed for the next ten minutes.", { exact: true })).toBeVisible();
  expect(reauthRequests).toBe(1);
});
