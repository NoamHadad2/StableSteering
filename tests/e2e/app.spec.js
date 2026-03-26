const { test, expect } = require("@playwright/test");

async function createSessionViaBrowser(page, options = {}) {
  await page.goto("/setup");
  await expect(page.getByRole("heading", { name: "Start from your text prompt" })).toBeVisible();

  await page.locator('[name="experiment_name"]').fill(options.experimentName || "Playwright experiment");
  await page.locator('[name="description"]').fill(options.description || "Browser click and see flow");
  await page.locator('[name="prompt"]').fill(options.prompt || "A bright orange concept car in a glass studio");
  await page.locator('[name="negative_prompt"]').fill(options.negativePrompt || "blurry");
  await page.locator('[name="config_yaml"]').fill(
    options.configYaml || `sampler: ${options.sampler || "exploit_orthogonal"}
updater: ${options.updater || "winner_average"}
feedback_mode: ${options.feedbackMode || "scalar_rating"}
seed_policy: fixed-per-round
steering_mode: low_dimensional
candidate_count: ${options.candidateCount || 4}
image_size: 512x512
trust_radius: 0.35
anchor_strength: 0.15
model_name: runwayml/stable-diffusion-v1-5`
  );
  await page.getByRole("button", { name: "Create and open session" }).click();

  await expect(page).toHaveURL(/\/sessions\/.+\/view$/);
  const match = page.url().match(/\/sessions\/([^/]+)\/view$/);
  return match?.[1];
}

test.describe("StableSteering browser flow", () => {
  test("user can create a session, click through a round, and see replay content", async ({ page }) => {
    await createSessionViaBrowser(page);
    await expect(page.getByRole("button", { name: "Generate next round" })).toBeVisible();
    await expect(page.getByText("Current steering vector:")).toBeVisible();

    await page.getByRole("button", { name: "Generate next round" }).click();

    await expect(page.getByRole("heading", { name: /Round 1/ })).toBeVisible();
    await expect(page.locator(".image-card")).toHaveCount(4);
    await expect(page.locator(".image-card img").first()).toBeVisible();

    const ratings = page.locator(".rating-input");
    await ratings.nth(0).fill("2");
    await ratings.nth(1).fill("5");
    await ratings.nth(2).fill("4");
    await ratings.nth(3).fill("1");
    await page.getByRole("button", { name: "Submit feedback" }).click();

    await expect(page.getByText("Status:")).toBeVisible();
    await expect(page.getByRole("link", { name: "Open replay" })).toBeVisible();

    await page.getByRole("link", { name: "Open replay" }).click();

    await expect(page).toHaveURL(/\/sessions\/.+\/replay-view$/);
    await expect(page.getByText("Replay", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Round 1/ })).toBeVisible();
    await expect(page.locator(".compact-card")).toHaveCount(4);
  });

  test("replay export API returns the round and feedback history for a browser-created session", async ({ page, request }) => {
    const sessionId = await createSessionViaBrowser(page, {
      experimentName: "Replay API smoke",
      description: "Replay export API smoke test",
      prompt: "A polished red roadster in a white cyclorama",
    });

    await page.getByRole("button", { name: "Generate next round" }).click();
    await expect(page.getByRole("heading", { name: /Round 1/ })).toBeVisible();

    const ratings = page.locator(".rating-input");
    await ratings.nth(0).fill("1");
    await ratings.nth(1).fill("4");
    await ratings.nth(2).fill("5");
    await ratings.nth(3).fill("2");
    await page.getByRole("button", { name: "Submit feedback" }).click();
    await expect(page.getByText("Status:")).toBeVisible();
    await expect(page.getByRole("link", { name: "Open replay" })).toBeVisible();

    const replayResponse = await request.get(`/sessions/${sessionId}/replay`);
    expect(replayResponse.ok()).toBeTruthy();

    const replay = await replayResponse.json();
    expect(replay.session.id).toBe(sessionId);
    expect(replay.rounds).toHaveLength(1);
    expect(replay.rounds[0].candidates).toHaveLength(4);
    expect(replay.rounds[0].feedback_events).toHaveLength(1);
    expect(replay.rounds[0].update_summary.winner_candidate_id).toBeTruthy();
  });

  test("home page shows experiments after a browser-created flow", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Interactive prompt-embedding steering research prototype" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Runtime diagnostics" })).toBeVisible();
    await page.getByRole("link", { name: "Start a session" }).click();
    await expect(page).toHaveURL("/setup");
    await expect(page.getByRole("button", { name: "Create and open session" })).toBeVisible();
  });

  test("diagnostics page shows resolved backend and CUDA status", async ({ page }) => {
    await page.goto("/diagnostics/view");
    await expect(page.getByRole("heading", { name: "Runtime backend status" })).toBeVisible();
    await expect(page.getByText("Resolved backend")).toBeVisible();
    await expect(page.getByText("CUDA available")).toBeVisible();
    await expect(page.getByRole("cell", { name: "mock" }).first()).toBeVisible();
  });
});
