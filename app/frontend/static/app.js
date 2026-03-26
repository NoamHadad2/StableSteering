const traceLog = document.getElementById("trace-log");

function appendTrace(message) {
  if (!traceLog) return;
  const item = document.createElement("li");
  item.textContent = `${new Date().toLocaleTimeString()} ${message}`;
  traceLog.prepend(item);
}

async function traceFrontend(event, details = {}) {
  const payload = {
    event,
    page: window.location.pathname,
    session_id: document.getElementById("next-round-button")?.dataset.sessionId || null,
    round_id: document.getElementById("submit-feedback-button")?.dataset.roundId || null,
    details,
  };
  appendTrace(`${event} ${JSON.stringify(details)}`);
  console.info("[StableSteering trace]", payload);
  try {
    await fetch("/frontend-events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    console.warn("Failed to persist frontend trace event", error);
  }
}

async function postJson(url, body) {
  await traceFrontend("http.request.started", { url, body_keys: Object.keys(body || {}) });
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    await traceFrontend("http.request.failed", { url, status: response.status, detail: text });
    throw new Error(text || `Request failed: ${response.status}`);
  }
  const data = await response.json();
  await traceFrontend("http.request.completed", { url, status: response.status });
  return data;
}

function collectRatings() {
  return Array.from(document.querySelectorAll(".rating-input")).map((input) => ({
    candidateId: input.dataset.candidateId,
    rating: Number(input.value || 0),
  }));
}

function buildFeedbackPayload(feedbackMode, ratingEntries) {
  if (!ratingEntries.length) {
    throw new Error("No candidate ratings were provided.");
  }

  const sorted = [...ratingEntries].sort((left, right) => right.rating - left.rating || left.candidateId.localeCompare(right.candidateId));
  const ratings = Object.fromEntries(ratingEntries.map((entry) => [entry.candidateId, entry.rating]));

  if (feedbackMode === "pairwise") {
    if (sorted.length < 2) {
      throw new Error("Pairwise feedback requires at least two rated candidates.");
    }
    return {
      feedback_type: "pairwise",
      payload: {
        winner_candidate_id: sorted[0].candidateId,
        loser_candidate_id: sorted[sorted.length - 1].candidateId,
      },
    };
  }

  if (feedbackMode === "top_k") {
    return {
      feedback_type: "top_k",
      payload: {
        ranking: sorted.map((entry) => entry.candidateId),
      },
    };
  }

  return {
    feedback_type: "scalar_rating",
    payload: { ratings },
  };
}

const setupForm = document.getElementById("setup-form");
if (setupForm) {
  traceFrontend("page.loaded", { view: "setup" });
  setupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await traceFrontend("setup.submit.clicked");
    const form = new FormData(setupForm);
    const experiment = await postJson("/experiments", {
      name: form.get("experiment_name"),
      description: form.get("description"),
      config: {
        sampler: form.get("sampler"),
        updater: form.get("updater"),
        feedback_mode: form.get("feedback_mode"),
        candidate_count: Number(form.get("candidate_count")),
      },
    });
    await traceFrontend("experiment.created", { experiment_id: experiment.id });
    const session = await postJson("/sessions", {
      experiment_id: experiment.id,
      prompt: form.get("prompt"),
      negative_prompt: form.get("negative_prompt"),
    });
    await traceFrontend("session.created", { session_id: session.id });
    window.location.href = `/sessions/${session.id}/view`;
  });
}

const nextRoundButton = document.getElementById("next-round-button");
if (nextRoundButton) {
  traceFrontend("page.loaded", { view: "session", session_id: nextRoundButton.dataset.sessionId });
  nextRoundButton.addEventListener("click", async () => {
    const sessionId = nextRoundButton.dataset.sessionId;
    await traceFrontend("round.generate.clicked", { session_id: sessionId });
    await postJson(`/sessions/${sessionId}/rounds/next`, {});
    window.location.reload();
  });
}

const submitFeedbackButton = document.getElementById("submit-feedback-button");
if (submitFeedbackButton) {
  traceFrontend("round.visible", { round_id: submitFeedbackButton.dataset.roundId });
  submitFeedbackButton.addEventListener("click", async () => {
    const feedbackMode = submitFeedbackButton.dataset.feedbackMode || "scalar_rating";
    const ratingEntries = collectRatings();
    const request = buildFeedbackPayload(feedbackMode, ratingEntries);
    await traceFrontend("feedback.submit.clicked", {
      round_id: submitFeedbackButton.dataset.roundId,
      feedback_mode: feedbackMode,
      rated_candidates: ratingEntries.length,
    });
    await postJson(`/rounds/${submitFeedbackButton.dataset.roundId}/feedback`, {
      ...request,
    });
    window.location.reload();
  });
}
