import { defineConfig } from "@playwright/test";

// The tests run against a running ValiTrack (API and web app on one port) with the demo data loaded.
export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8000",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
  },
});
