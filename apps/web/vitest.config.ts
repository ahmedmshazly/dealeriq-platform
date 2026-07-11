import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    globals: true,
    // e2e/ holds Playwright specs (QA-004) -- vitest's default include pattern would otherwise
    // also pick up e2e/*.spec.ts and fail to collect them (they use @playwright/test's `test`,
    // not vitest's global). Otherwise the same defaults vitest itself ships.
    exclude: [
      "**/node_modules/**",
      "**/dist/**",
      "**/.next/**",
      "**/.{idea,git,cache,output,temp}/**",
      "**/e2e/**",
    ],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
