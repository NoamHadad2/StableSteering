# Reader Confusion Notes

## Highest-risk confusion points

### 1. “Low-dimensional steering state” is still too abstract

Likely reviewer question:

- What exactly is being modified, and how does `z` relate to the text-conditioning representation?

Fix:

- define `z` as the session’s low-dimensional steering state early in the paper
- explain that the paper treats it as an implementation control state over prompt conditioning, not a proved-optimal representation

### 2. Platform contribution versus method contribution is blurry

Likely reviewer question:

- Are you presenting a new algorithm, or a system for testing several algorithms?

Fix:

- add an explicit “Contribution and Scope” section near the front
- include explicit non-contributions

### 3. The qualitative example setup is under-specified

Likely reviewer question:

- What exact prompt, config, sampler, updater, and stopping rule were used?

Fix:

- summarize the checked-in example run setup in the case-study section
- link to [manifest.json](E:\Projects\StableSteering\output\examples\real_e2e_example_run\manifest.json)

### 4. “Interactive steering” invites an unspoken baseline question

Likely reviewer question:

- Compared to what?

Fix:

- preemptively state that this paper does not yet claim superiority over prompt-only baselines

### 5. Verification language can be misread as scientific validation

Likely reviewer question:

- Are software tests being used as evidence of research effectiveness?

Fix:

- separate software verification from research validation explicitly

### 6. “Multiple strategies” can sound like “evaluated strategies”

Likely reviewer question:

- Were these strategies compared, or merely implemented?

Fix:

- say “implements interchangeable modules” rather than implying completed comparison

## Resolved in the current draft revision

- the first page now states explicitly that the paper is a systems-platform paper rather than a benchmark paper
- the steering state is defined earlier as a session-level control abstraction
- the qualitative case study now includes a compact setup description
- verification wording is now separated more clearly from research validation
