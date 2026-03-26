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

- [research_improvement_roadmap.md](/E:/Projects/StableSteering/docs/research_improvement_roadmap.md)

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

## 3. Priority Levels

- `P0`
  Important to system trust, correctness, or operator safety.

- `P1`
  Important to day-to-day usability and research throughput.

- `P2`
  Valuable polish, scale, or long-term maintainability work.

## 4. P0: Near-Term System Priorities

### 4.1 Strengthen real-backend end-to-end coverage

Goals:

- add more browser coverage against the real Diffusers backend
- verify at least one full generate-feedback-generate cycle on real GPU hardware
- catch UI or orchestration bugs that only appear with real latency

Suggested work:

- extend the opt-in real Playwright suite beyond diagnostics
- add a release checklist item for the real browser path
- persist real test artifacts for debugging

### 4.2 Add export packaging for session trace bundles

Goals:

- make one session easy to archive, share, or attach to a report
- keep images, replay payloads, trace logs, and `report.html` together

Suggested work:

- add a session export endpoint or script
- produce a zip bundle with stable manifest metadata
- include checksum and schema version info

### 4.3 Improve runtime diagnostics depth

Goals:

- make it obvious that the app is truly using GPU
- reduce time spent debugging environment mismatches

Suggested work:

- show GPU adapter name
- show VRAM totals and current usage if available
- show torch, diffusers, and transformers versions
- show prepared model path and pipeline warm state

### 4.4 Harden trace and export path hygiene

Goals:

- keep local paths readable without leaking unnecessary machine-specific details into exports
- make trace bundles easier to move between machines

Suggested work:

- reduce machine-local absolute paths in user-facing reports
- normalize export manifests around relative paths
- document which files are portable and which are local-runtime only

## 5. P1: Workflow and UX Improvements

### 5.1 Build true mode-specific feedback controls

Current gap:

- the UI uses rating inputs for all feedback modes and derives pairwise and top-k indirectly

Suggested work:

- add dedicated pairwise widgets
- add explicit ranking controls for top-k
- preserve a rating-only fast path for quick testing

### 5.2 Improve replay and trace navigation

Goals:

- reduce friction when reviewing a completed session
- connect replay, diagnostics, and trace reports more clearly

Suggested work:

- add navigation between replay and trace sections
- add per-round anchors
- add summary badges for winning candidates and user critique

### 5.3 Add richer async job visibility

Goals:

- make long-running work easier to interpret
- distinguish queueing, model warm-up, image generation, and feedback application phases

Suggested work:

- refine `status_message`
- add operation-specific milestones
- surface estimated duration when possible

### 5.4 Improve frontend resilience

Goals:

- preserve user work during recoverable failures
- reduce unnecessary page reloads

Suggested work:

- preserve unsent ratings locally until success
- replace full refreshes with selective in-page updates
- add clearer retry affordances

## 6. P1: Performance Improvements

### 6.1 Reduce repeated pipeline warm-up cost

Goals:

- improve first-round latency
- reduce perceived slowness during interactive use

Suggested work:

- preload pipeline on startup when appropriate
- add explicit warm-up action or startup hook
- report cold-start vs warm-run timing

### 6.2 Improve database structure for future growth

Current state:

- structured state is already in SQLite, but some values remain stored as JSON payloads

Suggested work:

- normalize the highest-value query fields further
- add indexes based on observed query patterns
- prepare migration notes for a future shared store

### 6.3 Optimize artifact lifecycle

Goals:

- avoid clutter from old runs
- keep storage growth understandable

Suggested work:

- add retention and cleanup scripts
- document safe deletion more clearly
- add optional artifact compression for exported bundles

### 6.4 Add a synthetic-data generation pipeline

Goals:

- support large-scale offline algorithm evaluation
- generate reproducible synthetic steering sessions
- make synthetic datasets realistic enough to be useful for training and benchmarking

Detailed roadmap items:

- add a dataset-generation script or service layer for synthetic sessions
- support two primary synthetic regimes:
  - anchor-seeking trajectories toward a target steer state or reference
  - diversity-seeking trajectories around one or more steered locations
- define a stable synthetic-session schema with:
  - prompt
  - anchor definition
  - candidate set
  - synthetic preference event
  - critique text if generated
  - next-state summary
  - simulator metadata
- persist synthetic run manifests separately from ordinary interactive sessions
- version the simulator policy independently from the rest of the app
- generate analysis-ready exports for each synthetic corpus

### 6.5 Expand steering support to more diffusion pipelines

Goals:

- move beyond text-to-image-only steering
- make the system useful for more realistic creative workflows
- support conditioning modes that practitioners already use in production

Detailed roadmap items:

- add a pipeline adapter layer so orchestration can target multiple diffusion workflows through one stable contract
- support image-prompt or image-variation steering where the user starts from a reference image and refines around it
- support inpainting steering where the user edits only a masked region while preserving the surrounding composition
- support ControlNet-guided steering for structure-aware workflows such as edge, depth, pose, or segmentation control
- persist pipeline-specific inputs in session state and replay exports, including:
  - reference images
  - masks
  - ControlNet conditioning assets
  - pipeline-specific generation settings
- extend diagnostics so the active pipeline type is visible during runtime
- extend trace reports so they clearly show which conditioning mode each round used
- add storage conventions for auxiliary assets used by non-text-only pipelines

Implementation tasks:

- define a generation request schema that can represent:
  - pure text prompt generation
  - text plus reference image generation
  - text plus mask generation
  - text plus ControlNet conditioning generation
- add adapter implementations for:
  - image prompt or image variation pipeline
  - inpainting pipeline
  - one or more ControlNet pipelines
- add validation rules for required assets per pipeline type
- add frontend affordances for uploading and previewing reference images, masks, and control inputs
- add replay rendering support for these extra conditioning artifacts
- add test fixtures for each pipeline family

## 7. P1: Synthetic Data Infrastructure and Tooling

### 7.1 Support anchor-seeking synthetic-user simulation

System requirements:

- represent an anchor as one or more of:
  - latent steering vector
  - reference image embedding
  - attribute target bundle
  - text-derived target state
- compute candidate-to-anchor scores consistently
- allow configurable synthetic-user noise models
- emit round-by-round decisions and rationale fields

Implementation tasks:

- add anchor-definition models
- add synthetic scorer interfaces
- add pluggable decision policies for ratings, pairwise outcomes, and rankings
- add critique-template or critique-generation hooks
- add calibration tools to compare synthetic traces with real traces

### 7.2 Support diversity-seeking synthetic-user simulation

System requirements:

- support one-center local diversity sampling
- support multi-center diversity sampling
- compute both quality and coverage scores
- prevent synthetic corpora from collapsing into near-duplicates

Implementation tasks:

- add local-neighborhood samplers around one steered location
- add multi-center batch construction around several promising locations
- add diversity metrics to candidate manifests
- add coverage-aware synthetic preference policies
- record whether the synthetic objective was:
  - converge-to-anchor
  - explore-around-anchor
  - cover-multiple-centers

### 7.3 Add synthetic corpus management

Goals:

- make synthetic datasets inspectable, versioned, and reproducible

Implementation tasks:

- define output folder layout for generated corpora
- add manifest files with seeds, simulator version, and task family
- add HTML summaries for synthetic runs similar to user trace reports
- add train/validation/test split support for synthetic corpora
- add filtering by prompt family, anchor type, and diversity regime

### 7.4 Add synthetic-data quality checks

Goals:

- avoid training on unrealistic or degenerate synthetic traces

Implementation tasks:

- add duplicate-detection checks
- add candidate-diversity threshold checks
- add anchor-distance sanity checks
- add synthetic preference consistency checks
- add comparison dashboards against real session statistics

## 8. P2: Architecture and Scale Improvements

### 7.1 Add a pluggable storage layer for shared deployments

Goals:

- support multi-user or hosted research workflows later

Suggested work:

- define a storage adapter contract explicitly
- prepare PostgreSQL-backed implementation
- preserve replay export compatibility

### 7.2 Improve release automation

Goals:

- make releases more repeatable
- reduce manual mistakes

Suggested work:

- automate release zip creation in CI
- validate docs-site generation in CI
- update workflow actions for upcoming Node 24 runtime changes

### 7.3 Add API schema snapshots

Goals:

- make contract drift more visible

Suggested work:

- snapshot structured API responses
- snapshot replay export schema
- snapshot trace-report structure where stable

## 9. Milestone View

### Milestone A: Operator Trust

- richer diagnostics
- session trace bundle export
- real-backend browser smoke expansion

### Milestone B: Better Interactive Use

- mode-specific feedback UI
- better async progress states
- improved replay and trace navigation
- first synthetic-data pipeline for anchor-seeking and diversity-seeking corpora
- first multi-pipeline steering support for image prompt, inpainting, and ControlNet workflows

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
5. refine async progress states
6. expand generation contracts for multiple diffusion pipeline types
7. add image-prompt steering support
8. add inpainting steering support
9. add ControlNet steering support
10. add anchor-seeking synthetic-data pipeline
11. add diversity-seeking synthetic-data pipeline
12. improve replay and trace navigation
13. harden release automation
14. prepare shared-storage evolution

## 11. Summary

The main system goal is no longer “make the MVP exist.” That is done.

The next engineering phase should make the system:

- easier to trust
- easier to inspect
- easier to operate
- easier to extend
- easier to publish and reproduce
- easier to use for realistic synthetic-data generation at scale
- usable across multiple diffusion conditioning workflows, not only prompt-only generation
