const { test, expect } = require("@playwright/test");

test.describe("StableSteering real backend smoke", () => {
  test.skip(!process.env.STABLE_STEERING_E2E_REAL, "Set STABLE_STEERING_E2E_REAL=true to run the real-backend browser smoke test.");

  test("diagnostics page reports the real diffusers backend", async ({ page }) => {
    await page.goto("/diagnostics/view");
    await expect(page.getByRole("heading", { name: "Runtime backend status" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "diffusers" }).first()).toBeVisible();
    await expect(page.getByText("CUDA available")).toBeVisible();
  });
});
