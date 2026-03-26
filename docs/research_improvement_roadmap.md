# Research Improvement Roadmap

## 1. Purpose

This document tracks the highest-value research improvements for StableSteering as a study platform.

It focuses on:

- research design
- experimental validity
- evaluation quality
- interpretability
- study operations
- comparative baselines

It does not focus on core engineering execution. That belongs in:

- [system_improvement_roadmap.md](system_improvement_roadmap.md)

## 2. Current Research Baseline

The current system already supports:

- iterative steering sessions
- multiple samplers and updaters
- multiple feedback modes at the schema level
- deterministic test paths
- replay and trace capture
- real GPU-backed image generation

This is enough for exploratory pilot work, but not yet enough for strong claims about algorithm quality, usability, or scientific validity.

## 3. Main Research Gaps

The largest current gaps are:

- limited comparative baselines
- limited human-study instrumentation
- no formal study protocols in the repo
- limited analysis automation
- weak coverage of confounds like seed sensitivity and user inconsistency

## 4. Priority Levels

- `R0`
  Needed before making strong research claims.

- `R1`
  Strongly improves study quality and interpretability.

- `R2`
  Valuable expansions once the core research loop is stable.

## 5. R0: Research Validity Priorities

### 5.1 Establish a baseline comparison matrix

Why it matters:

- steering only matters scientifically if it beats simpler alternatives
- without baselines, improvements can be mistaken for ordinary prompt iteration or random luck

Implementation notes:

- define a minimum comparison set:
  - prompt rewriting only
  - prompt-only manual iteration without steering state
  - no-update random sampling
  - updater comparisons such as winner-copy, winner-average, and linear-preference
- lock the task set and evaluation rules before collecting data
- require every new strategy claim to include at least one baseline comparison

Success signal:

- every reported result can be compared against a non-steering or weaker-steering baseline

### 5.2 Add explicit study protocols

Why it matters:

- informal operator habits create hidden study drift
- protocols turn one-off demos into repeatable experiments

Implementation notes:

- define pilot-study templates with prompt selection rules, stopping criteria, and operator instructions
- version the protocol documents alongside the code
- standardize how prompts, negative prompts, configuration presets, and success criteria are recorded
- separate exploratory studies from claim-bearing studies in documentation and reporting

Success signal:

- two different operators can run the same study and produce comparable artifacts

### 5.3 Improve confound logging

Why it matters:

- seed effects, fatigue, UI bias, and interruptions can dominate outcomes if they are not measured
- better logging makes null or mixed results more interpretable

Implementation notes:

- log hidden repeats for agreement checks
- add user confidence and decision time fields where appropriate
- log interruptions, retries, abandonment, and mid-session config changes
- distinguish runtime failures from preference uncertainty in analysis exports

Success signal:

- a disappointing or surprising session can be explained in terms of recorded confounds rather than guesswork

### 5.4 Define research success criteria

Why it matters:

- qualitative enthusiasm is useful for exploration but too weak for evaluating methods
- explicit criteria make it possible to stop, compare, and reject hypotheses honestly

Implementation notes:

- define expected effect sizes or directional improvements for key tasks
- define acceptable operator burden and session length
- add replay-based success checks such as incumbent improvement rate and convergence stability
- specify robustness thresholds across alternate seeds and repeated runs

Success signal:

- the team can say clearly when a strategy is better, worse, or inconclusive

## 6. R1: Better Measurement and Analysis

### 6.1 Add stronger outcome metrics

Why it matters:

- raw win counts are not enough to explain why a strategy helped or failed
- richer metrics reveal speed, stability, and user burden tradeoffs

Implementation notes:

- compute incumbent win rate, rounds-to-satisfaction, preference consistency, and seed robustness
- collect user-reported controllability and fatigue
- separate outcome quality metrics from interaction-cost metrics
- report uncertainty and sample counts together with aggregate values

Success signal:

- strategy comparisons show both effectiveness and operator cost

### 6.2 Build analysis-ready exports

Why it matters:

- analysis should not begin with manual cleaning of raw session files
- structured exports reduce friction for notebooks, dashboards, and papers

Implementation notes:

- export tidy CSV or parquet tables for candidates, feedback events, rounds, and sessions
- include join keys and session metadata in each table
- preserve references to replay bundles and trace reports
- version the export schema and document it clearly

Success signal:

- a researcher can load a session corpus into a notebook with minimal preprocessing

### 6.3 Add notebook-based analysis templates

Why it matters:

