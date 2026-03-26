# System Specification

## 1. Document Role

This document defines what the research platform must do, what components it contains, and what contracts must remain stable during implementation.

It is the primary functional specification for:

- application structure
- state and data contracts
- API behavior
- session and round lifecycle
- replay and reproducibility requirements

Related documents:

- [motivation.md](/E:/Projects/StableSteering/docs/motivation.md)
- [theoretical_background.md](/E:/Projects/StableSteering/docs/theoretical_background.md)
- [system_test_specification.md](/E:/Projects/StableSteering/docs/system_test_specification.md)
- [pre_implementation_blueprint.md](/E:/Projects/StableSteering/docs/pre_implementation_blueprint.md)

## 2. Scope

This specification covers the research prototype used to study interactive prompt-embedding steering for diffusion models.

It includes:

- frontend behavior
- backend services
- experiment, session, round, and candidate state
- persistence and replay
- strategy interfaces and constraints
- logging and reproducibility
- tracing and debugging surfaces

It does not define:

- production deployment architecture
- large-scale multi-tenant operations
- enterprise-grade security
- model training or fine-tuning pipelines

## 3. System Goals

The system must:

- support repeatable interactive steering sessions
- support multiple sampling, feedback, and update strategies
- preserve enough state for replay and analysis
- isolate randomness as much as practical
- stay simple enough for rapid research iteration

## 4. High-Level System Overview

The system consists of six major parts:

1. **Frontend**: interface for prompt entry, image display, feedback collection, replay, and export
2. **Experiment Controller**: orchestrates session lifecycle and round progression
3. **Generation Engine**: encodes prompts, applies steering, and renders images
4. **Sampling Module**: proposes steering candidates under a configured policy
5. **Preference / Update Module**: learns from feedback and computes the next incumbent
6. **Storage and Evaluation Layer**: persists state, computes metrics, and reconstructs replay data

## 5. Primary User Workflow

The canonical workflow is:

1. create or load an experiment
2. create a session with prompt and configuration
3. encode the base prompt and initialize steering state
4. propose round candidates
5. render candidate images
6. collect user feedback
7. update preference state and incumbent steering vector
8. repeat until the user stops
9. export or replay the session

## 6. Core Invariants

The following must remain true:

- each session uses an immutable configuration snapshot
- each round belongs to exactly one session
- each candidate belongs to exactly one round
- feedback is attached to exactly one round
- feedback for a round is accepted at most once
- seed information is persisted for every rendered candidate
- replay data is sufficient to reconstruct decision history
- session state is durable after each completed round and feedback submission
- a new round cannot be generated while the session is still awaiting feedback for the current round

## 7. Core Research Abstractions

### 7.1 Experiment

An experiment defines a reusable research configuration.

Required fields:

- experiment ID
- title
- description
- created timestamp
- model checkpoint
- steering mode
- sampler strategy
- feedback strategy
- update strategy
- seed policy
- candidate count
- trust-region settings
- anchoring settings
- status
- researcher notes

### 7.2 Session

A session is one interactive run of one experiment with one prompt.

Required fields:

- session ID
- experiment ID
- prompt text
- negative prompt text
- model name
- base embedding cache key
- steering basis configuration
- current state `z_t`
- current round index
- incumbent candidate ID if available
- session status
- final selected candidate if available

### 7.3 Round

A round is one propose-render-feedback-update cycle.

Required fields:

- round ID
- session ID
- round index
- incumbent `z_t`
- sampled candidate list
- seed policy used
- render status
- user feedback summary
- update summary
- latency metrics

### 7.4 Candidate

A candidate is one proposed point in steering space.

Required fields:

- candidate ID
- round ID
- candidate index within round
- steering vector `z`
- embedding offset metadata
- sampler role
- predicted score if available
- predicted uncertainty if available
- seed
- generation parameters
- image path or URL
- render status

### 7.5 Feedback Event

A feedback event records one user action on a round.

Required fields:

- feedback ID
- round ID
- candidate IDs involved
- feedback type
- payload
- optional critique text
- timestamp
- normalized internal representation

## 8. Lifecycle State Model

### 8.1 Experiment states

Recommended states:

- `draft`
- `active`
- `paused`
- `completed`
- `archived`

### 8.2 Session states

Recommended states:

- `created`
- `ready`
- `awaiting_feedback`
- `updating`
- `completed`
- `failed`
- `paused`

