# System Improvement Roadmap

## 1. Purpose

This document tracks the highest-value engineering and product improvements for the StableSteering system itself.

It focuses on:

- runtime reliability
- user experience
- observability
- performance
- maintainability
- release and deployment quality

It does not focus on research questions or study design. Those belong in:

- [research_improvement_roadmap.md](research_improvement_roadmap.md)

## 2. Current Baseline

The current MVP already includes:

- a FastAPI backend
- a real GPU-backed Diffusers runtime by default
- SQLite-backed local persistence
- async round generation and feedback jobs
- replay export
- runtime diagnostics
- backend and frontend tracing
- per-session HTML trace reports
- browser and backend test coverage
- GitHub Pages documentation publishing

The next phase is not about making the system merely functional. It is about making it faster to trust, easier to extend, and safer to operate in real research workflows.

## 3. Priority Levels

- `P0`
  Important to system trust, correctness, or operator safety.

- `P1`
  Important to day-to-day usability and research throughput.

- `P2`
  Valuable polish, scale, or long-term maintainability work.

## 4. P0: Near-Term System Priorities

### 4.1 Strengthen real-backend end-to-end coverage

Why it matters:

- the system now depends on real GPU inference in production
- some failures only appear under real model latency, memory pressure, or asset loading
- a research system is hard to trust if only the mock path is thoroughly exercised

Implementation notes:

- expand the opt-in real Playwright suite from diagnostics into a full prompt -> round -> feedback -> next round flow
- persist the generated browser and trace artifacts for failed real-backend runs
- add a lightweight release-gating checklist that explicitly includes one real GPU browser pass
- capture timing and failure metadata so regressions can be compared across releases

Success signal:

- at least one repeatable real-backend browser smoke passes on a CUDA machine before release

### 4.2 Add export packaging for session trace bundles

Why it matters:

- one session currently spans images, replay data, traces, and HTML reports across several files
- researchers need a single portable artifact for archiving, sharing, and citation

Implementation notes:

- add a session export script or endpoint that creates a zip bundle
- include `report.html`, replay JSON, trace JSONL, image artifacts, and a manifest
- record schema version, export time, app version, and checksums in the manifest
- normalize exported paths to be relative so bundles remain portable across machines

Success signal:

- one exported zip can be unpacked on another machine and viewed without broken links

### 4.3 Improve runtime diagnostics depth

Why it matters:

- operators need immediate proof that the app is using the intended GPU-backed runtime
- environment drift is one of the fastest ways to waste debugging time

Implementation notes:

- extend diagnostics with GPU adapter name, VRAM totals, current device, torch version, diffusers version, and transformers version
- show model path, pipeline warm state, and current backend mode on both the diagnostics page and session page
- log a structured startup diagnostics snapshot into the trace bundle
- distinguish clearly between configured device, requested device, and active device

Success signal:

- a user can answer “what model and device is this run using?” from the UI without inspecting code

### 4.4 Harden trace and export path hygiene

Why it matters:

- reports should be easy to move and publish without leaking workstation-specific absolute paths
- brittle path handling causes broken HTML bundles and weakens reproducibility

Implementation notes:

- continue replacing machine-local absolute paths in user-facing exports with relative bundle paths
- define which files are portable artifacts and which are local-runtime metadata
- add a portability check that validates copied reports still render images correctly after relocation
- keep internal diagnostics verbose in raw logs while keeping HTML reports cleaner and more shareable

Success signal:

- exported HTML trace bundles render correctly after being copied to a different folder or machine

## 5. P1: Workflow and UX Improvements

### 5.1 Build true mode-specific feedback controls

Why it matters:

- the backend supports several preference modes, but the UI still routes most interaction through rating-derived shortcuts
- this hides the real strengths and weaknesses of pairwise, ranking, and approve/reject interaction styles

Implementation notes:

- build dedicated controls for pairwise, top-k, winner-only, and approve/reject modes
- keep scalar ratings as the fast general-purpose mode
- make the selected feedback mode visually obvious before the user starts judging candidates
- update trace reports so they show the actual interaction type, not only the normalized payload

Success signal:

- the frontend expresses each feedback mode directly rather than inferring it from generic star ratings

### 5.2 Improve replay and trace navigation

Why it matters:

- replay, diagnostics, and trace reports are now valuable assets, but they still feel like separate islands
- users need to move across those views quickly when auditing a session

