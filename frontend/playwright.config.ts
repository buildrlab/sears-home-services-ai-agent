import { defineConfig, devices } from "@playwright/test";

const port = Number(process.env.PW_PORT ?? 5173);
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${String(port)}`;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command: `corepack pnpm dev --port ${String(port)}`,
        url: baseURL,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