- reusable notebooks turn collected traces into repeatable analysis rather than one-off custom scripts

Implementation notes:

- create starter notebooks for trajectory analysis, seed robustness, sampler comparisons, and updater comparisons
- make notebooks read the official export schema rather than private ad hoc data layouts
- include plots for round progression, incumbent lineage, and preference stability
- keep example notebooks small enough to run on a local workstation

Success signal:

- the same notebooks can be rerun across new study cohorts without structural edits

### 6.4 Strengthen replay as a research asset

Why it matters:

- replay is already one of the most information-dense artifacts in the project
- it should support comparative analysis, not only debugging

Implementation notes:

- derive structured summaries from replay automatically
- compute change-over-round plots and candidate-lineage views
- highlight baseline prompt images, incumbent carry-forward steps, and final winners
- support side-by-side replay comparisons across strategies or prompts

Success signal:

- replay becomes a first-class analysis surface, not just a development convenience

## 7. R1: Better Human Interaction Research

### 7.1 Move beyond rating-only interaction

Why it matters:

- different preference interfaces capture different kinds of user intent
- pairwise, top-k, winner-only, and approve/reject modes may produce very different noise and speed profiles

Implementation notes:

- run controlled comparisons of rating, pairwise, top-k, winner-only, and approve/reject flows
- measure speed, confidence, consistency, and subjective burden for each mode
- separate interface effects from updater effects in analysis
- align frontend instrumentation with the true interaction type rather than rating-derived shortcuts

Success signal:

- the project can justify when one feedback mode is preferable to another

### 7.2 Evaluate user consistency and fatigue

Why it matters:

- user preference data is only valuable if it remains stable enough to interpret
- long sessions may degrade data quality even if users continue to participate

Implementation notes:

- add hidden repeat judgments and calibration rounds
- measure round count versus confidence, time-to-decision, and critique quality
- look for fatigue patterns such as faster but less consistent later-round judgments
- test whether some feedback modes resist fatigue better than others

Success signal:

- session length recommendations are based on observed behavior rather than guesswork

### 7.3 Study interface bias

Why it matters:

- layout, ordering, and displayed metadata can shift user choices independently of the underlying model behavior
- UI bias can easily be mistaken for algorithmic improvement

Implementation notes:

- randomize candidate order in controlled experiments
- compare metadata-hidden versus metadata-visible variants
- compare different grid densities and spacing
- test whether richer replay context changes future judgments

Success signal:

- the influence of interface design on measured outcomes is quantified rather than ignored

## 8. R1: Synthetic Data Research Direction

### 8.1 Build realistic synthetic steering trajectories toward an anchor

Why it matters:

- real user studies are expensive, slow, and noisy
- anchor-seeking synthetic users can stress-test algorithms under known hidden targets

Implementation notes:

- define anchor types such as latent steering anchors, reference images, attribute vectors, and text-derived targets
- build a synthetic user model that prefers candidates closer to the anchor while still showing uncertainty and bounded inconsistency
- model near ties, occasional reversals, fatigue-like noise, and critique text aligned with choices
- compare synthetic trajectories against real traces on round count, winner stability, and path geometry

Success signal:

- synthetic anchor-seeking sessions look structurally similar to real steering sessions and support meaningful ablations

### 8.2 Build diversity-oriented synthetic sampling around one or more steered locations

Why it matters:

- users often want controlled variation around a good region, not only convergence to one hidden optimum
- diversity-seeking synthetic tasks open a richer class of evaluation problems

Implementation notes:

- define one-center diversity tasks that preserve core concept while varying composition, lighting, pose, or background
- define multi-center tasks where preference rewards both desirability and coverage
- formalize diversity objectives using center distance, inter-candidate distance, coverage, and duplicate avoidance
- test policies such as shortlist preference, winner-plus-diversity bonus, and coverage-seeking ranking

Success signal:

- diversity-seeking synthetic trajectories are clearly distinguishable from pure anchor-seeking trajectories

### 8.3 Use synthetic data to pretrain and stress-test steering algorithms

Why it matters:

- synthetic corpora can accelerate algorithm iteration before expensive human studies
- controlled hidden targets make failure analysis much easier

Implementation notes:

- generate corpora with known hidden targets and varied difficulty settings
- use those corpora for regression testing of samplers, updaters, and feedback interpreters
- build challenge sets containing misleading local optima, seed-sensitive candidates, near ties, and quality-diversity tradeoffs
- compare sim-to-real transfer by tuning on synthetic traces and evaluating on later human sessions

