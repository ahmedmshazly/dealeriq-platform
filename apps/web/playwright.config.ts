import { defineConfig, devices } from "@playwright/test";

// QA-004: the golden-path E2E suite runs against an already-running `make dev` stack (real
// Postgres, real API, real Next.js) -- no webServer here, matching every prior phase's
// "verify against the real dev stack" convention rather than spinning up an ephemeral instance.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 1,
  reporter: "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
