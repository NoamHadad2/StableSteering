# Year 3 Projects — Student Contribution Report

**Student:** Noam Hadad  
**Date:** June 2026  

---

## Semester A — WeatherProof-KITTI: Synthetic Adverse-Weather Data for Robust Object Detection

### Executive Summary

Modern object detectors trained exclusively on clear-weather driving data suffer catastrophic performance failure when deployed in real-world adverse conditions. This project builds an end-to-end pipeline that generates realistic synthetic rain, snow, fog, and night variants of the KITTI autonomous driving dataset, then trains a YOLOv8s model on the mixed data to produce a weather-robust detector.

### At a Glance

```
Before (sunny-only training)       After (mixed training)
──────────────────────────────────────────────────────────────────
mAP@50 on sunny test:   0.801      mAP@50 on sunny test:   0.815  (+1.7%)
mAP@50 on harsh test:   0.222      mAP@50 on harsh test:   0.718  (+223%)
Performance drop:       -72.3%     Performance drop:       -11.9%
```

### Problem

Object detectors trained only on sunny KITTI data drop from **0.801 → 0.222 mAP@50** when tested on synthetic harsh-weather images — a 72.3% collapse. Re-collecting and re-annotating real adverse-weather driving data is prohibitively expensive.

### Solution: Dual-Signal Guided Inpainting

The pipeline replaces each image's background with a weather-appropriate synthetic scene while keeping all objects (cars, pedestrians, cyclists) untouched and annotations valid — no re-labeling required.

**Pipeline steps:**

| Step | Tool | Purpose |
|---|---|---|
| Depth estimation | Depth Anything V2 | Understand spatial layout of the scene |
| Foreground isolation | Segment Anything (SAM) | Extract objects using bounding-box prompts |
| Background synthesis | SDXL + Dual ControlNet | Generate weather-conditioned background guided by depth + Canny edges |
| Post-processing | Color transfer | Match lighting between generated background and original scene |
| Label update | Automatic YOLO-format recalculation | Bounding boxes stay valid after resize/pad |

**Why dual ControlNet?**  
Using depth maps alone loses fine boundaries. Canny edges alone lose spatial structure. Both together preserve object boundaries and scene geometry so detections remain accurate in the composite image.

**Weather conditions generated:**
- **Rain** — wet reflections, reduced visibility
- **Snow** — road accumulation, white haze  
- **Fog** — diffuse visibility reduction
- **Night** — artificial lighting, dark conditions

### Dataset

| Split | Images |
|---|---|
| Original KITTI (sunny) | 5,236 |
| Synthetic harsh-weather | 5,236 |
| Total mixed training set | 10,472 |

### Results

**Cross-domain mAP@50:**

| Model | Sunny test | Harsh test | Drop |
|---|---|---|---|
| Sunny-only baseline | 0.801 | 0.222 | −72.3% |
| Mixed-domain (ours) | **0.815** | **0.718** | **−11.9%** |

**Per-class improvement on harsh weather:**

| Class | Baseline | Mixed | Gain |
|---|---|---|---|
| Car | 0.412 | 0.682 | +66% |
| Pedestrian | 0.178 | 0.643 | +261% |
| Cyclist | 0.201 | 0.559 | +178% |

**Finding:** Training on mixed data not only fixes the weather robustness gap — it also slightly improves sunny-condition performance (0.815 vs 0.801), suggesting the synthetic variants act as a regularizer.

### Notebooks

| Notebook | Purpose |
|---|---|
| `01_KITTI_EDA_DataPrep.ipynb` | Download KITTI, analyze class distribution and bounding box statistics |
| `02_Synthetic_Data_Generation.ipynb` | Full generation pipeline: depth → SAM → SDXL inpainting → color transfer |
| `03_YOLOv8s_Training_Evaluation.ipynb` | Train sunny-only and mixed models, cross-domain evaluation |

---

## Semester B — StableSteering: Human-Preference Features

**Project:** StableSteering — Iterative Preference-Guided Image Generation  
**Base platform:** Supervisor's StableSteering research prototype  
**Tomer Atia's additions (semester B baseline):** Convergence Detection, Critique-Assisted Feedback

All features below are **strictly additive** — no existing algorithm, updater, sampler, or feedback mode was modified.

### At a Glance

```
Before (Tomer's semester B)           After (our additions)
──────────────────────────────────────────────────────────────────────
Cold-start: random z initialization   Calibrated start from user's style picks
No per-dimension feedback             Per-dimension star ratings + priority order
No user preference model              Live Taste Profile with signal strength
Sessions not deletable                One-click delete from dashboard
```

