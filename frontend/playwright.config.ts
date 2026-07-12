import { defineConfig, devices } from "@playwright/test";

// E2E stack: real FastAPI (port 8100, real PostgreSQL) + Vite dev server
// (port 5273) proxying /api to it. AI-dependent specs self-skip without
// DEEPSEEK_API_KEY, mirroring backend/tests/test_real_provider_t3.py.
const BACKEND_PORT = 8100;
const FRONTEND_PORT = 5273;

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${FRONTEND_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "sh ../scripts/e2e-backend.sh",
      url: `http://127.0.0.1:${BACKEND_PORT}/api/v1/healthz`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      env: { ...process.env, E2E_BACKEND_PORT: String(BACKEND_PORT) },
    },
    {
      command: `npm run dev -- --port ${FRONTEND_PORT} --strictPort`,
      url: `http://127.0.0.1:${FRONTEND_PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      env: { ...process.env, VITE_API_PROXY_TARGET: `http://127.0.0.1:${BACKEND_PORT}` },
    },
  ],
});