Implementation notes:

- add cross-links between replay, diagnostics, and trace report pages
- add per-round anchors and a compact round index
- show badges for incumbent, baseline prompt, carried-forward winners, and final selected candidates
- make image lineage and candidate provenance easier to scan

Success signal:

- a user can move from a winning candidate to its previous-round context in one or two clicks

### 5.3 Add richer async job visibility

Why it matters:

- “running” is not detailed enough once real inference latency becomes noticeable
- users should know whether the system is warming the model, generating images, or applying feedback

Implementation notes:

- split async job progress into finer milestones such as queued, loading pipeline, generating candidates, saving artifacts, normalizing feedback, and updating state
- persist these milestones in backend traces and expose them through the jobs API
- show operation-specific progress text and timestamps in the frontend
- if timing history is available, estimate remaining duration conservatively

Success signal:

- long operations communicate phase-level progress rather than a single coarse status

### 5.4 Improve frontend resilience

Why it matters:

- user frustration rises sharply when ratings or critique text are lost during recoverable failures
- full page reloads hide useful state and make latency feel worse than it is

Implementation notes:

- preserve in-progress form state locally until the backend confirms success
- replace broad page refreshes with partial in-page updates where possible
- add clearer retry affordances and recovery messages
- distinguish transient backend failures from validation failures and GPU/runtime failures

Success signal:

- a failed submission does not force the user to re-enter their judgments

### 5.5 Add richer elicitation modes and UI workflows

Why it matters:

- users often want to express shortlist, uncertainty, local dissatisfaction, or critique, not only pick one winner
- richer elicitation workflows can capture more faithful preference signals and make the system useful for a broader set of creative tasks

Implementation notes:

- add shortlist selection and "acceptable set" interaction modes
- add explicit best-versus-incumbent comparisons so one candidate is always evaluated against the current best result
- add critique-assisted forms with structured reason tags such as composition, realism, lighting, color, faithfulness, and artifact severity
- add "cannot decide", "near tie", and confidence controls so ambiguous judgments are not forced into false certainty
- add region-aware UI patterns for future inpainting and image-prompt workflows
- ensure replay, trace, and export layers record the real elicitation workflow, not only the normalized winner payload

Success signal:

- the frontend supports several genuinely different preference-collection workflows with clear semantics and traceability

## 6. P1: Performance Improvements

### 6.1 Reduce repeated pipeline warm-up cost

Why it matters:

- real diffusion pipelines have a noticeable cold-start penalty
- long first-round latency makes the whole system feel slower and less trustworthy

Implementation notes:

- measure cold-start versus warm-run timing explicitly
- preload the pipeline at startup when that does not create unacceptable idle memory cost
- add a manual warm-up action for demo and lab setups
- persist warm-up timing in diagnostics so regressions are easy to spot

Success signal:

- first-round latency is predictable and clearly explained to the operator

### 6.2 Improve database structure for future growth

Why it matters:

- SQLite is a strong step up from flat JSON files, but the current payload-heavy design will become harder to query as the dataset grows
- future analysis tooling will want cleaner round-, candidate-, and feedback-level access

Implementation notes:

- normalize the highest-value query dimensions out of JSON blobs first
- add indexes for the most common lookup paths, especially session, round order, and candidate lineage
- preserve replay export compatibility while changing storage layout
- write migration notes and tests before changing persisted schema

Success signal:

- common session and replay queries remain fast as the local dataset grows

### 6.3 Optimize artifact lifecycle

Why it matters:

- generated images, reports, and traces accumulate quickly in real use
- unclear retention rules create both clutter and accidental data loss risk

Implementation notes:

- add cleanup and retention scripts with dry-run support
- classify artifacts by importance: essential, reproducible, or disposable
- document safe deletion rules for `data/`, `output/`, and exported bundles
- add optional compression for long-term archival bundles

Success signal:

- operators can reclaim disk space confidently without breaking active sessions or published artifacts

### 6.4 Add a synthetic-data generation pipeline

Why it matters:

- algorithm iteration is slow if every evaluation depends on live human steering
- synthetic sessions can provide scalable regression tests, ablations, and pretraining data

Implementation notes:

- add a dedicated synthetic-session generation layer rather than overloading the interactive runtime
- support two core regimes:
  - anchor-seeking trajectories toward a target steer state or reference
  - diversity-seeking trajectories around one or more promising steer locations