---

### Feature 1 — Style Calibration Round

#### Motivation

The steering loop starts from a zero vector `z = [0, 0, …, 0]`, meaning the first round is purely exploratory with no knowledge of what the user wants. This wastes 1–2 rounds on directions the user would immediately reject.

#### How It Works

Immediately after session creation (before round 1), the user lands on a calibration page. The system generates **15 images** using `spherical_cover` sampler at maximum trust radius (`trust_radius = 1.0`) — the widest possible style spread across the embedding space. The user picks their **5 favorites**. The system averages the `z` vectors of the 5 chosen images and sets that as the session's `current_z`, giving round 1 a meaningful starting direction.

```
Session created
      ↓
/sessions/{id}/style-calibration  (15 images, spherical spread)
      ↓
User selects 5 favorites
      ↓
avg(z₁, z₂, z₃, z₄, z₅) → session.current_z
      ↓
Round 1 starts from informed position
```

#### What Was Built

| File | Change |
|---|---|
| `app/engine/orchestrator.py` | `generate_calibration_round()` — 15-candidate generation; `submit_calibration()` — z averaging |
| `app/storage/repository.py` | `delete_session()` (also used by Feature 4) |
| `app/frontend/templates/style_calibration.html` | New page: image grid with click-to-select + progress tracking |
| `app/main.py` | 3 new endpoints: `GET /style-calibration`, `POST /generate/async`, `POST /submit` |
| `app/frontend/static/app.js` | `generate-cal-button` handler (async job + polling), `submit-cal-button` handler (selection of exactly 5) |
| `app/frontend/static/styles.css` | `.cal-card`, `.cal-selected`, `.cal-select-overlay` |

The calibration round is stored as `round_index = 0` and is filtered out of the regular session view — it does not count toward convergence or round history.

---

### Feature 2 — Dimension Rating

#### Motivation

The existing `scalar_rating` mode asks for a single overall score per image. This gives the model no information about **which aspects** of the image were good or bad. Two images can both score 3 stars for completely different reasons.

#### How It Works

For each candidate, below the overall star rating, a per-dimension row appears for every dimension extracted from the prompt (e.g., `lighting`, `color`, `mood`, `cinematic`). Each row has its own 1–5 star buttons. Ratings are stored in `FeedbackEvent.dimension_ratings` as `{ candidate_id: { dimension: score } }` and passed to the backend with every feedback submission.

#### Prompt Dimension Extraction

```python
def extract_prompt_dimensions(prompt: str) -> list[str]:
    words = re.findall(r"[a-zA-Z]+", prompt.lower())
    content_dims = [w for w in words if w not in _STOP_WORDS and len(w) > 3][:4]
    return list(dict.fromkeys(content_dims + _STYLE_DIMENSIONS[:3]))
```

Content words from the prompt are combined with fixed style axes (`lighting`, `color`, `mood`) to form a session-specific dimension set.

#### What Was Built

| File | Change |
|---|---|
| `app/core/schema.py` | `+dimension_ratings` field on `FeedbackEvent` and `FeedbackRequest` |
| `app/feedback/normalization.py` | Passes `dimension_ratings` through to `FeedbackEvent` |
| `app/main.py` | `extract_prompt_dimensions()`, passes `prompt_dimensions` to session template |
| `app/frontend/templates/session.html` | Per-candidate dimension rating widget (`dim-star-button`, `dim-rating-input`) |
| `app/frontend/static/app.js` | `dim-star-button` click handlers, `collectDimensionRatings()` |
| `app/frontend/static/styles.css` | `.dim-star-button`, `.dimension-rating-section`, `.dimension-row-static` |

---

### Feature 3 — Priority Weighting

#### Motivation

Not all dimensions matter equally to every user. Someone shooting a landscape cares most about `mood` and `lighting`; someone generating product shots cares most about `detail` and `realism`. Without a way to express relative importance, dimension ratings are treated as equally weighted — which may not match the user's actual priorities.

#### How It Works

Above the image grid, a drag-to-rank list of all prompt dimensions is displayed. The user drags rows to set priority order (1 = most important). When dimension star ratings are changed **or** the priority order is reordered, the overall star rating for each candidate is automatically recalculated using a weighted average:

```
weight(dim) = N - priority_index     # priority 1 → weight N, priority N → weight 1

weighted_score = Σ(weight(dim) × rating(dim)) / Σ(weight(dim))
```

The overall star display updates in real time so the user can see the effect of reordering.

#### What Was Built

