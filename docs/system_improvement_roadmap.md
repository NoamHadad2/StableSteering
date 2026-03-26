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

## 7. P2: Architecture and Scale Improvements

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

## 8. Milestone View

### Milestone A: Operator Trust

- richer diagnostics
- session trace bundle export
- real-backend browser smoke expansion

### Milestone B: Better Interactive Use

- mode-specific feedback UI
- better async progress states
- improved replay and trace navigation

### Milestone C: Hardening and Release Maturity

- stronger CI release automation
- better export portability
- shared-store preparation

## 9. Suggested Execution Order

1. expand real-backend end-to-end validation
2. package session trace bundles for export
3. improve diagnostics depth
4. build mode-specific feedback UI
5. refine async progress states
6. improve replay and trace navigation
7. harden release automation
8. prepare shared-storage evolution

## 10. Summary

The main system goal is no longer “make the MVP exist.” That is done.

The next engineering phase should make the system:

- easier to trust
- easier to inspect
- easier to operate
- easier to extend
- easier to publish and reproduce
