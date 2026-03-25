# Research System Specification: Interactive Prompt-Embedding Steering for Stable Diffusion

## 1. Purpose

This document specifies a research system for studying **human-in-the-loop steering of text-to-image diffusion models** by modifying prompt-conditioning embeddings rather than only rewriting the visible text prompt.

The system is intended for research, not production. It must make it easy to compare:

- different **candidate sampling policies**
- different **user feedback mechanisms**
- different **preference learning and update rules**
- different **trust-region and anchoring strategies**
- different **seed-control and robustness-validation procedures**

The system should expose these choices through a simple HTML interface and a modular backend so that experiments can be repeated, logged, and compared.

---

## 2. Motivation

### 2.1 Problem

Text-to-image diffusion models such as Stable Diffusion are highly sensitive to prompt wording, negative prompts, seed, guidance scale, scheduler, and other generation parameters. Small changes in wording can cause discontinuous changes in output. This makes user steering difficult:

- prompt editing is discrete rather than continuous
- many useful changes are hard to describe precisely in words
- user intent often evolves after seeing generated images
- the effect of a prompt change is mixed with seed variation
- naive trial-and-error wastes time and user attention

### 2.2 Central research idea

Instead of treating the user prompt as a fixed string, the system treats the prompt-conditioned embedding as a **searchable control object**. It then performs an iterative loop:

1. start from the initial prompt embedding
2. generate several modified embedding candidates
3. generate images for those candidates
4. collect user feedback
5. estimate a preferred direction or region in embedding space
6. update the steering state
7. repeat

This enables a controlled study of whether user preference can be learned through local search in a low-dimensional steering space.

### 2.3 Research value

This system supports research questions such as:

- Does local exploration in prompt-embedding space produce semantically meaningful visual changes?
- Which feedback type is most informative: scalar rating, pairwise comparison, ranking, critique text, or mixed feedback?
- Which sampling strategy best balances exploitation and discovery?
- How much does seed variation confound learned preference?
- Do users prefer global embedding movement or semantically separated subspaces such as style, composition, and realism?
- Can a lightweight preference model personalize generation faster than manual prompt rewriting?

### 2.4 Why a research platform is needed

Most image-generation interfaces optimize for convenience, not controlled experimentation. A research platform must instead provide:

- exact reproducibility
- pluggable exploration policies
- pluggable update mechanisms
- strong logging and replay
- support for A/B evaluation of interaction loops
- exportable experiment traces

---

## 3. Theoretical Background

This section is self-contained and written for readers who understand machine learning at a basic level but do not necessarily specialize in diffusion models.

### 3.1 How text-to-image diffusion works at a high level

A text-to-image diffusion model learns to generate an image by progressively denoising a random latent representation while being conditioned on a text prompt.

A simplified pipeline is:

1. tokenize the text prompt
2. encode the tokens into text embeddings
3. sample a random latent noise tensor
4. iteratively denoise the latent using a U-Net conditioned on the text embeddings
5. decode the final latent into an image using a VAE decoder

The important point for this system is that the text prompt does not directly control the image. The model actually consumes a **tensor of embeddings** derived from the prompt.

### 3.2 Prompt text versus prompt embedding

The visible prompt string is discrete. The embedding is continuous.

That distinction matters:

- editing text changes the embedding indirectly and often non-smoothly
- editing the embedding allows continuous local movement
- continuous movement makes optimization and controlled experimentation easier

A prompt embedding is typically a sequence of token-level vectors, not a single vector. For research purposes, the system may work with:

- the full token embedding tensor
- a pooled vector representation
- a low-rank parameterization of embedding offsets

### 3.3 Why low-dimensional steering is useful

Directly searching the full embedding tensor is high-dimensional, expensive, and unstable. A better approach is to define a low-dimensional steering code:

- let `E0` be the original prompt embedding tensor
- let `U` be a learned or predefined basis of steering directions
- let `z` be a low-dimensional steering code
- define the active embedding as `E(z) = E0 + U z`

Now the system searches over `z` rather than over the full embedding space.

Advantages:

- easier optimization
- easier uncertainty estimation
- better interpretability
- easier comparison of update policies