| File | Change |
|---|---|
| `app/frontend/templates/session.html` | Global `.global-priority-list` section above image grid |
| `app/core/schema.py` | `+dimension_priorities` field on `FeedbackEvent` and `FeedbackRequest` |
| `app/feedback/normalization.py` | Passes `dimension_priorities` through to `FeedbackEvent` |
| `app/frontend/static/app.js` | `getpriorities()`, `recalcWeightedScore()`, drag-to-rank handlers with live badge renumbering, `collectDimensionPriorities()` |
| `app/frontend/static/styles.css` | `.global-priority-list`, `.dimension-row`, `.priority-badge`, `.dimension-row.dragging` |

---

### Feature 4 — Taste Profile

#### Motivation

Tomer's Convergence Detection answers: *"Has the image settled?"*  
This feature answers the complementary question: *"What has the model learned about this user?"*

After several rounds of feedback, the system accumulates evidence about which dimensions the user consistently cares about, which are noisy, and whether preferences are strengthening or weakening over time. Without surfacing this information, the user has no way to know whether the model is actually learning their taste.

#### How It Works

`compute_taste_profile(rounds)` processes all `FeedbackEvent.dimension_ratings` and `dimension_priorities` from all completed rounds and computes per-dimension statistics:

| Metric | Computation |
|---|---|
| **Mean rating** | Average score given to this dimension across all candidates and rounds |
| **Consistency** | `1 - std / 2.5` — high consistency means low variance in ratings |
| **Signal strength** | `(mean / 5) × consistency` — high mean + high consistency = strong signal |
| **Trend** | Compare first-half rounds vs second-half rounds: `↑ growing`, `→ stable`, `↓ declining` |

An overall **Profile confidence** score is computed as the sample-weighted mean signal across all dimensions.

**UI — live panel on the session page:**

```
Taste Profile                              Profile confidence: 64%
─────────────────────────────────────────────────────────────────
lighting      ████████░░  80%  ↑
composition   ██████░░░░  60%  →
color         ███░░░░░░░  30%  ↓
```

The panel appears automatically after the first round with dimension feedback and updates after every submission.

#### What Was Built

| File | Change |
|---|---|
| `app/feedback/taste_profile.py` | New file — `compute_taste_profile()`, pure computation, no side effects |
| `app/main.py` | Import + pass `taste_profile` to session template |
| `app/frontend/templates/session.html` | Taste Profile card with bar chart, trend arrows, confidence score |
| `app/frontend/static/styles.css` | `.taste-profile-card`, `.taste-bar`, `.taste-trend-*` |

---

### Feature 5 — Delete Session

One-click delete button next to each session on the dashboard. Removes the session and all its rounds from storage immediately without a page reload.

| File | Change |
|---|---|
| `app/storage/repository.py` | `delete_session()` — deletes from `sessions` and `rounds` tables |
| `app/engine/orchestrator.py` | `delete_session()` delegate |
| `app/main.py` | `DELETE /sessions/{session_id}` endpoint |
| `app/frontend/templates/index.html` | Delete button per row + `<script src="/static/app.js">` |
| `app/frontend/static/app.js` | `.delete-session-button` click handler with confirmation dialog |

---

## Summary of All Files Changed or Created (Semester B)

### New files

| File | Purpose |
|---|---|
| `app/feedback/taste_profile.py` | Taste Profile computation logic |
| `app/frontend/templates/style_calibration.html` | Style calibration page (15-image grid) |
| `app/frontend/templates/calibration.html` | Aesthetic style tag selection page |

### Modified files

| File | Change |
|---|---|
| `app/core/schema.py` | `+dimension_ratings`, `+dimension_priorities` on `FeedbackEvent` and `FeedbackRequest` |
| `app/feedback/normalization.py` | Pass new fields through to `FeedbackEvent` |
| `app/engine/orchestrator.py` | `generate_calibration_round()`, `submit_calibration()`, `delete_session()` |
| `app/storage/repository.py` | `delete_session()` |
| `app/main.py` | 5 new endpoints, `extract_prompt_dimensions()`, `compute_taste_profile()` injection |
| `app/frontend/templates/session.html` | Priority section, dimension rating widgets, Taste Profile card |
| `app/frontend/templates/setup.html` | Aesthetic profile banner, calibration link |
| `app/frontend/templates/index.html` | Delete buttons, app.js script tag |
| `app/frontend/static/app.js` | All new feature handlers and collectors |
| `app/frontend/static/styles.css` | All new component styles |

**No existing algorithms, updaters, samplers, or feedback modes were modified.**
