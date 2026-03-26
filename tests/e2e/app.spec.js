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
candidate_count: ${options.candidateCount || 5}
image_size: 512x512
trust_radius: 0.35
anchor_strength: 0.35
guidance_scale: 7.5
num_inference_steps: 15
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
    await expect(page.getByRole("button", { name: /Generate .* round/ })).toBeVisible();
    await expect(page.getByText(/Steering vector/)).toBeVisible();

    await page.getByRole("button", { name: /Generate .* round/ }).click();

    await expect(page.locator("#round-container").getByText("Round 1")).toBeVisible();
    await expect(page.locator(".image-card")).toHaveCount(5);
    await expect(page.locator(".image-card img").first()).toBeVisible();

    await page.locator('.star-button[data-candidate-id]').nth(1 * 5 + 4).click();
    await page.locator('.star-button[data-candidate-id]').nth(2 * 5 + 3).click();
    await page.locator('.star-button[data-candidate-id]').nth(3 * 5 + 2).click();
    await page.locator('.star-button[data-candidate-id]').nth(4 * 5 + 0).click();
    await page.getByRole("button", { name: "Submit feedback" }).click();

    await expect(page.getByRole("button", { name: /Generate .* round/ })).toBeVisible();
    await expect(page.getByRole("link", { name: "Open replay" })).toBeVisible();
    await page.getByRole("button", { name: /Generate .* round/ }).click();
    await expect(page.locator("details.round-block")).toHaveCount(2);
    await expect(page.locator("#round-container").getByText("Round 1")).toBeVisible();
    await expect(page.locator("#round-container").getByText("Round 2")).toBeVisible();
    await expect(page.locator("details.round-block[open]")).toHaveCount(1);
    await expect(page.locator("details.round-block[open]").getByText("Round 2")).toBeVisible();

    await page.getByRole("link", { name: "Open replay" }).click();

    await expect(page).toHaveURL(/\/sessions\/.+\/replay-view$/);
    await expect(page.getByText("Replay", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Round 1/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Round 2/ })).toBeVisible();
    await expect(page.locator(".compact-card")).toHaveCount(10);
  });

  test("replay export API returns the round and feedback history for a browser-created session", async ({ page, request }) => {
    const sessionId = await createSessionViaBrowser(page, {
      experimentName: "Replay API smoke",
      description: "Replay export API smoke test",
      prompt: "A polished red roadster in a white cyclorama",
    });

    await page.getByRole("button", { name: /Generate .* round/ }).click();
    await expect(page.locator("#round-container").getByText("Round 1")).toBeVisible();

    await page.locator('.star-button[data-candidate-id]').nth(1 * 5 + 3).click();
    await page.locator('.star-button[data-candidate-id]').nth(2 * 5 + 4).click();
    await page.locator('.star-button[data-candidate-id]').nth(3 * 5 + 2).click();
    await page.locator('.star-button[data-candidate-id]').nth(4 * 5 + 1).click();
    await page.getByRole("button", { name: "Submit feedback" }).click();
    await expect(page.getByRole("button", { name: /Generate .* round/ })).toBeVisible();
    await expect(page.getByRole("link", { name: "Open replay" })).toBeVisible();

    const replayResponse = await request.get(`/sessions/${sessionId}/replay`);
    expect(replayResponse.ok()).toBeTruthy();

    const replay = await replayResponse.json();
    expect(replay.session.id).toBe(sessionId);
    expect(replay.rounds).toHaveLength(1);
    expect(replay.rounds[0].candidates).toHaveLength(5);
    expect(replay.rounds[0].feedback_events).toHaveLength(1);
    expect(replay.rounds[0].update_summary.winner_candidate_id).toBeTruthy();
  });

  test("winner-only mode uses explicit winner selection controls", async ({ page }) => {
    await createSessionViaBrowser(page, {
      experimentName: "Winner only flow",
      description: "Winner-only control test",
      feedbackMode: "winner_only",
    });

    await page.getByRole("button", { name: /Generate .* round/ }).click();
    await expect(page.locator("#round-container").getByText("Round 1")).toBeVisible();
    await expect(page.locator(".winner-only-input")).toHaveCount(5);
    await page.locator(".winner-only-input").nth(2).check();
    await page.getByRole("button", { name: "Submit feedback" }).click();
    await expect(page.getByRole("button", { name: /Generate .* round/ })).toBeVisible();
  });

  test("setup page can reload the default YAML template", async ({ page }) => {
    await page.goto("/setup");
    const editor = page.locator('[name="config_yaml"]');
    await editor.fill("candidate_count: 2");
    await page.getByRole("button", { name: "Reload default YAML" }).click();
    await expect(editor).toContainText("candidate_count: 5");
    await expect(editor).toContainText("sampler: random_local");
  });

  test("home page shows experiments after a browser-created flow", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Interactive prompt-embedding steering research prototype" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Runtime diagnostics" })).toBeVisible();
    await page.getByRole("link", { name: "Start a session" }).click();
    await expect(page).toHaveURL("/setup");
    await expect(page.getByRole("button", { name: "Create and open session" })).toBeVisible();
  });

  test("home page lets the user resume a recent session", async ({ page }) => {
    const sessionId = await createSessionViaBrowser(page, {
      experimentName: "Resume session flow",
      description: "Resume session test",
      prompt: "A minimal ceramic lamp on a pedestal",
    });

    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Resume sessions" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Resume session" }).first()).toBeVisible();
    await page.getByRole("link", { name: "Resume session" }).first().click();
    await expect(page).toHaveURL(new RegExp(`/sessions/${sessionId}/view$`));
  });

  test("diagnostics page shows resolved backend and CUDA status", async ({ page }) => {
    await page.goto("/diagnostics/view");
    await expect(page.getByRole("heading", { name: "Runtime backend status" })).toBeVisible();
    await expect(page.getByText("Resolved backend")).toBeVisible();
    await expect(page.getByText("CUDA available")).toBeVisible();
    await expect(page.getByRole("cell", { name: "mock" }).first()).toBeVisible();
  });
});
