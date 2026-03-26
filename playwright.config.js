const { defineConfig, devices } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: {
    timeout: 10_000,
  },
  outputDir: "output/playwright/test-results",
  reporter: [["list"], ["html", { outputFolder: "output/playwright/report", open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:8000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: {
    command: 'cmd /c "set \"STABLE_STEERING_GENERATION_BACKEND=mock\" && set \"STABLE_STEERING_ENFORCE_GPU_RUNTIME=false\" && set \"STABLE_STEERING_ALLOW_TEST_MOCK_BACKEND=true\" && python scripts/run_dev.py"',
    url: "http://127.0.0.1:8000",
    reuseExistingServer: true,
    timeout: 120_000,
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
