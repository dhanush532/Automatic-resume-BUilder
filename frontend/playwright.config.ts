import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  use: { baseURL: "http://localhost:3000", trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } } },
    { name: "mobile", use: { ...devices["iPhone 13"], defaultBrowserType: "chromium", reducedMotion: "reduce" } },
  ],
  webServer: [
    { command: "uv run --project ../backend uvicorn app.main:app --app-dir ../backend --port 8000", url: "http://localhost:8000/api/v1/health", reuseExistingServer: !process.env.CI, timeout: 60000 },
    { command: "npm run dev", url: "http://localhost:3000", reuseExistingServer: !process.env.CI, timeout: 120000 },
  ],
});
