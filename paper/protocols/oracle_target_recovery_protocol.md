# Oracle Target-Recovery Protocol

## Goal

Evaluate whether iterative preference-guided steering can move generated images closer to a held-out real target image when the only initialization signal is a manually written caption.

## Task definition

For each target image:

1. Keep the target image hidden from the generator.
2. Start the session from a manually written caption and optional negative prompt.
3. Generate a first round of candidates from the caption.
4. Use an oracle to select the candidate closest to the hidden target image in embedding space.
5. Update the steering state from that oracle feedback.
6. Repeat for a fixed number of rounds.

The resulting study is a target-recovery task, not a human-preference study.

## Oracle definition

The oracle uses cosine similarity between the target image embedding and each candidate image embedding. In the current protocol, the oracle is implemented with CLIP image embeddings.

At round `t`, the oracle chooses:

\[
j_t^\star = \arg\max_j \cos\!\left(\phi(I^\star), \phi(I_t^{(j)})\right),
\]

where `I^\star` is the hidden target image and `\phi` is the frozen embedding model.

## Locked conditions

- backend and model
- image size
- inference steps
- candidate count
- seed policy
- steering dimension
- trust radius
- updater
- sampler
- stopping rule
- oracle embedding model

## Primary outputs

- per-target round table
- per-candidate oracle score table
- target-level summary table
- aggregate convergence summary
- convergence figure
- qualitative contact sheet

## Interpretation boundary

This protocol measures recovery toward a hidden target under an embedding-based oracle. It does not measure human visual quality directly, and it should not be interpreted as a user-study result.