### 3.4 Human preference learning

The system is not trying to predict a ground-truth target image. It is trying to infer what the user prefers.

This is a preference-learning problem. A preference model estimates a hidden reward or utility function from observed feedback.

Examples:

- scalar rating: image gets a score from 1 to 5
- pairwise feedback: image A is preferred over image B
- ranking: sort images from best to worst
- critique text: “keep composition, make it more realistic”

The reward function is not directly known. It is inferred from user responses.

### 3.5 Exploration versus exploitation

This is the core sequential decision problem.

- **Exploitation** means sampling near the currently estimated best direction.
- **Exploration** means sampling directions that reduce uncertainty or test alternative hypotheses.

If the system only exploits, it may converge too early to a mediocre local optimum.
If it only explores, it wastes user effort and does not improve quickly.

A research goal of the platform is to compare policies for balancing the two.

### 3.6 Seed sensitivity

Text-to-image diffusion is stochastic. The random seed can change image content substantially even when the prompt embedding stays fixed.

Therefore, preference learning must separate:

- change caused by embedding movement
n- change caused by random seed

The system must support explicit seed-control policies:

- same-seed comparison within a round
- multi-seed validation of promising candidates
- robustness metrics across seeds

### 3.7 Trust region and anchoring

Large moves in embedding space may drift away from the user’s initial intention. The system therefore uses two stabilizers:

- **trust region**: restrict step size per round
- **anchor to original prompt**: penalize excessive drift from `z = 0`

This lets the system search locally without losing semantic coherence.

### 3.8 Why multiple update mechanisms should be compared

There is no reason to assume one update rule is best. A research platform should compare:

- direct winner averaging
- linear preference models
- pairwise Bradley-Terry style models
- Bayesian preference models
- bandit-style updates
- critique-conditioned updates
- hybrid updates using both explicit and implicit feedback

---

## 4. Research Goals and Non-Goals

### 4.1 Goals

The system must support controlled experiments on:

- embedding-space candidate generation
- user feedback collection
- user-preference inference
- iterative update policies
- robustness to randomness
- reproducibility and traceability

### 4.2 Non-goals

The initial version is not required to:

- provide best-in-class image quality
- support multi-user concurrent production traffic
- provide full model fine-tuning
- support every diffusion family
- optimize GPU throughput aggressively
- provide advanced authentication or billing

---

## 5. High-Level System Overview

The system consists of six major parts:

1. **Frontend**: simple HTML interface for prompt entry, image display, feedback collection, and experiment controls
2. **Experiment Controller**: orchestrates rounds, policies, and logs
3. **Generation Engine**: calls the diffusion pipeline and handles prompt embeddings
4. **Sampling Module**: proposes candidate steering codes or embedding offsets
5. **Preference / Update Module**: learns from feedback and computes the next state
6. **Storage and Evaluation Layer**: records experiments, metrics, artifacts, and replays

Data flow:

1. user creates or loads an experiment
2. prompt is encoded to base embedding
3. current strategy proposes candidates
4. engine generates images
5. frontend displays them
6. user provides feedback
7. backend updates preference state
8. next round starts

---

## 6. Core Research Abstractions

### 6.1 Experiment

An experiment is a fully specified configuration and all data generated under it.

Fields:

- experiment ID
- title
- description
- date/time
- model checkpoint
- sampler strategy
- feedback strategy
- update strategy
- random seed policy
- number of rounds
- current status
- user notes

### 6.2 Session

A session is one interactive run of one experiment with one prompt and one user.

Fields:

- session ID
- experiment ID
- prompt text
- negative prompt text
- base embedding cache key
- steering basis configuration
- current state `z_t`
- round count
- final selected candidate

### 6.3 Round

A round is one propose-generate-display-feedback-update cycle.

Fields:

- round index
- incumbent `z_t`
- sampled candidate list
- seed policy used
- rendered images
- user feedback
- updated model state summary
- latency metrics

### 6.4 Candidate

A candidate is one proposed point in steering space.

Fields:

- candidate ID
- round index
- steering vector `z`
- embedding offset metadata
- generation parameters
- seed
- image path
- sampler tag (`exploit`, `explore`, `mirror`, `validation`, etc.)
- predicted score and uncertainty

### 6.5 Feedback event

A feedback event records one user action.

Fields:

- feedback ID
- candidate IDs involved
- feedback type
- timestamp
- payload
- optional natural-language critique

---

## 7. Frontend Specification (Simple HTML Interface)

### 7.1 Design principles

The interface should be intentionally simple:

- plain HTML + minimal JavaScript
- no heavy front-end framework required for v1
- fast iteration over UX for research tasks
- easy to inspect DOM and debug
- accessible layout that keeps the experiment state visible

### 7.2 Main pages

#### A. Home / Experiment Dashboard

Purpose:

- create a new experiment
- list previous experiments
- resume a session
- compare results

Main elements:

- experiment list table
- “new experiment” button
- filters by model, strategy, date
- quick links to export logs

#### B. Session Setup Page

Inputs:

- prompt text
- negative prompt text
- model checkpoint selector
- image size
- number of candidates per round
- seed policy selector
- sampler strategy selector
- feedback mechanism selector
- update mechanism selector
- trust-region parameters
- anchor strength

Actions:

- start session
- save config template
- load preset

#### C. Interactive Steering Page

Main layout:

- header with current experiment and round
- left control panel
- center image grid
- right state summary panel

Controls:

- next round
- regenerate round
- pause session
- revert to previous round
- pin candidate as incumbent
- mark candidate as favorite
- export round

Image grid requirements:

- show 4 to 12 images per round
- consistent labeling: A, B, C, ... or numeric IDs
- display candidate metadata on demand
- allow image zoom
- allow fixed layout across rounds

Feedback widgets must be switchable by experiment mode:

- scalar rating controls
- rank ordering drag-and-drop
- pairwise winner buttons
- top-k selection
- checkbox shortlist
- text critique box

#### D. Replay / Analysis Page

Purpose:

- replay rounds in order
- inspect generated images and feedback
- compare update trajectories
- see metric summaries

### 7.3 Frontend state model

The frontend should maintain:

- active experiment config
- current session ID
- current round number
- displayed candidates
- local unsaved feedback state
- pending request status
- error messages

### 7.4 Accessibility requirements

- keyboard navigation for candidate selection
- screen-readable labels
- non-color-only visual distinctions
- image labels visible without hover

### 7.5 Frontend technology recommendation

Preferred initial stack:

- HTML5
- CSS with simple modular stylesheet
- vanilla JavaScript or lightweight TypeScript
- fetch-based REST calls
- no build step required in the first prototype if possible

---

## 8. Backend Specification

### 8.1 Recommended stack

A suitable baseline stack:

- Python 3.11+
- FastAPI backend
- Diffusers-based generation engine
- SQLite for local experimentation, PostgreSQL optional later
- filesystem or object storage for images and logs
- Pydantic models for API contracts

### 8.2 Backend modules

#### A. API layer

Responsibilities:

- session management
- round generation endpoints
- feedback submission
- experiment listing
- replay and export endpoints

#### B. Orchestrator

Responsibilities:

- create session state
- call sampler
- call generation engine
- persist round data
- invoke updater after feedback

#### C. Embedding manager

Responsibilities:

- encode prompts
- cache text embeddings
- construct steering basis
- apply steering vector `z`
- manage pooled versus token-level modes

#### D. Sampling manager

Responsibilities:

- sample candidate points under configured policy
- label candidates by role
- obey trust region and diversity constraints

#### E. Generation manager

Responsibilities:

- generate images from embeddings
- manage seed policy
- record latency and failures
- retry or surface errors cleanly

#### F. Preference/update manager

Responsibilities:

- normalize feedback into internal format
- fit or update preference model
- compute incumbent state update
- adjust trust radius or uncertainty state

#### G. Evaluation manager

Responsibilities:

- compute online metrics
- compute cross-session summaries
- generate exports and plots

---

## 9. Data Model Specification

### 9.1 Core tables or collections

#### experiments
- id
- created_at
- name
- description
- config_json

