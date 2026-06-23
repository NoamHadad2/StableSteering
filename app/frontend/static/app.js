const traceLog = document.getElementById("trace-log");
const pageStatus = document.getElementById("page-status");
const progressPanel = document.getElementById("progress-panel");
const progressBar = document.getElementById("progress-bar");
const progressValue = document.getElementById("progress-value");
const progressLabel = document.getElementById("progress-label");
const configYamlEditor = document.getElementById("config-yaml-editor");
const reloadConfigButton = document.getElementById("reload-config-button");

function appendTrace(message) {
  if (!traceLog) return;
  const item = document.createElement("li");
  item.textContent = `${new Date().toLocaleTimeString()} ${message}`;
  traceLog.prepend(item);
}

function setStatus(message, isError = false) {
  if (!pageStatus) return;
  pageStatus.hidden = !message;
  pageStatus.textContent = message || "";
  pageStatus.classList.toggle("error", Boolean(isError));
}

function setProgress(progress, label = "Working...") {
  if (!progressPanel || !progressBar || !progressValue || !progressLabel) return;
  const clamped = Math.max(0, Math.min(100, Number(progress || 0)));
  progressPanel.hidden = false;
  progressBar.style.width = `${clamped}%`;
  progressValue.textContent = `${clamped}%`;
  progressLabel.textContent = label;
}

function clearProgress() {
  if (!progressPanel || !progressBar || !progressValue || !progressLabel) return;
  progressPanel.hidden = true;
  progressBar.style.width = "0%";
  progressValue.textContent = "0%";
  progressLabel.textContent = "Working...";
}

function traceFrontend(event, details = {}) {
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
    const body = JSON.stringify(payload);
    if (navigator.sendBeacon) {
      const blob = new Blob([body], { type: "application/json" });
      navigator.sendBeacon("/frontend-events", blob);
      return;
    }
    fetch("/frontend-events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch((error) => console.warn("Failed to persist frontend trace event", error));
  } catch (error) {
    console.warn("Failed to persist frontend trace event", error);
  }
}

async function postJson(url, body) {
  traceFrontend("http.request.started", { url, body_keys: Object.keys(body || {}) });
  let response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (error) {
    const message = "Could not reach the server. Make sure the app is still running, then try again.";
    traceFrontend("http.request.failed", { url, detail: message, error_name: error?.name || "network_error" });
    throw new Error(message);
  }
  if (!response.ok) {
    const text = await response.text();
    let message = text || `Request failed: ${response.status}`;
    try {
      const parsed = JSON.parse(text);
      message = parsed.message || parsed.detail || message;
    } catch {
      message = text || message;
    }
    traceFrontend("http.request.failed", { url, status: response.status, detail: message });
    throw new Error(message);
  }
  const data = await response.json();
  traceFrontend("http.request.completed", { url, status: response.status });
  return data;
}

