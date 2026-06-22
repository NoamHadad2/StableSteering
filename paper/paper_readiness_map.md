# Paper Readiness Map

## Recommended paper type

Best current fit:

- system/demo paper for an interactive diffusion-steering platform
- workshop paper for a configurable preference-guided image refinement testbed

Weak fit today:

- full empirical methods paper claiming one sampler or updater is superior
- formal HCI paper with user-study conclusions

## One-paragraph thesis

StableSteering is a prompt-first, human-in-the-loop image-generation platform that lets a user iteratively refine diffusion outputs by selecting among candidate images, recording structured preference feedback, and updating a session-level steering state across rounds. The repository already contains a real GPU-backed Diffusers runtime, replay export, trace capture, session diagnostics, multiple sampler and updater implementations, and a checked-in real example session. The strongest current paper story is therefore a systems and research-platform contribution: a configurable, traceable environment intended to support future controlled studies of interactive steering, rather than a completed empirical claim that a particular steering algorithm outperforms prompt-only alternatives.

## Candidate titles

- StableSteering: A Traceable Platform for Interactive Preference-Guided Diffusion Steering
- StableSteering: A Research Testbed for Human-in-the-Loop Diffusion Image Refinement
- StableSteering: Replayable Interactive Steering for Diffusion Image Generation

## What the repository clearly supports

- A working FastAPI application with prompt-first setup, session resume, replay, diagnostics, and trace reporting.
- Real GPU-backed Diffusers inference by default, with explicit refusal instead of silent fallback when runtime requirements are not met.
- Configurable session-level YAML that changes runtime behavior.
- Multiple samplers, multiple update rules, multiple feedback modes, and multiple seed policies.
- A checked-in qualitative example session with 5 rounds, 25 candidates, and image sanity checks.
- Automated backend and browser tests.

## What is only partially supported

- The repository supports the infrastructure for research on human-in-the-loop steering, but not yet the dataset and analysis needed for strong research conclusions.
- The repository demonstrates that multiple samplers and update rules are implemented, but not that one is quantitatively superior.
- The repository demonstrates one strong curated example run, but not corpus-level generalization.

## What is missing before a stronger paper

- A benchmark prompt suite.
- Baselines against prompt-only iteration and no-update sampling.
- Aggregate experiment tables and figures.
- Broader related-work coverage and a fuller citation-backed comparison to adjacent interactive systems.
- Analysis-ready exports or notebooks for paper figures.
- Formal study protocol and success criteria.

## Suggested narrative

Use the paper to argue:

1. interactive prompt rewriting is awkward for local refinement
2. a session-level steering loop is a practical alternative control surface
3. StableSteering contributes a traceable platform for testing that idea
4. the current repository validates the platform implementation, not final scientific superiority

## Best evidence anchors

- System architecture and workflow:
  - [app/main.py](E:\Projects\StableSteering\app\main.py)
  - [app/engine/orchestrator.py](E:\Projects\StableSteering\app\engine\orchestrator.py)
  - [docs/system_specification.md](E:\Projects\StableSteering\docs\system_specification.md)
- Runtime and generation behavior:
  - [app/engine/generation.py](E:\Projects\StableSteering\app\engine\generation.py)
  - [app/core/schema.py](E:\Projects\StableSteering\app\core\schema.py)
  - [app/core/config_yaml.py](E:\Projects\StableSteering\app\core\config_yaml.py)
- Observability and replay:
  - [app/core/tracing.py](E:\Projects\StableSteering\app\core\tracing.py)
  - [output/examples/real_e2e_example_run/real_e2e_example_run.html](E:\Projects\StableSteering\output\examples\real_e2e_example_run\real_e2e_example_run.html)
  - [output/examples/real_e2e_example_run/session_trace_report.html](E:\Projects\StableSteering\output\examples\real_e2e_example_run\session_trace_report.html)
- Verification:
  - [tests/test_session_lifecycle.py](E:\Projects\StableSteering\tests\test_session_lifecycle.py)
  - [tests/test_generation_engine.py](E:\Projects\StableSteering\tests\test_generation_engine.py)
  - [tests/e2e/app.spec.js](E:\Projects\StableSteering\tests\e2e\app.spec.js)

## Bottom line

The repository is paper-ready as a platform paper scaffold, not yet paper-ready as a claim-heavy comparative research paper.
