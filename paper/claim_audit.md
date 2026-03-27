# Claim Audit

## Verified claims to use in the paper

1. StableSteering implements a prompt-first interactive diffusion-steering workflow.
Evidence:
- [README.md](E:\Projects\StableSteering\README.md)
- [app/main.py](E:\Projects\StableSteering\app\main.py)

2. Sessions preserve configuration, rounds, candidates, replay state, and trace history.
Evidence:
- [app/core/schema.py](E:\Projects\StableSteering\app\core\schema.py)
- [app/storage/repository.py](E:\Projects\StableSteering\app\storage\repository.py)
- [app/core/tracing.py](E:\Projects\StableSteering\app\core\tracing.py)

3. The runtime supports a real GPU-backed Diffusers backend and records diagnostics.
Evidence:
- [app/engine/generation.py](E:\Projects\StableSteering\app\engine\generation.py)
- [app/frontend/templates/diagnostics.html](E:\Projects\StableSteering\app\frontend\templates\diagnostics.html)
- [tests/test_runtime_policy.py](E:\Projects\StableSteering\tests\test_runtime_policy.py)

4. The system supports multiple interchangeable sampler, updater, feedback, and seed-policy modules.
Evidence:
- [app/core/schema.py](E:\Projects\StableSteering\app\core\schema.py)
- [app/samplers](E:\Projects\StableSteering\app\samplers)
- [app/updaters](E:\Projects\StableSteering\app\updaters)

5. A real multi-round example bundle is checked into the repo.
Evidence:
- [output/examples/real_e2e_example_run/manifest.json](E:\Projects\StableSteering\output\examples\real_e2e_example_run\manifest.json)

## Claims that need careful wording

1. “Preference-guided steering improves image quality.”
Use instead:
- “the repository demonstrates an implemented preference-guided steering loop and a qualitative multi-round example”

2. “StableSteering is more controllable than prompt rewriting.”
Use instead:
- “StableSteering is designed to support controlled comparisons against prompt-only baselines, but those comparisons are not yet fully populated in the repository”

3. “The sampler family balances exploration and exploitation effectively.”
Use instead:
- “the repository implements multiple sampling policies intended to cover different exploration and exploitation behaviors”

4. “The system learns an accurate user reward model.”
Use instead:
- “the system normalizes user feedback and updates an internal steering state using interchangeable update rules”

## Claims to avoid

- any quantitative superiority statement
- any user-study conclusion
- any strong novelty statement relative to external literature without citations
- any state-of-the-art claim

## Recommended framing sentence

This paper presents StableSteering as a configurable and traceable platform for studying interactive preference-guided refinement of diffusion image generation, and uses the current implementation plus a real example session to illustrate the system design and workflow.