#### sessions
- id
- experiment_id
- prompt
- negative_prompt
- model_name
- created_at
- status
- basis_type
- current_round
- current_z_json

#### rounds
- id
- session_id
- round_index
- incumbent_z_json
- trust_radius
- seed_policy
- created_at
- update_summary_json

#### candidates
- id
- round_id
- candidate_index
- z_json
- sampler_role
- predicted_score
- predicted_uncertainty
- seed
- image_path
- generation_params_json

#### feedback_events
- id
- round_id
- type
- payload_json
- critique_text
- created_at

#### artifacts
- id
- session_id
- type
- path
- metadata_json

### 9.2 File artifacts

Artifacts to store:

- generated images
- round manifests
- session config snapshots
- evaluation reports
- exported CSV / JSON traces

---

## 10. API Specification

### 10.1 Example REST endpoints

#### POST /experiments
Create a new experiment.

Request body:
- name
- description
- config

Response:
- experiment ID

#### GET /experiments
List experiments.

#### POST /sessions
Create a session from an experiment config.

Request body:
- experiment ID or full config
- prompt
- negative prompt

Response:
- session ID
- initial state

#### POST /sessions/{session_id}/rounds/next
Generate the next round of candidates.

Response:
- round ID
- candidate metadata
- image URLs
- state summary

#### POST /rounds/{round_id}/feedback
Submit feedback for the round.

Request body:
- feedback type
- payload
- optional critique text

Response:
- update summary
- next incumbent state

#### GET /sessions/{session_id}
Get full session summary.

#### GET /sessions/{session_id}/replay
Get ordered rounds and artifacts.

#### GET /sessions/{session_id}/export
Export logs, metrics, and artifacts manifest.

---

## 11. Steering Representation Specification

### 11.1 Required modes

The system must support at least three steering representations.

#### Mode A: Low-dimensional latent code
`E(z) = E0 + U z`

Recommended default for research.

#### Mode B: Token-level offset mode
Apply learned or sampled offsets to selected token embeddings.

Useful for analyzing more local control.

#### Mode C: Pooled embedding mode
Apply a simplified offset to a pooled representation.

Useful as a baseline, even if weaker.

### 11.2 Basis construction strategies

The system should support:

- random orthonormal basis
- PCA basis from prior accepted moves
- hand-defined semantic basis
- basis from prompt rewrite differences
- hybrid basis

### 11.3 Constraints

Steering representation must support:

- trust-region clipping
- optional anchor-to-origin penalty
- optional subspace masks
- diversity computation between candidates

---

## 12. Sampling Strategy Specification

This is a main experimental axis. The system must make samplers plug-in based.

### 12.1 Sampler interface

Each sampler must implement:

- `propose(state, config, preference_model) -> list[candidate]`
- candidate role tags
- reproducible sampling under fixed RNG state

### 12.2 Required baseline samplers

#### A. Random local sampler
Sample directions uniformly or Gaussian within a trust ball.

Purpose:
- sanity baseline

#### B. Exploit-plus-orthogonal sampler
Batch composition:
- exploit near estimated best direction
- refine around that direction
- explore orthogonal directions
- optional mirror check

Purpose:
- strong baseline for interactive search

#### C. Uncertainty-guided sampler
Prefer candidates with high estimated uncertainty and adequate predicted utility.

Purpose:
- active learning baseline

#### D. Thompson-style sampler
Sample from the posterior over reward parameters, then optimize under that sample.

Purpose:
- principled exploration/exploitation tradeoff

#### E. Quality-diversity sampler
Generate candidates that are both strong and diverse across simple descriptors.

Purpose:
- preserve multiple promising modes

### 12.3 Optional advanced samplers

- CMA-ES style covariance adaptation sampler
- dueling-bandit comparison sampler
- critique-conditioned sampler
- subspace-adaptive sampler

### 12.4 Batch composition controls

Per round, the system should log and optionally enforce:

- number of exploit candidates
- number of explore candidates
- number of validation candidates
- number of mirror candidates
- number of replay candidates from previous rounds

---

## 13. Feedback Mechanism Specification

This is another major experimental axis.

### 13.1 Unified internal feedback schema

