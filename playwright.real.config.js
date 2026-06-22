const { defineConfig, devices } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./tests/e2e",
  testMatch: /real_backend\.spec\.js/,
  timeout: 60_000,
  expect: {
    timeout: 15_000,
  },
  outputDir: "output/playwright/real-test-results",
  reporter: [["list"], ["html", { outputFolder: "output/playwright/real-report", open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:8000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: {
    command: 'cmd /c "set \"STABLE_STEERING_GENERATION_BACKEND=diffusers\" && python scripts/run_dev.py"',
    url: "http://127.0.0.1:8000",
    reuseExistingServer: true,
    timeout: 180_000,
  },
  projects: [
    {
      name: "chrome",
      use: {
        ...devices["Desktop Chrome"],
        browserName: "chromium",
        channel: "chrome",
      },
    },
  ],
});