- define a stable synthetic schema with prompt, anchor, candidate batch, synthetic preference event, critique text, simulator metadata, and next-state summary
- version simulator behavior independently so old corpora remain interpretable
- emit analysis-ready exports and HTML summaries similar to user trace reports

Success signal:

- synthetic corpora can be generated reproducibly and compared across simulator versions

### 6.5 Expand steering support to more diffusion pipelines

Why it matters:

- prompt-only generation is too narrow for many real creative workflows
- practical steering systems need to work with reference images, local edits, and structural constraints

Implementation notes:

- define a common generation request contract that supports:
  - pure text prompt generation
  - text plus reference image generation
  - text plus mask generation
  - text plus ControlNet conditioning generation
- add adapter implementations for image-prompt, inpainting, and ControlNet workflows
- validate required auxiliary assets per pipeline type
- extend replay, trace reports, and storage conventions so those extra assets are visible and portable
- update the frontend to upload, preview, and persist reference images, masks, and control inputs

Success signal:

- one orchestration layer can drive multiple diffusion workflow families without special-case route logic

### 6.6 Add stronger sampler families

Why it matters:

- the sampler defines which candidate images the user ever gets to judge
- better sampler families may improve convergence speed, diversity, and robustness under noisy or sparse feedback

Implementation notes:

- add contextual bandit and Thompson-style samplers that consume uncertainty estimates explicitly
- add archive-based or quality-diversity samplers that preserve diverse high-value regions rather than only following the incumbent
- add critique-conditioned samplers that use structured user complaints or desired attributes to bias proposals
- add incumbent-versus-challenger samplers that guarantee one stability option and one higher-risk exploratory option in every round
- add adaptive trust-region samplers whose radius expands or contracts based on preference stability and model confidence
- make sampler metadata first-class in traces so proposal behavior is inspectable after the session

Success signal:

- the system can compare several materially different sampler families, not only local heuristic variations

### 6.7 Add stronger preference-model implementations

Why it matters:

- current update logic is intentionally simple, but richer preference models can use ratings, pairwise choices, rankings, approvals, and critiques more effectively
- stronger preference models could improve both learning speed and robustness to inconsistent user judgments

Implementation notes:

- add Bradley-Terry or Plackett-Luce style preference models for pairwise and ranking data
- add Bayesian preference estimators with explicit uncertainty over candidate quality
- add listwise models that use full or partial rankings rather than collapsing them to one winner
- add critique-aware preference models that combine structured reasons with discrete selections
- add incumbent-aware models that distinguish "best in batch" from "better than current best"
- standardize a scorer interface so future samplers can consume posterior scores and uncertainty estimates directly

Success signal:

- the system can switch between heuristic update rules and explicit learned preference models through one stable contract

## 7. P1: Synthetic Data Infrastructure and Tooling

### 7.1 Support anchor-seeking synthetic-user simulation

Why it matters:

- anchor-seeking behavior is the most direct simulation of a user trying to steer toward a desired hidden target
- it creates a clean environment for comparing samplers and updaters

Implementation notes:

- represent anchors as latent states, reference-image embeddings, attribute bundles, or text-derived targets
- define a synthetic scoring interface that compares candidates against the anchor consistently
- add configurable noise models for uncertainty, reversals, fatigue, and near-tie behavior
- emit synthetic rationale fields and optional generated critique text
- calibrate simulator behavior against real traces rather than assuming the simulator is realistic

Success signal:

- anchor-seeking synthetic traces reproduce recognizable patterns seen in real sessions

### 7.2 Support diversity-seeking synthetic-user simulation

Why it matters:

- not every useful user wants convergence to a single target
- many creative tasks reward local novelty and coverage around one or several promising modes

Implementation notes:

- support one-center and multi-center diversity objectives
- compute both quality and coverage metrics for candidate sets
- add diversity-aware preference policies such as shortlist preference and winner-plus-diversity bonus
- record whether the synthetic objective is convergence, neighborhood exploration, or multi-center coverage
- guard against near-duplicate corpora with explicit diversity checks

Success signal:

- synthetic diversity tasks produce trajectories that are measurably different from pure anchor-seeking runs

### 7.3 Add synthetic corpus management

Why it matters:

- synthetic data only becomes useful research infrastructure if it is easy to inspect, version, and subset