All feedback must be normalized to a common event format. Even if the frontend collects ratings or rankings, the backend should be able to derive pairwise comparisons when useful.

### 13.2 Required feedback modes

#### A. Scalar ratings
User rates each image on a fixed scale.

Pros:
- easy to collect

Cons:
- noisy calibration

#### B. Pairwise comparison
User chooses preferred image between two candidates.

Pros:
- clean signal

Cons:
- may require many comparisons

#### C. Partial ranking
User ranks top-k candidates.

Pros:
- more informative than single winner

#### D. Winner + critique
User selects best candidate and provides a short natural-language reason.

Pros:
- can support directional interpretation later

#### E. Select-all-that-fit
User marks all acceptable candidates.

Pros:
- useful when multiple modes are valid

### 13.3 Feedback quality controls

The platform should support:

- repeated hidden comparison for consistency measurement
- confidence self-report by user
- optional time-to-decision logging
- optional skip / uncertain action

---

## 14. Update Mechanism Specification

The update module takes session state and normalized feedback, and computes the next incumbent and preference state.

### 14.1 Update interface

Each updater must implement:

- `update(state, candidates, feedback, model) -> new_state, update_summary`

### 14.2 Required baseline updaters

#### A. Winner-copy updater
Set next incumbent to the winning candidate.

Purpose:
- simplest baseline

#### B. Winner-average updater
Move partially toward top-rated or top-ranked candidates.

Purpose:
- simple smooth update baseline

#### C. Linear preference model updater
Fit a linear model on steering features and move along estimated reward gradient.

Purpose:
- practical baseline

#### D. Bradley-Terry / pairwise logistic updater
Fit pairwise preference probabilities and derive next step from estimated utility.

Purpose:
- strong baseline for pairwise data

#### E. Bayesian updater
Maintain posterior uncertainty and update using preference observations.

Purpose:
- enables uncertainty-based sampling

### 14.3 Optional advanced updaters

- contextual bandit updater
- critique-conditioned latent editing updater
- trust-region policy optimization updater
- multi-subspace independent updater

### 14.4 Stabilization controls

Each updater should optionally support:

- trust-region clipping
- anchor regularization
- momentum across rounds
- rollback on confidence drop
- incumbent preservation if uncertainty rises sharply

---

## 15. Seed Policy Specification

### 15.1 Required seed modes

#### A. Fixed-per-round
All candidates in the round share the same seed.

Purpose:
- isolate embedding effect

#### B. Fixed-per-candidate-role
Validation candidates use alternate seeds while main comparison candidates remain fixed.

#### C. Multi-seed averaging
A candidate is rendered under multiple seeds and summarized.

Purpose:
- robustness analysis

### 15.2 Seed logging requirements

For every candidate, log:

- seed
- scheduler settings
- inference step count
- guidance scale
- image resolution

---

## 16. Evaluation and Metrics Specification

The platform must support both online and offline evaluation.

### 16.1 Interaction-level metrics

- average time per round
- average time per feedback action
- number of rounds until user stops
- number of generated images per session
- user consistency score

### 16.2 Optimization metrics

- improvement in user preference score over rounds
- incumbent win rate against earlier incumbents
- regret proxy relative to best observed candidate
- preference-model calibration where applicable

### 16.3 Robustness metrics

- performance under alternate seeds
- rank stability across seeds
- variance of score estimates

### 16.4 Diversity metrics

- pairwise embedding distance among candidates
- pairwise perceptual image distance
- mode coverage proxy

### 16.5 Drift metrics

- distance of current `z_t` from origin
- distance from previous incumbent
- semantic drift notes if critique text is used

### 16.6 Human-centered metrics

- perceived controllability
- perceived usefulness of feedback mechanism
- fatigue level after session
- subjective satisfaction with final image

---

## 17. Logging and Reproducibility Specification

### 17.1 Mandatory logging

Every experiment must log:

- full config snapshot
- random seeds
- software version
- model checkpoint identifier
- hardware metadata
- API request/response manifests for each round
- serialized feedback events

### 17.2 Replay requirements

A session replay must reconstruct:

- prompt and config
- round order
- candidate images
- feedback timeline
- updater summaries

