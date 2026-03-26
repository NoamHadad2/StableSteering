# Pre-Implementation Blueprint

## 1. Document Role

This document translates the research-oriented specification into an implementation-ready build plan. It exists to reduce ambiguity before coding begins.

Implementation note:

- the repository now includes a working MVP
- this blueprint remains useful as the intended design baseline and gap-analysis reference

It focuses on:

- what must be fixed before implementation
- what v1 should contain
- what boundaries must remain clean
- what delivery order will reduce rework

Related documents:

- [motivation.md](/E:/Projects/StableSteering/docs/motivation.md)
- [system_specification.md](/E:/Projects/StableSteering/docs/system_specification.md)
- [system_test_specification.md](/E:/Projects/StableSteering/docs/system_test_specification.md)

## 2. Implementation Principles

The first implementation should optimize for:

- research usefulness over production polish
- reproducibility over raw throughput
- modularity over premature abstraction
- debuggability over hidden automation
- clear data contracts over convenience shortcuts

## 3. v1 Scope

### 3.1 In scope

- one local-user research workflow
- one FastAPI backend
- one simple HTML frontend
- one Stable Diffusion or SDXL wrapper via Diffusers
- one persistent store for experiments, sessions, rounds, and feedback
- one replay and export workflow
- low-dimensional steering mode
- fixed-per-round seed mode
- three samplers
- three feedback modes
- three updaters

### 3.2 Out of scope

- multi-user collaboration
- cloud-scale operations
- production authentication
- distributed job scheduling
- model fine-tuning
- advanced GPU optimization
- enterprise security controls

## 4. Assumptions to Lock Early

The project should proceed with these default assumptions unless deliberately changed:

- single-machine execution
- one active interactive session at a time in v1
- JSON-backed local persistence for the current MVP, with SQLite or PostgreSQL still a plausible next step
- filesystem storage for images and exports
- replay correctness is higher priority than generation speed
- prompts and critique text are stored as research data
- mock generation is available for tests
- the normal app runtime uses real GPU-backed Diffusers inference
- trace logging is a first-class debugging and auditability feature

## 5. Decisions That Should Be Fixed Before Coding

### 5.1 Default model baseline

Options:

- Stable Diffusion 1.5 or similar lightweight baseline
- SDXL baseline

Recommendation:

- start with the lighter baseline to reduce development and test friction

### 5.2 Default steering basis

Options:

- random orthonormal basis
- PCA basis
- prompt-difference basis

Recommendation:

- start with random orthonormal basis for simplicity and deterministic validation

### 5.3 Default feedback mode

Options:

- scalar rating
- pairwise comparison
- top-k ranking

Recommendation:

- start with scalar rating for the simplest complete end-to-end flow

### 5.4 Default updater

Options:

- winner-copy
- winner-average
- linear preference updater

Recommendation:

- start with winner-average as the reference behavior

## 6. System Boundaries

### 6.1 Frontend boundary

Frontend responsibilities:

- collect prompt and configuration
- request round generation
- display candidates and metadata
- collect feedback
- show session progress and errors

Frontend non-responsibilities:

- preference inference
- steering calculations
- persistence rules
- replay reconstruction logic

### 6.2 Backend boundary

Backend responsibilities:

- prompt encoding
- steering state management
- candidate generation
- image rendering
- feedback normalization
- preference update logic
- persistence
- replay and export

### 6.3 Storage boundary

Storage must persist:

- experiment configs
- session state
- rounds
- candidates
- feedback events
- generated image paths
- trace event logs
- exports and manifests

Storage should avoid:

- arbitrary temporary tensors unless they are explicitly required for replay

## 7. Stable Contracts to Define Before Coding

### 7.1 Session contract

Every session state should contain:

- session ID
- experiment configuration snapshot
- prompt and negative prompt
- basis configuration
- current steering state
- current round index
- incumbent reference
- status

### 7.2 Candidate contract

Every candidate should contain:

- candidate ID
- round ID
- steering vector
- seed
- sampler role
- generation parameters
- image location
- predicted score if available
- predicted uncertainty if available
- render status

### 7.3 Feedback contract

Every normalized feedback object should contain:

- feedback type
- involved candidate IDs
- ordered preference information if derivable
- raw payload
- optional critique text
- timestamp

### 7.4 Replay contract

Every replay export should contain enough information to reconstruct:

- experiment configuration
- session setup
- round order
- candidate metadata
- image references
- feedback events
- updater outputs

## 8. Delivery Order

Implementation should proceed in this order:

1. define schemas and configuration models
2. implement persistence and repositories
3. implement prompt encoding and steering basis logic
4. implement sampler interface and one baseline sampler
5. implement generation wrapper
6. implement orchestration
7. implement feedback normalization
8. implement updater interface and one baseline updater
9. expose API endpoints
10. build the minimal frontend
11. add replay and export
12. add remaining strategies
13. harden deterministic replay

## 9. Minimal API Decisions

These rules should be fixed before coding:

- all write endpoints return persisted identifiers
- round-generation responses include candidate metadata and image references
- feedback submission returns updated incumbent state and summary
- errors return structured codes and readable messages
- session configuration snapshots are immutable after creation

## 10. Non-Functional Requirements

### 10.1 Reproducibility

The system must:

- persist full config snapshots
- persist seeds for all candidates
- version strategy implementations
- support deterministic replay with a controlled backend

### 10.2 Debuggability

The system must:

- log round lifecycle events
- log request-level backend traces
- capture frontend interaction traces
- log per-candidate generation failures
- preserve raw feedback payloads
- allow inspection of session state from storage

### 10.3 Modularity

The system must:

- allow sampler swapping by configuration
- allow updater swapping by configuration
- keep generation logic separate from orchestration logic

## 11. Design Risks to Address Early

### 11.1 Hidden coupling

Risk:

- sampler, updater, and persistence logic become entangled

Mitigation:

- define interfaces early and centralize orchestration

### 11.2 Replay drift

Risk:

- missing config or seed data breaks replay trust

Mitigation:

- treat replay metadata as first-class persisted state

### 11.3 Generation cost

Risk:

- development slows dramatically if every test requires real generation

Mitigation:

- define a mock generator from day one

### 11.4 UI overreach

Risk:

- supporting every mode too early makes the frontend brittle

Mitigation:

- build one simple, switchable feedback component first

## 12. Definition of Implementation Readiness

The project is ready to implement when:

- the baseline model is fixed
- the baseline steering basis is fixed
- the baseline sampler, feedback, and updater set is fixed
- the API payload schemas are agreed
- the persistence model is agreed
- replay requirements are agreed
- acceptance criteria are accepted from the test specification

## 13. Delivery Milestones

Recommended milestones:

1. schema and storage foundation
2. single-round generation path
3. full session lifecycle
4. replay and export
5. logging, tracing, and diagnostics hardening
6. strategy plug-in expansion
7. test hardening and polish

## 14. Summary

This blueprint is the engineering handoff document. It exists to ensure that implementation starts from fixed assumptions, explicit contracts, and a realistic v1 boundary rather than from a broad but underspecified research description.