async function getJson(url) {
  const response = await fetch(url, { method: "GET" });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

async function pollJob(statusUrl, { onProgress } = {}) {
  for (;;) {
    const response = await fetch(statusUrl, { method: "GET" });
    if (!response.ok) {
      throw new Error(`Failed to poll job status: ${response.status}`);
    }
    const job = await response.json();
    if (onProgress) {
      onProgress(job);
    }
    if (job.state === "succeeded") {
      return job.result;
    }
    if (job.state === "failed") {
      throw new Error(job.error || "Asynchronous job failed.");
    }
    await new Promise((resolve) => window.setTimeout(resolve, 250));
  }
}

async function runNextRoundJob(sessionId, { queuedLabel, runningFallbackLabel } = {}) {
  const job = await postJson(`/sessions/${sessionId}/rounds/next/async`, {});
  setStatus(queuedLabel || "Queueing round generation...");
  setProgress(55, queuedLabel || "Queueing next round");
  await pollJob(job.status_url, {
    onProgress: (snapshot) => {
      setStatus(snapshot.status_message);
      setProgress(snapshot.progress, snapshot.status_message || runningFallbackLabel || "Generating next round");
    },
  });
}

function collectRatings() {
  return Array.from(document.querySelectorAll(".rating-input")).map((input) => ({
    candidateId: input.dataset.candidateId,
    rating: Number(input.value || 0),
  })).filter((entry) => entry.rating > 0);
}

function ratingCaption(value) {
  if (!value) {
    return "No rating selected yet";
  }
  if (value === 1) return "1 star selected";
  return `${value} stars selected`;
}

function applyStarRating(candidateId, value) {
  const numericValue = Number(value || 0);
  const hiddenInput = document.querySelector(`.rating-input[data-candidate-id="${candidateId}"]`);
  if (hiddenInput) {
    hiddenInput.value = String(numericValue);
  }
  const buttons = Array.from(document.querySelectorAll(`.star-button[data-candidate-id="${candidateId}"]`));
  buttons.forEach((button) => {
    const buttonValue = Number(button.dataset.ratingValue || 0);
    const active = numericValue > 0 && buttonValue <= numericValue;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
  const caption = document.querySelector(`.star-rating-caption[data-candidate-id="${candidateId}"]`);
  if (caption) {
    caption.textContent = ratingCaption(numericValue);
  }
}

function buildFeedbackPayload(feedbackMode) {
  if (feedbackMode === "pairwise") {
    const winner = document.querySelector(".pairwise-winner-input:checked")?.dataset.candidateId;
    const loser = document.querySelector(".pairwise-loser-input:checked")?.dataset.candidateId;
    if (!winner || !loser) {
      throw new Error("Pairwise feedback requires one explicit winner and one explicit loser.");
    }
    if (winner === loser) {
      throw new Error("Pairwise feedback requires different winner and loser candidates.");
    }
    return {
      feedback_type: "pairwise",
      payload: {
        winner_candidate_id: winner,
        loser_candidate_id: loser,
      },
    };
  }

  if (feedbackMode === "winner_only") {
    const winner = document.querySelector(".winner-only-input:checked")?.dataset.candidateId;
    if (!winner) {
      throw new Error("Winner-only feedback requires choosing one winner.");
    }
    return {
      feedback_type: "winner_only",
      payload: {
        winner_candidate_id: winner,
      },
    };
  }

  if (feedbackMode === "approve_reject") {
    const approvalInputs = Array.from(document.querySelectorAll(".approve-checkbox"));
    const approvals = Object.fromEntries(
      approvalInputs.map((input) => [input.dataset.candidateId, Boolean(input.checked)])
    );
    const approvedEntries = approvalInputs.filter((input) => input.checked);
    if (!approvedEntries.length) {
      throw new Error("Approve/reject feedback requires at least one approved candidate.");
    }
    const winner = document.querySelector(".approve-winner-input:checked")?.dataset.candidateId;
    if (!winner) {
      throw new Error("Approve/reject feedback requires choosing the preferred approved winner.");
    }
    if (!approvals[winner]) {
      throw new Error("The approve/reject winner must also be marked approved.");
    }
    return {
      feedback_type: "approve_reject",
      payload: {
        winner_candidate_id: winner,
        approvals,
      },
    };
  }

  if (feedbackMode === "top_k") {
    const ranks = Array.from(document.querySelectorAll(".rank-input"))
      .map((input) => ({
        candidateId: input.dataset.candidateId,
        rank: Number(input.value || 0),
      }))
      .filter((entry) => entry.rank > 0);
    if (ranks.length < 2) {
      throw new Error("Top-k feedback requires ranking at least two candidates.");
    }
    const uniqueRanks = new Set(ranks.map((entry) => entry.rank));
    if (uniqueRanks.size !== ranks.length) {
      throw new Error("Top-k feedback requires unique ranks.");
    }
    ranks.sort((left, right) => left.rank - right.rank || left.candidateId.localeCompare(right.candidateId));
    const approvals = Object.fromEntries(
      ranks.map((entry) => [entry.candidateId, entry.rank])
    );
    return {
      feedback_type: "top_k",
      payload: {
        ranking: ranks.map((entry) => entry.candidateId),
        ranks: approvals,
      },
    };
  }

  if (feedbackMode === "critique_rating") {
    const ratingEntries = collectRatings();
    if (!ratingEntries.length) {
      throw new Error("Critique rating feedback requires at least one explicit rating.");
    }
    const ratings = Object.fromEntries(ratingEntries.map((entry) => [entry.candidateId, entry.rating]));
    return {
      feedback_type: "critique_rating",
      payload: {
        ratings,
        critique_tags: collectCritiqueTags(),
      },
    };
  }

  const ratingEntries = collectRatings();
  if (!ratingEntries.length) {
    throw new Error("Scalar rating feedback requires at least one explicit rating.");
  }
  const sorted = [...ratingEntries].sort((left, right) => right.rating - left.rating || left.candidateId.localeCompare(right.candidateId));
  const ratings = Object.fromEntries(ratingEntries.map((entry) => [entry.candidateId, entry.rating]));

  return {
    feedback_type: "scalar_rating",
    payload: { ratings },
  };
}

function collectCritiqueTags() {
  const tags = {};
  Array.from(document.querySelectorAll(".critique-tag-pill[aria-pressed='true']")).forEach((pill) => {
    const candidateId = pill.dataset.candidateId;
    const tag = pill.dataset.tag;
    if (!candidateId || !tag) {
      return;
    }
    if (!tags[candidateId]) {
      tags[candidateId] = [];
    }
    tags[candidateId].push(tag);
  });
  return tags;
}

// ── Dimension ratings ────────────────────────────────────────────────────────
function getpriorities() {
  const priorities = {};
  document.querySelectorAll(".global-priority-list .dimension-row[data-dimension]").forEach((row) => {
    priorities[row.dataset.dimension] = parseInt(row.dataset.priority, 10);
  });
  return priorities;
}

function recalcWeightedScore(candidateId) {
  const priorities = getpriorities();
  const dims = Object.keys(priorities);
  if (dims.length === 0) return;
  const N = dims.length;
  let weightedSum = 0;
  let totalWeight = 0;
  dims.forEach((dim) => {
    const priorityIndex = priorities[dim] - 1;
    const weight = N - priorityIndex;
    const input = document.querySelector(`.dim-rating-input[data-candidate-id="${candidateId}"][data-dimension="${dim}"]`);
    const score = input ? parseInt(input.value, 10) || 0 : 0;
    weightedSum += weight * score;
    totalWeight += weight;
  });
  if (totalWeight === 0) return;
  const weighted = weightedSum / totalWeight;
  const rounded = Math.round(weighted);
  applyStarRating(candidateId, rounded);
  const hint = document.querySelector(`.weighted-score-hint[data-candidate-id="${candidateId}"]`);
  if (hint) hint.textContent = `Weighted score: ${weighted.toFixed(2)} / 5`;
}

document.querySelectorAll(".dim-star-button").forEach((btn) => {
  btn.addEventListener("click", () => {
    const candidateId = btn.dataset.candidateId;
    const dim = btn.dataset.dimension;
    const val = parseInt(btn.dataset.value, 10);
    const input = document.querySelector(`.dim-rating-input[data-candidate-id="${candidateId}"][data-dimension="${dim}"]`);
    if (input) input.value = String(val);
    document.querySelectorAll(`.dim-star-button[data-candidate-id="${candidateId}"][data-dimension="${dim}"]`).forEach((b) => {
      const active = parseInt(b.dataset.value, 10) <= val;
      b.classList.toggle("active", active);
      b.setAttribute("aria-pressed", active ? "true" : "false");
    });
    recalcWeightedScore(candidateId);
  });
});

function collectDimensionRatings() {
  const result = {};
  document.querySelectorAll(".image-card[data-candidate-id]").forEach((card) => {
    const cid = card.dataset.candidateId;
    const dims = {};
    card.querySelectorAll(".dim-rating-input").forEach((input) => {
      const v = parseInt(input.value, 10);
      if (v > 0) dims[input.dataset.dimension] = v;
    });
    if (Object.keys(dims).length > 0) result[cid] = dims;
  });
  return result;
}

function collectDimensionPriorities() {
  const priorities = getpriorities();
  if (Object.keys(priorities).length === 0) return {};
  const result = {};
  document.querySelectorAll(".image-card[data-candidate-id]").forEach((card) => {
    result[card.dataset.candidateId] = priorities;
  });
  return result;
}


// ── Drag-to-rank priority ─────────────────────────────────────────────────────
let _dragRow = null;
document.querySelectorAll(".global-priority-list").forEach((list) => {
  list.addEventListener("dragstart", (e) => {
    _dragRow = e.target.closest(".dimension-row");
    if (_dragRow) _dragRow.classList.add("dragging");
  });
  list.addEventListener("dragend", () => {
    if (_dragRow) _dragRow.classList.remove("dragging");
    _dragRow = null;
  });
  list.addEventListener("dragover", (e) => {
    e.preventDefault();
    if (!_dragRow) return;
    const target = e.target.closest(".dimension-row");
    if (target && target !== _dragRow) {
      const rect = target.getBoundingClientRect();
      const after = e.clientY > rect.top + rect.height / 2;
      list.insertBefore(_dragRow, after ? target.nextSibling : target);
      list.querySelectorAll(".dimension-row").forEach((row, i) => {
        row.dataset.priority = String(i + 1);
        const badge = row.querySelector(".priority-badge");
        if (badge) badge.textContent = String(i + 1);
      });
      document.querySelectorAll(".image-card[data-candidate-id]").forEach((card) => {
        recalcWeightedScore(card.dataset.candidateId);
      });
    }
  });
});

// ── Setup form — aesthetic calibration injection ──────────────────────────────
const setupForm = document.getElementById("setup-form");
const setupSubmitButton = document.getElementById("setup-submit-button");
if (setupForm) {
  traceFrontend("page.loaded", { view: "setup" });
  try {
    const aestheticRaw = localStorage.getItem("aesthetic_profile");
    if (aestheticRaw) {
      const styles = JSON.parse(aestheticRaw);
      if (Array.isArray(styles) && styles.length > 0) {
        const banner = document.getElementById("aesthetic-banner");
        const tags = document.getElementById("aesthetic-tags");
        if (banner && tags) { tags.textContent = styles.map((s) => s.replace(/_/g, " ")).join(", "); banner.style.display = ""; }
      }
    }
  } catch (_) {}
  reloadConfigButton?.addEventListener("click", async () => {
    reloadConfigButton.disabled = true;
    setStatus("Reloading default YAML template...");
    traceFrontend("setup.config.reload.clicked");
    try {
      const payload = await getJson("/setup/config-template");
      if (configYamlEditor) {
        configYamlEditor.value = payload.config_yaml || "";
      }
      setStatus("Default YAML template reloaded.");
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      reloadConfigButton.disabled = false;
    }
  });
  setupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    traceFrontend("setup.submit.clicked");
    if (setupSubmitButton) setupSubmitButton.disabled = true;
    if (reloadConfigButton) reloadConfigButton.disabled = true;
    setStatus("Creating experiment and session from YAML configuration...");
    try {
      const form = new FormData(setupForm);
      let prompt = form.get("prompt") || "";
      try {
        const aestheticRaw = localStorage.getItem("aesthetic_profile");
        if (aestheticRaw) {
          const styles = JSON.parse(aestheticRaw);
          if (Array.isArray(styles) && styles.length > 0) {
            const styleTag = styles.map((s) => s.replace(/_/g, " ")).join(", ");
            if (!prompt.toLowerCase().includes(styles[0].replace(/_/g, " ").toLowerCase())) {
              prompt = prompt.trimEnd().replace(/,\s*$/, "") + ", " + styleTag;
            }
          }
        }
      } catch (_) {}
      const payload = await postJson("/setup/session", {
        experiment_name: form.get("experiment_name"),
        description: form.get("description"),
        prompt,
        negative_prompt: form.get("negative_prompt"),
        config_yaml: form.get("config_yaml"),
      });
      traceFrontend("experiment.created", { experiment_id: payload.experiment.id });
      traceFrontend("session.created", { session_id: payload.session.id });
      setStatus("Session created. Opening the interactive view...");
      window.location.href = `/sessions/${payload.session.id}/style-calibration`;
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      if (setupSubmitButton) setupSubmitButton.disabled = false;
      if (reloadConfigButton) reloadConfigButton.disabled = false;
    }
  });
}

const nextRoundButton = document.getElementById("next-round-button");
if (nextRoundButton) {
  traceFrontend("page.loaded", { view: "session", session_id: nextRoundButton.dataset.sessionId });
  nextRoundButton.addEventListener("click", async () => {
    if (nextRoundButton.disabled) return;
    const sessionId = nextRoundButton.dataset.sessionId;
    traceFrontend("round.generate.clicked", { session_id: sessionId });
    nextRoundButton.disabled = true;
    setStatus("Queueing round generation...");
    setProgress(5, "Queueing next round");
    try {
      await runNextRoundJob(sessionId, {
        queuedLabel: "Queueing round generation...",
        runningFallbackLabel: "Generating next round",
      });
      setStatus("Round generated. Refreshing session view...");
      setProgress(100, "Round completed");
      window.location.reload();
    } catch (error) {
      setStatus(error.message, true);
      clearProgress();
      nextRoundButton.disabled = false;
    }
  });
}

Array.from(document.querySelectorAll(".star-button")).forEach((button) => {
  button.addEventListener("click", () => {
    if (button.disabled) return;
    const candidateId = button.dataset.candidateId;
    const value = Number(button.dataset.ratingValue || 0);
    applyStarRating(candidateId, value);
    traceFrontend("feedback.rating.selected", { candidate_id: candidateId, rating: value });
  });
});

Array.from(document.querySelectorAll(".critique-tag-pill")).forEach((pill) => {
  pill.addEventListener("click", () => {
    if (pill.disabled) return;
    const selected = pill.getAttribute("aria-pressed") === "true";
    pill.setAttribute("aria-pressed", selected ? "false" : "true");
    pill.classList.toggle("selected", !selected);
    traceFrontend("feedback.critique_tag.toggled", {
      candidate_id: pill.dataset.candidateId,
      tag: pill.dataset.tag,
      selected: !selected,
    });
  });
});

const submitFeedbackButton = document.getElementById("submit-feedback-button");
if (submitFeedbackButton) {
  traceFrontend("round.visible", { round_id: submitFeedbackButton.dataset.roundId });
  submitFeedbackButton.addEventListener("click", async () => {
    if (submitFeedbackButton.disabled) return;
    const feedbackMode = submitFeedbackButton.dataset.feedbackMode || "scalar_rating";
    const sessionId = submitFeedbackButton.dataset.sessionId;
    try {
      const request = buildFeedbackPayload(feedbackMode);
      request.dimension_ratings = collectDimensionRatings();
      request.dimension_priorities = collectDimensionPriorities();

      traceFrontend("feedback.submit.clicked", {
        round_id: submitFeedbackButton.dataset.roundId,
        feedback_mode: feedbackMode,
        interaction_mode: feedbackMode,
      });
      submitFeedbackButton.disabled = true;
      setStatus("Queueing feedback submission...");
      setProgress(5, "Queueing feedback");
      const job = await postJson(`/rounds/${submitFeedbackButton.dataset.roundId}/feedback/async`, {
        ...request,
      });
      await pollJob(job.status_url, {
        onProgress: (snapshot) => {
          setStatus(snapshot.status_message);
          setProgress(snapshot.progress, snapshot.status_message || "Applying feedback");
        },
      });
      traceFrontend("feedback.submit.completed", {
        round_id: submitFeedbackButton.dataset.roundId,
        session_id: sessionId,
      });
      setStatus("Feedback applied. Starting the next round...");
      setProgress(50, "Preparing next round");
      await runNextRoundJob(sessionId, {
        queuedLabel: "Queueing next round after feedback...",
        runningFallbackLabel: "Generating the next round",
      });
      setStatus("Next round ready. Refreshing session view...");
      setProgress(100, "Next round completed");
      window.location.reload();
    } catch (error) {
      setStatus(error.message, true);
      clearProgress();
      submitFeedbackButton.disabled = false;
    }
  });
}

// ── Style Calibration page ────────────────────────────────────────────────────
const generateCalButton = document.getElementById("generate-cal-button");
if (generateCalButton) {
  generateCalButton.addEventListener("click", async () => {
    const sessionId = generateCalButton.dataset.sessionId;
    generateCalButton.disabled = true;
    setStatus("Generating 15 style images — this takes a few minutes...");
    setProgress(5, "Starting calibration generation");
    try {
      const job = await postJson(`/sessions/${sessionId}/style-calibration/generate/async`, {});
      await pollJob(job.status_url, {
        onProgress: (snapshot) => {
          setStatus(snapshot.status_message);
          setProgress(snapshot.progress, snapshot.status_message || "Generating calibration images");
        },
      });
      setStatus("Images ready! Reloading...");
      setProgress(100, "Done");
      window.location.reload();
    } catch (error) {
      setStatus(error.message, true);
      clearProgress();
      generateCalButton.disabled = false;
    }
  });
}

const submitCalButton = document.getElementById("submit-cal-button");
if (submitCalButton) {
  const _selectedCal = new Set();

  document.querySelectorAll(".cal-card").forEach((card) => {
    card.addEventListener("click", () => {
      const cid = card.dataset.candidateId;
      if (_selectedCal.has(cid)) {
        _selectedCal.delete(cid);
        card.classList.remove("cal-selected");
      } else if (_selectedCal.size < 5) {
        _selectedCal.add(cid);
        card.classList.add("cal-selected");
      }
      const count = document.getElementById("selection-count");
      if (count) count.textContent = `${_selectedCal.size} / 5 selected`;
      submitCalButton.disabled = _selectedCal.size !== 5;
    });
  });

  submitCalButton.addEventListener("click", async () => {
    const sessionId = submitCalButton.dataset.sessionId;
    submitCalButton.disabled = true;
    setStatus("Saving your style preferences...");
    try {
      await postJson(`/sessions/${sessionId}/style-calibration/submit`, {
        selected_ids: Array.from(_selectedCal),
      });
      window.location.href = `/sessions/${sessionId}/view`;
    } catch (error) {
      setStatus(error.message, true);
      submitCalButton.disabled = false;
    }
  });
}

// ── Delete session (index page) ───────────────────────────────────────────────
document.querySelectorAll(".delete-session-button").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const sessionId = btn.dataset.sessionId;
    if (!confirm("Delete this session and all its rounds? This cannot be undone.")) return;
    btn.disabled = true;
    try {
      await fetch(`/sessions/${sessionId}`, { method: "DELETE" });
      btn.closest("tr")?.remove();
    } catch {
      btn.disabled = false;
    }
  });
});
