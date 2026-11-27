import { defineConfig } from "@playwright/test";
export default defineConfig({
  webServer: {
    command: "npm run dev -- --port 5174 --strictPort",
    env: { FINHEALTH_API_ORIGIN: "http://127.0.0.1:8765" },
    url: "http://127.0.0.1:5174",
    reuseExistingServer: false,
  },
  testDir: "e2e",
  timeout: 60_000,
  workers: 1,
  retries: 0,
  use: {
    baseURL: "http://127.0.0.1:8765",
    channel: "chrome",
    headless: true,
    trace: "retain-on-failure",
  },
  reporter: [
    ["list"],
    [
      "html",
      { outputFolder: "../audit-reports/frontend/playwright", open: "never" },
    ],
  ],
});
