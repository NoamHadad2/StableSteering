# Theoretical Background

## 1. Document Role

This document provides the minimum theoretical grounding needed to understand the system design without assuming deep specialization in diffusion modeling.

It explains:

- how text conditioning affects image generation
- why embedding-space steering is plausible
- why low-dimensional control is useful
- why preference learning is the right framing

Related documents:

- [motivation.md](/E:/Projects/StableSteering/docs/motivation.md)
- [system_specification.md](/E:/Projects/StableSteering/docs/system_specification.md)

## 2. Diffusion at a High Level

A text-to-image diffusion model generates an image by starting from noise and iteratively denoising a latent representation while conditioning each step on text-derived features.

A simplified pipeline is:

1. tokenize the prompt
2. encode tokens into text embeddings
3. sample a latent noise tensor
4. iteratively denoise using a conditional U-Net
5. decode the final latent with a VAE

The important design consequence is that the model is conditioned on embeddings, not directly on raw text.

## 3. Why Prompt Rewriting Is Hard

The visible prompt string is discrete, but the model control signal is continuous.

That mismatch matters:

- a tiny wording change can move the conditioning signal in a non-smooth way
- many visual intents do not map cleanly to words
- the same prompt may behave differently under different seeds
- users often discover their intent only after seeing generated outputs

Prompt rewriting remains useful, but it is a blunt control surface for iterative local search.

## 4. Prompt Embeddings as Control Objects

For this project, the prompt-conditioned embedding is treated as the editable object of interest.

A prompt embedding is usually a sequence of token-level vectors rather than one single vector. Practical steering may therefore operate on:

- the full token embedding tensor
- a pooled representation
- a structured low-rank offset
- selected token subsets

This distinction matters because different representations trade off expressiveness, cost, interpretability, and stability.

## 5. Low-Dimensional Steering

Direct search over the full embedding tensor is high-dimensional and unstable. A lower-dimensional steering parameterization gives the system a controllable search space.

One useful formulation is:

- `E0`: the base prompt embedding
- `U`: a basis of steering directions
- `z`: a low-dimensional steering code
- `E(z) = E0 + U z`: the active conditioned embedding

Advantages of searching over `z`:

- fewer degrees of freedom
- easier optimization
- easier uncertainty estimation
- more interpretable trajectories
- simpler comparison between update rules

## 6. Why Local Search Is Reasonable

The system is not attempting unrestricted global optimization over all possible prompts. It is attempting local improvement around a user-provided intent.

That makes local search reasonable because:

- the user already provides a semantic starting point
- nearby movements are more likely to preserve intent
- smaller steps are easier to interpret
- local updates are easier to constrain and replay

The purpose is controlled adaptation, not unconstrained generation.

## 7. Preference Learning Framing

The system is not predicting a ground-truth target image. Instead, it tries to infer a latent user utility function from observed responses.

This is naturally a preference-learning problem.

Common feedback forms include:

- scalar rating
- pairwise preference
- partial ranking
- shortlist selection
- free-text critique

The reward is never directly observed. It must be inferred from noisy, partial, and sometimes inconsistent feedback.

## 8. Exploration and Exploitation

Interactive steering is a sequential decision problem.

- **Exploitation** means sampling near the currently estimated best direction.
- **Exploration** means sampling uncertain or diverse directions that may reveal better outcomes.

A system that only exploits can converge prematurely. A system that only explores may waste user attention.

One research objective of the platform is to compare policies for balancing these pressures under real human feedback.

## 9. Seed Sensitivity

Diffusion generation is stochastic. Two images produced from the same embedding can still differ substantially because of seed variation.

That introduces a core identification problem:

- some quality changes come from embedding movement
- some quality changes come from random seed variation

This is why the system must support:

- same-seed within-round comparisons
- alternate-seed validation
- robustness metrics across seeds

## 10. Trust Regions and Anchoring

Large movements in steering space may drift far from the user's original intent.

Two stabilizers are therefore important:

- **trust region**: limit step size per round
- **anchor penalty**: discourage excessive movement away from the origin `z = 0`

Together they help the system search locally while preserving semantic coherence.

## 11. Multiple Representation and Update Choices

There is no reason to assume one representation or one update rule is universally best.

The platform should compare alternatives such as:

- pooled versus token-level steering
- random versus structured bases
- winner-copy versus averaged updates
- linear versus pairwise probabilistic preference models
- deterministic versus uncertainty-aware updates

This comparative framing is central to the research value of the system.

## 12. Practical Implications for Design

The theoretical framing leads directly to several engineering consequences:

- the system must log seed policy explicitly
- the system must preserve full round trajectories
- the system must support interchangeable samplers and updaters
- the system must track uncertainty where possible
- the system must constrain steering movement

These are not implementation conveniences. They are necessary to make the research claims testable.

## 13. Limits of the Theory

This document does not claim that embedding movement is always semantically smooth or always easier than prompt editing.

Known limitations include:

- entangled latent directions
- non-linear effects in the generator
- instability under different prompts or checkpoints
- user inconsistency in expressed preference

The system exists partly to measure these limits rather than assume them away.

## 14. Summary

The theoretical justification for the project is straightforward: diffusion models consume continuous text-conditioning embeddings, user intent is best modeled through preference feedback, and controlled local search in a low-dimensional steering space provides a plausible way to study interactive steering rigorously.
