import { loadEnvConfig } from "@next/env";
import { defineConfig } from "@playwright/test";

// Specs that call the backend directly need API_URL and BACKEND_API_KEY from .env.local.
loadEnvConfig(process.cwd());

export default defineConfig({
  testDir: "./e2e",
  use: {
    baseURL: "http://localhost:3000",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