### 17.3 Versioning

Version the following independently:

- frontend version
- backend version
- model wrapper version
- sampler version
- updater version
- schema version

---

## 18. Error Handling and Fault Tolerance

The system must handle:

- generation failure for one candidate
- timeout during image generation
- partial round completion
- duplicate feedback submissions
- invalid ranking payload
- GPU out-of-memory conditions
- experiment resume after crash

Behavioral requirements:

- failures should be surfaced in the UI clearly
- one failed candidate should not invalidate the whole session unless configured
- session state should be durable after each completed round and feedback submission

---

## 19. Security and Privacy Notes

Because this is a research prototype, security requirements are modest but should not be ignored.

Minimum requirements:

- no arbitrary file path input from frontend
- input validation on all API endpoints
- optional session isolation if multiple users are supported later
- stored critique text treated as user data
- experiment exports should not leak server-local paths

---

## 20. Suggested Project Structure

```text
project/
  app/
    api/
      routes_experiments.py
      routes_sessions.py
      routes_rounds.py
      routes_exports.py
    core/
      config.py
      logging.py
      schema.py
    engine/
      prompt_encoder.py
      steering_basis.py
      generation.py
      seeds.py
    samplers/
      base.py
      random_local.py
      exploit_orthogonal.py
      uncertainty.py
      thompson.py
      quality_diversity.py
    feedback/
      normalization.py
      validation.py
    updaters/
      base.py
      winner_copy.py
      winner_average.py
      linear_pref.py
      bradley_terry.py
      bayesian.py
    evaluation/
      metrics.py
      replay.py
      reports.py
    storage/
      db.py
      models.py
      repository.py
    frontend/
      templates/
        index.html
        setup.html
        session.html
        replay.html
      static/
        styles.css
        app.js
  tests/
    unit/
    integration/
    e2e/
    fixtures/
  scripts/
    run_dev.py
    export_session.py
    replay_session.py
  docs/
    specification.md
```

---

## 21. Test Suite Specification

The test suite is a required part of the research platform because correctness, comparability, and reproducibility are central.

### 21.1 Test categories

The system must include:

- unit tests
- integration tests
- end-to-end tests
- deterministic replay tests
- regression tests for experiment schemas

### 21.2 Unit tests

#### A. Steering representation tests

Verify:

- prompt encoding returns expected shape
- basis construction returns correct dimensions
- `E(z) = E0 + U z` applies correct tensor shape rules
- trust-region clipping works
- anchor penalty reduces drift

#### B. Sampler tests

Verify:

- sampler returns correct number of candidates
- candidates respect trust radius
- orthogonal sampler reduces alignment with exploit direction
- deterministic sampling under fixed RNG state
- diversity filter removes near duplicates

#### C. Feedback normalization tests

Verify:

- ratings convert to normalized internal events
- rankings convert to pairwise preferences correctly
- invalid ranking payloads are rejected
- duplicate selections are rejected where required

#### D. Updater tests

Verify:

- winner-copy selects winning candidate exactly
- averaging updater interpolates correctly
- linear updater produces gradient-shaped move in expected direction
- pairwise updater handles symmetric cases correctly
- Bayesian updater updates uncertainty monotonically under repeated evidence where expected

#### E. Seed policy tests

Verify:

- fixed-per-round uses same seed
- validation candidates get alternate seeds when configured
- seed manifest is saved for all candidates

### 21.3 Integration tests

#### A. Session lifecycle test

Flow:

1. create experiment
2. create session
3. request first round
4. submit feedback
5. request next round
6. verify state progression and persistence

#### B. Generation pipeline test

Use a lightweight mock or tiny test pipeline when full image generation is too expensive.

Verify:

- embeddings flow from encoder through steering to generator
- generation failures are captured and surfaced

#### C. Replay integrity test

Verify:

- exported replay matches stored rounds and feedback
- images and metadata align correctly

#### D. Strategy plug-in test

Verify:

- samplers and updaters can be swapped without breaking controller logic

### 21.4 End-to-end tests

Using browser automation or HTTP-level testing, verify:

