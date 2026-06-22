# Evidence Inventory

## Verified core system claims

### Claim: the repository contains a working interactive image-generation system

Status:

- verified

Evidence:

- [app/main.py](E:\Projects\StableSteering\app\main.py)
- [app/engine/orchestrator.py](E:\Projects\StableSteering\app\engine\orchestrator.py)
- [app/frontend/templates/setup.html](E:\Projects\StableSteering\app\frontend\templates\setup.html)
- [app/frontend/templates/session.html](E:\Projects\StableSteering\app\frontend\templates\session.html)
- [app/frontend/templates/replay.html](E:\Projects\StableSteering\app\frontend\templates\replay.html)

Notes:

- The system supports session creation, round generation, feedback submission, replay export, diagnostics, and HTML trace reporting.

### Claim: the default runtime uses a real GPU-backed Diffusers backend

Status:

- verified

Evidence:

- [app/engine/generation.py](E:\Projects\StableSteering\app\engine\generation.py)
- [app/core/config.py](E:\Projects\StableSteering\app\core\config.py)
- [tests/test_generation_engine.py](E:\Projects\StableSteering\tests\test_generation_engine.py)
- [tests/test_runtime_policy.py](E:\Projects\StableSteering\tests\test_runtime_policy.py)

Notes:

- The system is explicitly designed to refuse silent fallback from the real backend.

### Claim: session-level YAML configuration changes runtime behavior

Status:

- verified

Evidence:

- [app/core/config_yaml.py](E:\Projects\StableSteering\app\core\config_yaml.py)
- [app/core/schema.py](E:\Projects\StableSteering\app\core\schema.py)
- [app/engine/generation.py](E:\Projects\StableSteering\app\engine\generation.py)
- [tests/test_config_yaml.py](E:\Projects\StableSteering\tests\test_config_yaml.py)
- [tests/test_session_lifecycle.py](E:\Projects\StableSteering\tests\test_session_lifecycle.py)

Notes:

- Runtime-relevant parameters include sampler, updater, feedback mode, seed policy, steering mode, steering dimension, candidate count, image size, trust radius, anchor strength, guidance scale, inference steps, and model name.

### Claim: the system supports multiple samplers, update rules, and feedback modes

Status:

- verified

Evidence:

- [app/samplers/random_local.py](E:\Projects\StableSteering\app\samplers\random_local.py)
- [app/samplers/axis_sweep.py](E:\Projects\StableSteering\app\samplers\axis_sweep.py)
- [app/samplers/exploit_orthogonal.py](E:\Projects\StableSteering\app\samplers\exploit_orthogonal.py)
- [app/samplers/incumbent_mix.py](E:\Projects\StableSteering\app\samplers\incumbent_mix.py)
- [app/samplers/uncertainty.py](E:\Projects\StableSteering\app\samplers\uncertainty.py)
- [app/updaters/winner_copy.py](E:\Projects\StableSteering\app\updaters\winner_copy.py)
- [app/updaters/winner_average.py](E:\Projects\StableSteering\app\updaters\winner_average.py)
- [app/updaters/linear_pref.py](E:\Projects\StableSteering\app\updaters\linear_pref.py)
- [app/feedback/normalization.py](E:\Projects\StableSteering\app\feedback\normalization.py)

### Claim: the repository contains a real example run with preserved artifacts

Status:

- verified

Evidence:

- [output/examples/real_e2e_example_run/manifest.json](E:\Projects\StableSteering\output\examples\real_e2e_example_run\manifest.json)
- [output/examples/real_e2e_example_run/real_e2e_example_run.html](E:\Projects\StableSteering\output\examples\real_e2e_example_run\real_e2e_example_run.html)
- [output/examples/real_e2e_example_run/session_trace_report.html](E:\Projects\StableSteering\output\examples\real_e2e_example_run\session_trace_report.html)

Observed facts from the current manifest:

- `round_count = 5`
- `candidate_count = 25`
- `backend = diffusers`
- `configured_device = cuda`
- `active_device = cuda`
- `failing_image_count = 0`

### Claim: the codebase has meaningful automated verification

Status:

- verified

Evidence:

- [tests/README.md](E:\Projects\StableSteering\tests\README.md)
- [tests/test_feedback.py](E:\Projects\StableSteering\tests\test_feedback.py)
- [tests/test_generation_engine.py](E:\Projects\StableSteering\tests\test_generation_engine.py)
- [tests/test_jobs.py](E:\Projects\StableSteering\tests\test_jobs.py)
- [tests/test_session_lifecycle.py](E:\Projects\StableSteering\tests\test_session_lifecycle.py)
- [tests/test_tracing.py](E:\Projects\StableSteering\tests\test_tracing.py)
- [tests/e2e/app.spec.js](E:\Projects\StableSteering\tests\e2e\app.spec.js)
- [tests/e2e/real_backend.spec.js](E:\Projects\StableSteering\tests\e2e\real_backend.spec.js)

Current verification snapshot used while preparing this paper folder:

- `python -m pytest -q` -> `64 passed`
- `npm run test:e2e:chrome` -> `8 passed`, `1 skipped`

## Partially supported claims

### Claim: the system is a research platform for human-in-the-loop steering

Status:

- partially verified

What is supported:

- infrastructure for sessions, feedback, replay, diagnostics, and trace capture

What is missing:

- formal study protocol
- aggregate session corpus
- paper-ready analysis pipeline

Evidence:

- [docs/system_specification.md](E:\Projects\StableSteering\docs\system_specification.md)
- [docs/research_improvement_roadmap.md](E:\Projects\StableSteering\docs\research_improvement_roadmap.md)

### Claim: the steering loop improves outcomes over rounds

Status:

- partially verified

What is supported:

- one curated real example run

What is missing:

- benchmark prompts
- repeated seeds
- aggregate metrics

Evidence:

- [scripts/create_real_e2e_example.py](E:\Projects\StableSteering\scripts\create_real_e2e_example.py)
- [output/examples/real_e2e_example_run/manifest.json](E:\Projects\StableSteering\output\examples\real_e2e_example_run\manifest.json)

### Claim: one sampler or updater is better than another

Status:

- unverified

Evidence gap:

- no checked-in benchmark matrix or results corpus comparing strategies

## Missing evidence for a stronger paper

- no bibliography or `.bib` file
- no manuscript source before this paper folder
- no benchmark prompt suite
- no analysis notebook
- no structured results corpus beyond one example run
- no baseline comparison table against prompt-only workflows

## Safe claim boundary for the draft

Safe:

- the system is implemented
- the system is configurable
- the system is traceable
- the system is tested
- the system can execute a real multi-round example on GPU

Unsafe:

- the method is superior to prompt rewriting
- the method is user-preferred in general
- any specific sampler or updater is best
