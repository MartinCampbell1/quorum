import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3740",
    viewport: { width: 1366, height: 768 },
    colorScheme: "light",
    locale: "en-US",
  },
  webServer: {
    command: "rm -f .next/build.lock && npm run build && rm -f .next/build.lock && npx next start -p 3740",
    url: "http://127.0.0.1:3740",
    reuseExistingServer: false,
    timeout: 240_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