### 8.3 Candidate render states

Recommended states:

- `pending`
- `rendering`
- `succeeded`
- `failed`

## 9. Frontend Specification

### 9.1 Design principles

The frontend should be intentionally simple:

- plain HTML with minimal JavaScript
- minimal hidden state
- easy DOM inspection and debugging
- accessible controls
- predictable interaction patterns across rounds
- a visible trace surface during interactive use

### 9.2 Main pages

#### A. Experiment Dashboard

Purpose:

- create a new experiment
- list existing experiments
- resume a session
- compare results
- export logs

Required elements:

- experiment list
- summary columns
- filters by model, strategy, and date
- create experiment action
- resume session action
- export links

#### B. Session Setup Page

Required inputs:

- prompt text
- negative prompt text
- model checkpoint selector
- image size
- number of candidates per round
- seed policy selector
- sampler selector
- feedback selector
- updater selector
- trust-region parameters
- anchor strength

Required actions:

- start session
- save preset
- load preset

#### C. Interactive Steering Page

Required layout:

- header with experiment and round metadata
- control panel
- candidate image grid
- state summary panel
- trace panel

Required actions:

- next round
- regenerate current round
- pause session
- revert to previous round if supported
- pin candidate as incumbent
- mark candidate as favorite
- export round data

Required grid behavior:

- show 4 to 12 images per round
- use consistent candidate labeling
- display metadata on demand
- support image zoom
- preserve stable ordering within a round

Required feedback widgets:

- scalar rating
- rating-driven pairwise derivation
- rating-driven top-k derivation
- shortlist selection
- text critique entry

#### D. Replay / Analysis Page

Purpose:

- replay completed rounds in order
- inspect candidates and feedback
- inspect trajectory summaries
- inspect metrics and exports

### 9.3 Frontend state model

The frontend should maintain:

- active experiment config snapshot
- active session ID
- current round number
- current candidate set
- local unsaved feedback state
- request status
- recoverable error messages

### 9.4 Accessibility requirements

The interface must support:

- keyboard navigation
- visible labels without hover dependence
- non-color-only distinctions
- screen-readable control labels
- focus visibility for active controls

### 9.5 Frontend failure behavior

The UI must:

- surface per-candidate failures without hiding successful candidates
- preserve unsaved feedback where possible after recoverable errors
- prevent double submission when a request is already in flight
- show the current round status clearly
- make trace and error information inspectable during debugging

## 10. Backend Specification

### 10.1 Recommended stack

Baseline stack:

- Python 3.11+
- FastAPI
- Diffusers
- SQLite for local research
- filesystem image storage
- Pydantic models

### 10.2 Backend modules

#### A. API layer

Responsibilities:

- experiment management
- session creation and retrieval
- round generation
- feedback submission
- replay and export delivery
- trace event intake for the frontend

#### B. Orchestrator

Responsibilities:

- initialize session state
- call sampler
- call generation manager
- persist round data
- call updater after feedback
- enforce lifecycle transitions

#### C. Embedding manager

Responsibilities:

- encode prompts
- cache text embeddings
- construct steering basis
- apply steering vector `z`
- support pooled and token-level modes

#### D. Sampling manager

Responsibilities:

- produce candidates from current state
- apply trust-region constraints
- enforce diversity constraints
- label candidates by role

#### E. Generation manager

Responsibilities:

- render images from embeddings
- manage seed policy
- collect latency and failure metadata
- expose deterministic test hooks

#### F. Preference / update manager

Responsibilities:

- normalize feedback
- update preference model
- compute next incumbent state
- compute update summary
- apply stabilization controls

#### G. Evaluation manager

Responsibilities:

- compute online metrics
- compute aggregate session metrics
- prepare exports and plots

#### H. Storage layer

Responsibilities:

- persist structured state
- persist artifacts
- provide repository interfaces
- support replay queries

## 11. Data Model Specification

### 11.1 Core tables or collections

#### experiments

- `id`
- `created_at`
- `updated_at`
- `name`
- `description`
- `status`
- `config_json`

#### sessions

- `id`
- `experiment_id`
- `prompt`
- `negative_prompt`
- `model_name`
- `status`
- `basis_type`
- `current_round`
- `current_z_json`
- `incumbent_candidate_id`
- `created_at`
- `updated_at`

#### rounds