Success signal:

- synthetic data reduces wasted human-study cycles and catches weak strategies earlier

### 8.4 Treat synthetic-user realism itself as a research problem

Why it matters:

- a poor simulator can bias the whole research program
- realism should be measured and improved, not assumed

Implementation notes:

- define realism metrics across win/loss structure, rating distributions, critique patterns, stop-time distributions, and path geometry
- fit simulator parameters to match observed human behavior more closely
- compare multiple simulator families rather than searching for one universal synthetic user
- document which simulator simplifications are believed to be harmless and which remain risky

Success signal:

- synthetic-user realism can be discussed and improved with evidence, not intuition alone

### 8.5 Extend steering research to richer diffusion workflows

Why it matters:

- many practical workflows use reference images, masks, or structural controls rather than only text prompts
- a steering method that works only for plain text-to-image may not generalize to real creative work

Implementation notes:

- study image-prompt, image-variation, inpainting, and ControlNet-guided steering as distinct task families
- compare whether the same preference-update logic transfers across those workflows
- define pipeline-specific metrics such as structure adherence, local edit faithfulness, and reference-image faithfulness
- study cross-workflow transfer, including whether synthetic-user models calibrated in one workflow transfer to another

Success signal:

- the research program can say where iterative steering helps most across diffusion workflow families

## 9. R2: Strategy Research Expansions

### 9.1 Add richer steering representations

Why it matters:

- low-dimensional steering is interpretable and simple, but it may be too limited for some tasks

Implementation notes:

- compare low-dimensional steering against token-level, pooled-embedding, and hybrid representations
- measure whether richer representations improve controllability or only add instability
- preserve interpretability metrics while expanding representation capacity

Success signal:

- representation changes are justified by measurable gains rather than novelty alone

### 9.2 Add stronger samplers

Why it matters:

- sampler quality strongly shapes the candidate set a user can choose from
- better samplers may improve both convergence and exploration efficiency

Implementation notes:

- compare current samplers with Thompson-style, quality-diversity, critique-conditioned, and adaptive trust-region methods
- evaluate both human-judged quality and synthetic benchmark performance
- test whether some samplers pair better with specific feedback modes or update rules

Success signal:

- sampler comparisons reveal clear tradeoffs in exploration, stability, and user burden

### 9.3 Add stronger updaters

Why it matters:

- the update rule determines how user judgments become steering-state movement
- weak updaters can waste high-quality feedback

Implementation notes:

- compare current simple updaters with Bradley-Terry, Bayesian preference, contextual bandit, and critique-aware approaches
- evaluate update sensitivity, robustness to noisy feedback, and stability over multiple rounds
- test how updater choice interacts with sampler choice and feedback modality

Success signal:

- updater research produces concrete guidance on which feedback-to-state mapping works best under which conditions

## 10. Study Program Milestones

### Milestone R-A: Pilot Validity

- establish baseline comparison tasks
- define prompt set
- define study protocol
- log confounds more explicitly

### Milestone R-B: Reliable Measurement

- add stronger metrics
- add analysis exports
- add notebooks and replay summaries
- build first realistic anchor-seeking synthetic-user pipeline
- build first diversity-seeking synthetic-user pipeline

### Milestone R-C: Comparative Research

- compare samplers
- compare updaters
- compare feedback modalities
- compare representation strategies
- compare synthetic-user regimes against real-user outcomes
- compare steering behavior across text-to-image, image-prompt, inpainting, and ControlNet workflows

## 11. Suggested Execution Order

1. define the baseline comparison matrix
2. define pilot protocols and prompt/task sets
3. improve confound logging
4. define explicit research success criteria
5. build analysis-ready exports
6. create notebook-based analysis templates
7. strengthen replay as an analysis asset
8. compare feedback modalities with real users
9. evaluate consistency, fatigue, and interface bias
10. define anchor-seeking synthetic-user tasks
11. define diversity-seeking synthetic-user tasks
12. build synthetic stress-test corpora
13. evaluate synthetic-user realism
14. extend studies to image-prompt, inpainting, and ControlNet workflows
15. compare richer representations, samplers, and updaters

## 12. Summary

The next research phase should shift from “can the system run?” to “can the system support credible conclusions?”

That means focusing on:

- better baselines
- better measurement
- better confound control
- better analysis workflows
- better human-study structure
- realistic synthetic-user generation
- diversity-aware synthetic data regimes
- research coverage beyond text-only generation into richer diffusion pipeline families