- user can create experiment from UI
- user can start session
- user can rate, rank, or compare candidates
- user can move to next round
- replay page renders completed session correctly

### 21.5 Deterministic replay tests

These tests are critical.

Given:

- fixed prompt
- fixed experiment config
- fixed RNG seeds
- mocked or deterministic generation backend

The replay must reproduce:

- same candidate proposals
- same order of candidates
- same update steps
- same stored metrics

### 21.6 Schema regression tests

Verify that old experiment exports can still be loaded or migrated.

### 21.7 Test fixtures

Required fixtures:

- deterministic prompt embedding fixture
- synthetic candidate set fixture
- fake user feedback fixture
- mock image generator fixture
- small replay log fixture

### 21.8 Acceptance test criteria

The prototype is acceptable when:

- all unit tests pass
- main session lifecycle integration test passes
- deterministic replay test passes
- at least one sampler and one updater can be swapped by config only
- UI supports at least two feedback modes
- logs can be exported and replayed

---

## 22. Minimal Viable Research Prototype

The first working version should include only the following mandatory features.

### 22.1 Mandatory capabilities

- Stable Diffusion or SDXL backend through Diffusers
- low-dimensional steering code mode
- one HTML interactive session page
- one replay page
- at least three samplers:
  - random local
  - exploit-plus-orthogonal
  - uncertainty-guided
- at least three feedback modes:
  - scalar rating
  - pairwise comparison
  - top-k ranking
- at least three updaters:
  - winner-copy
  - winner-average
  - linear preference updater
- fixed-per-round seed mode
- basic experiment export
- deterministic replay support

### 22.2 Nice-to-have but optional for v1

- critique text conditioning
- Bayesian preference model
- multi-seed validation mode
- quality-diversity archive
- user study report generator

---

## 23. Example Experimental Matrix

A useful first matrix for research comparison:

### Axis 1: Sampling
- random local
- exploit-plus-orthogonal
- uncertainty-guided

### Axis 2: Feedback
- scalar rating
- pairwise comparison
- top-3 ranking

### Axis 3: Update
- winner-average
- linear preference update
- pairwise logistic update

### Axis 4: Seed policy
- fixed-per-round
- fixed-per-round + periodic validation seeds

This creates a manageable but meaningful comparison grid.

---

## 24. Research Risks and Confounds

The system specification must explicitly acknowledge the main risks.

### 24.1 Seed confounding
A candidate may look best because of seed luck rather than embedding quality.

### 24.2 Human inconsistency
User preference may change or become inconsistent as they see more options.

### 24.3 Entangled directions
One steering move may affect multiple visual properties at once.

### 24.4 Interface bias
The layout or labeling of images may influence choice.

### 24.5 Fatigue effects
Long sessions may reduce feedback quality.

The system should log enough metadata to study these confounds later.

---

## 25. Deliverables for AI-Generated Implementation

An AI code generator receiving this specification should produce:

1. a Python FastAPI backend
2. a simple HTML/CSS/JS frontend
3. modular sampler and updater interfaces
4. one working diffusion generation wrapper
5. experiment persistence layer
6. replay/export support
7. a complete automated test suite following Section 21
8. documentation for local setup and running experiments

### 25.1 Code-generation constraints

Generated code should:

- prioritize clarity over framework complexity
- keep modules small and replaceable
- avoid unnecessary abstractions in v1
- separate research logic from web route logic
- include docstrings and type hints
- include configuration presets for quick experiments

### 25.2 Output artifacts expected from implementation

- runnable application
- sample config presets
- sample replay export
- test report output
- developer README

---

## 26. Final Summary

This system is a controlled research platform for studying iterative user-guided image generation by steering prompt embeddings in a diffusion model.

Its core design principles are:

- low-dimensional controllable steering representation
- explicit comparison of sampling policies
- explicit comparison of feedback mechanisms
- explicit comparison of update mechanisms
- strong logging and replay
- simple HTML interface for rapid experimentation
- reproducible testable architecture

The platform is valuable not because it assumes one best method, but because it creates a clean environment for discovering which combinations of steering representation, candidate sampling, feedback collection, and update logic actually work.