- `id`
- `session_id`
- `round_index`
- `incumbent_z_json`
- `trust_radius`
- `seed_policy`
- `render_status`
- `update_summary_json`
- `created_at`

#### candidates

- `id`
- `round_id`
- `candidate_index`
- `z_json`
- `sampler_role`
- `predicted_score`
- `predicted_uncertainty`
- `seed`
- `render_status`
- `image_path`
- `generation_params_json`

#### feedback_events

- `id`
- `round_id`
- `type`
- `payload_json`
- `normalized_payload_json`
- `critique_text`
- `created_at`

#### artifacts

- `id`
- `session_id`
- `type`
- `path`
- `metadata_json`
- `created_at`

### 11.2 File artifacts

Artifacts to store:

- generated images
- round manifests
- configuration snapshots
- exported replay bundles
- evaluation reports
- JSON trace logs

## 12. API Specification

### 12.1 API conventions

The API should follow these rules:

- all responses are JSON except artifact downloads
- all write operations return persisted identifiers
- every error returns a structured code and human-readable message
- session config becomes immutable once the session is created
- round generation is idempotent only when explicitly requested

### 12.2 Example endpoints

#### POST `/experiments`

Create a new experiment.

Request body:

- `name`
- `description`
- `config`

Response:

- `experiment_id`

#### GET `/experiments`

List experiments.

#### GET `/experiments/{experiment_id}`

Return full experiment metadata and configuration.

#### POST `/sessions`

Create a session from an experiment or full config.

Request body:

- `experiment_id` or inline `config`
- `prompt`
- `negative_prompt`

Response:

- `session_id`
- `initial_state`

#### GET `/sessions/{session_id}`

Return session summary and current state.

#### POST `/sessions/{session_id}/rounds/next`

Generate the next round of candidates.

Response:

- `round_id`
- `candidate_metadata`
- `image_urls`
- `state_summary`

#### POST `/rounds/{round_id}/feedback`

Submit feedback for a round.

Request body:

- `feedback_type`
- `payload`
- optional `critique_text`

Response:

- `update_summary`
- `next_incumbent_state`

#### GET `/sessions/{session_id}/replay`

Return ordered rounds, artifacts, and summaries for replay.

#### POST `/frontend-events`

Persist browser-side trace events for debugging and auditability.

#### GET `/sessions/{session_id}/export`

Export logs, metrics, and artifact manifest.

## 13. Steering Representation Specification

### 13.1 Required modes

The system must support at least:

- low-dimensional latent code
- token-level offset mode
- pooled embedding mode

### 13.2 Default steering equation

For low-dimensional steering:

`E(z) = E0 + U z`

Where:

- `E0` is the base embedding
- `U` is the steering basis
- `z` is the controllable code

### 13.3 Basis construction strategies

The system should support:

- random orthonormal basis
- PCA basis from prior accepted moves
- hand-defined semantic basis
- basis from prompt rewrite differences
- hybrid basis

### 13.4 Representation constraints

The steering representation must support:

- trust-region clipping
- anchor-to-origin regularization
- optional subspace masks
- candidate diversity measurement

## 14. Sampling Strategy Specification

### 14.1 Sampler contract

Each sampler must implement:

- `propose(state, config, preference_model) -> list[candidate]`
- candidate role tagging
- reproducible behavior under fixed RNG state

### 14.2 Required baseline samplers

The system must include:

- random local sampler
- exploit-plus-orthogonal sampler
- uncertainty-guided sampler

### 14.3 Optional advanced samplers

The system may later include:

- Thompson-style sampler
- quality-diversity sampler
- CMA-ES style sampler
- dueling-bandit sampler
- critique-conditioned sampler
- subspace-adaptive sampler

### 14.4 Batch composition controls

Per round, the system should log and optionally constrain:

- exploit candidate count
- explore candidate count
- validation candidate count
- mirror candidate count
- replay candidate count

## 15. Feedback Mechanism Specification

### 15.1 Unified schema

All frontend feedback must normalize into one internal event format.

The backend should derive pairwise preferences from richer signals when useful.

### 15.2 Required feedback modes

The system must support:

- scalar ratings
- pairwise comparison
- partial ranking
- winner plus critique
- select-all-that-fit

### 15.3 Feedback quality controls

The platform should support:

- hidden repeated comparisons
- user confidence reporting
- decision-time logging
- uncertain or skip actions