Implementation notes:

- define a stable output folder layout and manifest format
- include seeds, simulator version, task family, prompt family, and split assignment
- generate HTML summaries for corpora and individual sessions
- support filtering by anchor type, difficulty, diversity regime, and prompt family
- keep generated corpora separable from ordinary interactive session data

Success signal:

- a synthetic corpus can be reproduced, filtered, and reused without ad hoc cleanup scripts

### 7.4 Add synthetic-data quality checks

Why it matters:

- weak synthetic traces can quietly teach the wrong lessons to algorithms and researchers
- corpus quality must be tested, not assumed

Implementation notes:

- add duplicate detection, diversity thresholds, anchor-distance sanity checks, and preference-consistency checks
- compare synthetic distributions against real session statistics where possible
- generate quality dashboards for each corpus build
- fail corpus generation or mark builds degraded when thresholds are violated

Success signal:

- poor-quality synthetic corpora are detected before they are used for analysis or training

## 8. P2: Architecture and Scale Improvements

### 8.1 Add a pluggable storage layer for shared deployments

Why it matters:

- local SQLite is a good MVP choice, but future hosted or collaborative deployments will need a cleaner storage abstraction

Implementation notes:

- formalize the storage adapter contract around sessions, rounds, feedback, artifacts, and exports
- add contract tests that every backend must pass
- prepare a PostgreSQL-backed implementation without changing route semantics
- preserve replay and trace export compatibility across backends

Success signal:

- the storage backend can change without breaking orchestration or exported artifacts

### 8.2 Improve release automation

Why it matters:

- releases are more trustworthy when packaging, docs generation, and validation are automated
- manual release work is error-prone, especially as the docs site and example bundles grow

Implementation notes:

- automate release zip creation and site generation checks in CI
- verify that committed Pages output matches the current Markdown state
- refresh workflow actions before the upcoming Node runtime changes become disruptive
- add an explicit release checklist artifact for human sign-off

Success signal:

- a release candidate can be validated with one repeatable CI-backed process

### 8.3 Add API schema snapshots

Why it matters:

- contract drift is easy to miss when responses evolve gradually
- snapshots make accidental breaking changes visible early

Implementation notes:

- snapshot JSON API responses for core endpoints
- snapshot replay export payloads and trace-report structure where stable
- keep snapshot tests intentionally narrow around durable fields
- version snapshots when intentional contract changes are made

Success signal:

- meaningful API and export shape changes are deliberate, reviewable, and test-backed

## 9. Milestone View

### Milestone A: Operator Trust

- richer diagnostics
- session trace bundle export
- real-backend browser smoke expansion

### Milestone B: Better Interactive Use

- mode-specific feedback UI
- richer elicitation modes and critique-aware UI
- better async progress states
- improved replay and trace navigation
- first synthetic-data pipeline for anchor-seeking and diversity-seeking corpora
- first multi-pipeline steering support for image prompt, inpainting, and ControlNet workflows
- first advanced sampler family
- first explicit preference-model family beyond winner heuristics

### Milestone C: Hardening and Release Maturity

- stronger CI release automation
- better export portability
- shared-store preparation
- synthetic corpus validation and packaging

## 10. Suggested Execution Order

1. expand real-backend end-to-end validation
2. package session trace bundles for export
3. improve diagnostics depth
4. build mode-specific feedback UI
5. add richer elicitation modes and critique-aware UI
6. refine async progress states
7. improve replay and trace navigation
8. add stronger sampler families
9. add stronger preference-model implementations
10. reduce pipeline warm-up cost
11. normalize high-value SQLite query paths
12. add artifact retention and cleanup tooling
13. add anchor-seeking synthetic-data pipeline
14. add diversity-seeking synthetic-data pipeline
15. build synthetic corpus management and quality checks
16. expand generation contracts for multiple diffusion pipeline types
17. add image-prompt steering support
18. add inpainting steering support
19. add ControlNet steering support
20. harden release automation
21. prepare shared-storage evolution
22. add API schema snapshots

## 11. Summary

The main engineering goal is no longer “make the MVP exist.” That is done.

The next system phase should make StableSteering:

- easier to trust
- easier to inspect
- easier to operate
- easier to extend
- easier to publish and reproduce
- more scalable as a synthetic-data generation platform
- more useful across multiple diffusion conditioning workflows, not only prompt-only generation
