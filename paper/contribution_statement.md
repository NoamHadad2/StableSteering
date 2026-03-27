# Contribution Statement

## Recommended contribution framing

StableSteering should be presented as a traceable platform intended to support research on interactive preference-guided diffusion refinement, not as a completed empirical methods paper.

## Canonical paper identity

Use one canonical label throughout the paper package:

- `traceable platform`

Use these only as secondary descriptors when needed:

- `workflow-comparison pilot`
- `qualitative case study`
- `steering state z`

## Singular thesis

The paper should keep one central message throughout: StableSteering contributes a runnable, GPU-backed, replayable platform that organizes image generation around a repeated prompt-to-candidates-to-preferences-to-update loop. It should not drift into claiming a new best steering algorithm.

## Strongest defensible contribution bullets

1. StableSteering is a runnable, prompt-first platform for iterative preference-guided diffusion image generation with explicit session, round, and candidate state.
Evidence:
- [app/main.py](E:\Projects\StableSteering\app\main.py)
- [app/engine/orchestrator.py](E:\Projects\StableSteering\app\engine\orchestrator.py)
- [app/core/schema.py](E:\Projects\StableSteering\app\core\schema.py)

2. The system preserves replay, diagnostics, backend/frontend traces, and session artifacts well enough to support post-hoc audit and reproducibility-oriented analysis.
Evidence:
- [app/core/tracing.py](E:\Projects\StableSteering\app\core\tracing.py)
- [output/examples/real_e2e_example_run/session_trace_report.html](E:\Projects\StableSteering\output\examples\real_e2e_example_run\session_trace_report.html)
- [output/examples/real_e2e_example_run/manifest.json](E:\Projects\StableSteering\output\examples\real_e2e_example_run\manifest.json)

3. The repository supports interchangeable samplers, update rules, feedback modes, seed policies, and per-session YAML configuration under one common lifecycle.
Evidence:
- [app/core/schema.py](E:\Projects\StableSteering\app\core\schema.py)
- [app/samplers](E:\Projects\StableSteering\app\samplers)
- [app/updaters](E:\Projects\StableSteering\app\updaters)
- [app/core/config_yaml.py](E:\Projects\StableSteering\app\core\config_yaml.py)

4. The runtime is implemented against a real GPU-backed Diffusers path rather than a mock-only prototype, and the repo includes a checked-in qualitative multi-round case study.
Evidence:
- [app/engine/generation.py](E:\Projects\StableSteering\app\engine\generation.py)
- [output/examples/real_e2e_example_run/real_e2e_example_run.html](E:\Projects\StableSteering\output\examples\real_e2e_example_run\real_e2e_example_run.html)

5. The system contribution is backed by substantial backend and browser verification.
Evidence:
- [tests/test_session_lifecycle.py](E:\Projects\StableSteering\tests\test_session_lifecycle.py)
- [tests/test_generation_engine.py](E:\Projects\StableSteering\tests\test_generation_engine.py)
- [tests/e2e/app.spec.js](E:\Projects\StableSteering\tests\e2e\app.spec.js)

## Engineering but not novelty

- FastAPI service wiring, frontend pages, async jobs, SQLite persistence, and GitHub Pages publication are engineering quality, not core novelty by themselves.
- Rich diagnostics, trace HTML reports, and session-resume UX strengthen artifact value and reproducibility, but should not be sold as the main scientific contribution.
- The presence of many sampler and updater variants is engineering breadth unless the paper compares them systematically.

## Explicit non-contributions

- This paper does not establish that StableSteering outperforms prompt-only iteration or no-update baselines.
- This paper does not claim that any implemented sampler or updater is empirically superior.
- This paper does not present a formal human-subjects study or general usability conclusion.
- This paper does not claim state-of-the-art image quality.
- This paper does not offer a literature-backed novelty proof over all prior interactive generative systems yet.

## Recommended contribution paragraph

StableSteering contributes a traceable platform intended to support future controlled studies of interactive preference-guided refinement of diffusion image generation. The repository implements a prompt-first workflow in which a session maintains an explicit steering state, generates candidate images over multiple rounds, collects structured user feedback, updates the incumbent state, and preserves replay, diagnostics, and trace artifacts for later inspection. The present contribution is therefore best framed as a real, GPU-backed platform with a checked-in qualitative multi-round case study and a bounded workflow-comparison pilot, rather than as a completed empirical demonstration that one steering algorithm outperforms prompt-only alternatives.