## 16. Update Mechanism Specification

### 16.1 Updater contract

Each updater must implement:

- `update(state, candidates, feedback, model) -> new_state, update_summary`

### 16.2 Required baseline updaters

The system must include:

- winner-copy updater
- winner-average updater
- linear preference updater

### 16.3 Optional advanced updaters

The system may later include:

- Bradley-Terry / pairwise logistic updater
- Bayesian updater
- contextual bandit updater
- critique-conditioned updater
- trust-region policy optimizer
- multi-subspace updater

### 16.4 Stabilization controls

Each updater should optionally support:

- trust-region clipping
- anchor regularization
- momentum
- rollback on confidence drop
- incumbent preservation under instability

## 17. Seed Policy Specification

### 17.1 Required seed modes

The system must support:

- fixed-per-round
- fixed-per-candidate-role
- multi-seed averaging

### 17.2 Seed metadata requirements

For every candidate, persist:

- seed
- scheduler settings
- inference step count
- guidance scale
- image resolution

## 18. Evaluation and Metrics Specification

The platform must support both online and offline evaluation.

### 18.1 Interaction metrics

- average time per round
- average time per feedback action
- rounds until stop
- images generated per session
- user consistency score

### 18.2 Optimization metrics

- preference improvement over rounds
- incumbent win rate against earlier incumbents
- regret proxy relative to best observed candidate
- model calibration where applicable

### 18.3 Robustness metrics

- performance under alternate seeds
- rank stability across seeds
- score estimate variance

### 18.4 Diversity metrics

- pairwise embedding distance
- perceptual image distance
- mode coverage proxy

### 18.5 Drift metrics

- distance from origin
- distance from previous incumbent
- semantic drift notes where available

### 18.6 Human-centered metrics

- perceived controllability
- perceived usefulness of feedback
- fatigue level
- final-image satisfaction

## 19. Logging and Reproducibility Specification

### 19.1 Mandatory logging

Every experiment must log:

- full config snapshot
- random seeds
- software version
- model checkpoint identifier
- hardware metadata
- request and response manifests for each round
- serialized feedback events
- request-level backend traces
- browser-submitted frontend trace events

### 19.2 Replay requirements

A replay must reconstruct:

- prompt and config
- round order
- candidate images
- feedback timeline
- updater summaries

### 19.3 Versioning

Version independently:

- frontend
- backend
- model wrapper
- sampler
- updater
- schema

## 20. Error Handling and Fault Tolerance

The system must handle:

- one-candidate generation failure
- render timeout
- partial round completion
- duplicate feedback submission
- invalid ranking payload
- GPU out-of-memory events
- experiment resume after crash

Behavioral requirements:

- failures are visible in the UI
- one failed candidate does not invalidate the whole round by default
- durable state is written after each completed round and feedback submission
- invalid lifecycle transitions return explicit conflict-style errors

## 21. Security and Privacy Notes

Minimum requirements:

- no arbitrary file path input from the frontend
- input validation on all API endpoints
- critique text treated as user data
- exports must not leak server-local paths
- session isolation may be added later if multi-user support appears

## 22. Operational Constraints

The v1 system should assume:

- local or single-node execution
- manual operator oversight
- limited concurrency
- reproducibility prioritized over throughput

## 23. Suggested Project Structure

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
    system_specification.md
```

## 24. Minimal Viable Research Prototype

### 24.1 Mandatory capabilities

- Stable Diffusion or SDXL backend through Diffusers
- low-dimensional steering mode
- one interactive session page
- one replay page
- at least three samplers
- at least three feedback modes
- at least three updaters
- fixed-per-round seed mode
- export support
- deterministic replay support

### 24.2 Optional v1 extensions

- critique-conditioned updates
- Bayesian preference model
- multi-seed validation mode
- quality-diversity archive
- study report generation

## 25. Implementation Deliverables

An implementation generated from this specification should produce:

1. a Python FastAPI backend
2. a simple HTML/CSS/JS frontend
3. modular sampler interfaces
4. modular updater interfaces
5. a working diffusion wrapper
6. persistence and export support
7. a test suite aligned with the test specification
8. local setup documentation

## 26. Summary

This system is a controlled research platform for interactive user-guided image generation through prompt-embedding steering.

Its architectural priorities are:

- modular experimentation
- durable state
- replayability
- controlled randomness
- low implementation complexity consistent with research use
