import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  // The screenshot suite is run deliberately, not on every smoke run: it is
  // slow and it writes into artifacts/.
  testIgnore: process.env.SHOOT ? ["**/static/**"] : ["**/screens.spec.ts", "**/static/**"],
  timeout: 60_000,
  use: {
    baseURL: "http://127.0.0.1:3000",
    ...devices["Pixel 7"],
    // Use the system Chrome: the bundled chromium binary is not downloaded in
    // this environment, and installing it is a ~150 MB fetch per machine.
    channel: "chrome",
  },
  webServer: {
    command: "npx next dev -p 3000",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
