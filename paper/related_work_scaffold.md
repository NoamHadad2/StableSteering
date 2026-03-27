# Related Work Scaffold

## Use policy

This file is a structure and positioning scaffold, not a citation-complete related-work section. Do not turn it into a strong novelty claim until citations are added.

## Theme 1: Interactive control for text-to-image generation

Focus:

- systems that let users iteratively refine outputs rather than rely on one-shot prompting
- interfaces based on prompt editing, prompt suggestions, selection, ranking, or critique

How StableSteering contrasts:

- many interactive systems keep prompt text as the main control surface
- StableSteering instead centers a persistent steering state and multi-round preference loop

Repo evidence supporting this contrast:

- [README.md](E:\Projects\StableSteering\README.md)
- [app/engine/orchestrator.py](E:\Projects\StableSteering\app\engine\orchestrator.py)

Missing literature:

- citations to interactive prompt-editing and co-creative text-to-image systems
- citations distinguishing prompt-rewrite interfaces from latent or embedding-level control

## Theme 2: Preference-guided generation and human-in-the-loop optimization

Focus:

- work that uses ratings, pairwise comparisons, rankings, or critique to guide generation
- preference learning, reward modeling, and online human feedback loops

How StableSteering contrasts:

- the repository is strongest as infrastructure for collecting, replaying, and comparing such signals
- it supports multiple feedback modes and updater variants, but not yet a claim that one strategy is empirically best

Repo evidence:

- [app/core/schema.py](E:\Projects\StableSteering\app\core\schema.py)
- [app/feedback/normalization.py](E:\Projects\StableSteering\app\feedback\normalization.py)
- [app/updaters](E:\Projects\StableSteering\app\updaters)

Missing literature:

- citations for pairwise and scalar preference learning in generative systems
- citations for directly relevant human-feedback optimization work

## Theme 3: Diffusion steering and conditioning control

Focus:

- work on controlling diffusion outputs through conditioning signals, latent directions, semantic edits, or structured steering variables
- prompt-to-embedding conditioning and local steering ideas

How StableSteering contrasts:

- the repository frames prompt embeddings as control objects and uses a low-dimensional steering state `z`
- the current implementation is a platform instantiation of that idea, not yet a validated claim that it is the best representation

Repo evidence:

- [docs/theoretical_background.md](E:\Projects\StableSteering\docs\theoretical_background.md)
- [app/core/schema.py](E:\Projects\StableSteering\app\core\schema.py)
- [app/engine/generation.py](E:\Projects\StableSteering\app\engine\generation.py)

Missing literature:

- citations for diffusion control via latent or embedding edits
- citations for low-dimensional or structured steering directions

## Theme 4: Reproducibility, replay, and observability in generative research systems

Focus:

- systems papers or tooling work emphasizing traceability, replay, diagnostics, artifact packaging, and experiment control

How StableSteering contrasts:

- this is probably the strongest current differentiator in the repo
- the system combines replay, per-session trace bundles, diagnostics, YAML-configured sessions, and a checked-in real example run

Repo evidence:

- [app/core/tracing.py](E:\Projects\StableSteering\app\core\tracing.py)
- [app/frontend/templates/diagnostics.html](E:\Projects\StableSteering\app\frontend\templates\diagnostics.html)
- [output/examples/real_e2e_example_run/manifest.json](E:\Projects\StableSteering\output\examples\real_e2e_example_run\manifest.json)

Missing literature:

- citations for reproducibility and observability tooling in ML systems

## Cautious novelty-positioning paragraph

A defensible novelty claim for the current repository is not that StableSteering has already established a superior steering algorithm, but that it integrates prompt-first session setup, low-dimensional iterative steering state, explicit multi-round preference collection, replayable session history, and strong observability into one runnable research platform for interactive diffusion refinement. Relative to prompt-centric iterative interfaces, the repository is organized around persistent steering-state updates rather than prompt rewriting alone. Relative to generic preference-learning discussions, the current contribution is a concrete, traceable implementation and evaluation scaffold. This positioning should remain cautious until the paper is backed by explicit related-work citations and comparative baseline results.

## Safe wording

- “we present a platform”
- “we instantiate”
- “we organize the workflow around”
- “we aim to support comparison of”

## Unsafe wording

- “we are the first to”
- “we outperform prior interactive systems”
- “our steering formulation is novel” without citations
- “existing work lacks replay or traceability” without literature support
