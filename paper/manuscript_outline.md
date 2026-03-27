# Manuscript Outline

## Preferred title

StableSteering: A Traceable Platform for Interactive Preference-Guided Diffusion Steering

## Argument shape

This paper should read as:

1. prompt-only local refinement is awkward
2. StableSteering contributes a configurable, traceable platform for studying an alternative loop
3. the main loop is prompt -> candidates -> preferences -> update -> replay
4. the platform is real, runnable, and observable on a GPU-backed backend
5. a checked-in multi-round case study shows what the platform enables
5. the contribution is the platform and workflow, not a completed benchmark claim

## Recommended section order

1. Introduction
2. Contribution and Scope
3. Related Work and Positioning
4. StableSteering Platform and Core Loop
5. Implementation and Observability
6. Qualitative Case Study: One Real End-to-End Session
7. Verification and Reproducibility
8. Discussion and Limitations
9. Conclusion and Future Work

## Section-by-section purpose

### 1. Introduction

Goals:

- motivate the difficulty of prompt-only local refinement
- explain why preference-guided iteration is worth supporting
- preview the platform contribution

Primary evidence:

- [docs/motivation.md](E:\Projects\StableSteering\docs\motivation.md)
- [README.md](E:\Projects\StableSteering\README.md)

### 2. Related Work and Positioning

Goals:

- position the work cautiously and early
- explain what kind of paper this is before the system details begin
- avoid unsupported novelty or "first" language

Primary evidence:

- [paper/related_work_draft.md](E:\Projects\StableSteering\paper\related_work_draft.md)
- [paper/references.bib](E:\Projects\StableSteering\paper\references.bib)

### 3. StableSteering Platform and Core Loop

Goals:

- explain the prompt-first workflow
- introduce frontend, orchestration, generation, storage, tracing, and replay
- define session state `z`
- explain baseline prompt candidate and incumbent carry-forward
- explain candidate proposal, feedback normalization, and updates

Primary evidence:

- [docs/system_specification.md](E:\Projects\StableSteering\docs\system_specification.md)
- [docs/assets/illustrations/runtime_flow.svg](E:\Projects\StableSteering\docs\assets\illustrations\runtime_flow.svg)
- [app/main.py](E:\Projects\StableSteering\app\main.py)
- [app/core/schema.py](E:\Projects\StableSteering\app\core\schema.py)
- [app/engine/orchestrator.py](E:\Projects\StableSteering\app\engine\orchestrator.py)
- [docs/assets/illustrations/session_lifecycle.svg](E:\Projects\StableSteering\docs\assets\illustrations\session_lifecycle.svg)

### 4. Implementation and Observability

Goals:

- explain FastAPI, SQLite, async jobs, diagnostics, tracing, replay, and per-session YAML
- make implementation choices serve the paper's credibility argument rather than feel like a repo tour

Primary evidence:

- [app/main.py](E:\Projects\StableSteering\app\main.py)
- [app/storage/repository.py](E:\Projects\StableSteering\app\storage\repository.py)
- [app/core/jobs.py](E:\Projects\StableSteering\app\core\jobs.py)
- [app/core/tracing.py](E:\Projects\StableSteering\app\core\tracing.py)
- [docs/configuration_manual.md](E:\Projects\StableSteering\docs\configuration_manual.md)

### 5. Qualitative Case Study: One Real End-to-End Session

Goals:

- make the checked-in example run the central proof-of-value section
- show prompt, configuration, rounds, stopping rule, and preserved artifacts
- foreground that this is one curated qualitative case study

Primary evidence:

- [scripts/create_real_e2e_example.py](E:\Projects\StableSteering\scripts\create_real_e2e_example.py)
- [output/examples/real_e2e_example_run/manifest.json](E:\Projects\StableSteering\output\examples\real_e2e_example_run\manifest.json)
- [output/examples/real_e2e_example_run/real_e2e_example_run.html](E:\Projects\StableSteering\output\examples\real_e2e_example_run\real_e2e_example_run.html)

### 6. Verification and Reproducibility

Goals:

- separate software verification from research validation
- summarize backend tests, browser tests, and runtime policy checks
- keep test success framed as local verification, not algorithmic evidence

Primary evidence:

- [tests/test_session_lifecycle.py](E:\Projects\StableSteering\tests\test_session_lifecycle.py)
- [tests/test_generation_engine.py](E:\Projects\StableSteering\tests\test_generation_engine.py)
- [tests/e2e/app.spec.js](E:\Projects\StableSteering\tests\e2e\app.spec.js)
- [docs/system_test_specification.md](E:\Projects\StableSteering\docs\system_test_specification.md)

### 7. Discussion and Limitations

Goals:

- state the three strongest evidence boundaries
- keep the qualitative-case-study framing explicit
- list the main threats to interpretation and generalization

Primary evidence:

- [paper/claim_evidence_matrix.md](E:\Projects\StableSteering\paper\claim_evidence_matrix.md)
- [docs/research_improvement_roadmap.md](E:\Projects\StableSteering\docs\research_improvement_roadmap.md)

### 8. Conclusion and Future Work

Goals:

- restate the platform contribution cleanly
- define the next evidence-building steps

Primary evidence:

- [paper/experiment_matrix.md](E:\Projects\StableSteering\paper\experiment_matrix.md)
- [docs/system_improvement_roadmap.md](E:\Projects\StableSteering\docs\system_improvement_roadmap.md)
- [docs/research_improvement_roadmap.md](E:\Projects\StableSteering\docs\research_improvement_roadmap.md)
