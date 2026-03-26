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

- [system_improvement_roadmap.md](/E:/Projects/StableSteering/docs/system_improvement_roadmap.md)

## 2. Current Research Baseline

The current system already supports:

- iterative steering sessions
- multiple samplers and updaters
- multiple feedback modes at the schema level
- deterministic test paths
- replay and trace capture
- real GPU-backed image generation

This is enough for exploratory pilot work, but not yet enough for a strong research program.

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

Goals:

- compare steering against simpler alternatives
- avoid overclaiming based on one workflow

Minimum baselines:

- prompt-only rewriting
- prompt-only manual iteration without steering state
- no-update random sampling baseline
- winner-copy vs winner-average vs linear-preference updater comparison

### 5.2 Add explicit study protocols

Goals:

- make experiments repeatable across operators
- reduce ad hoc evaluation drift

Suggested work:

- define pilot study templates
- define prompt set selection rules
- define stopping criteria
- define annotation instructions for operators

### 5.3 Improve confound logging

Goals:

- understand when session outcomes are caused by seed, fatigue, or interface effects rather than the steering method itself

Suggested work:

- log repeated hidden comparisons
- log user confidence
- log time-to-decision
- log interruptions, retries, and session abandonment

### 5.4 Define research success criteria

Goals:

- make it clear when a strategy is actually better
- prevent endless qualitative-only iteration

Suggested work:

- define minimum effect expectations
- define acceptable operator burden
- define replay-based success checks
- define robustness thresholds across seeds

## 6. R1: Better Measurement and Analysis

### 6.1 Add stronger outcome metrics

Suggested metrics:

- incumbent win rate against previous incumbents
- average rounds to satisfaction
- preference consistency over repeated judgments
- robustness under alternate seeds
- user-reported controllability
- user-reported fatigue

### 6.2 Build analysis-ready exports

Goals:

- reduce manual cleanup before analysis
- make traces easier to use in notebooks and reports

Suggested work:

- export tidy CSV or parquet summaries
- create one row per candidate
- create one row per feedback event
- create one row per round
- include experiment/session metadata joins

### 6.3 Add notebook-based analysis templates

Goals:

- make it easy to analyze sessions without rebuilding analysis logic each time

Suggested work:

- session trajectory notebook
- seed robustness notebook
- sampler comparison notebook
- updater comparison notebook

### 6.4 Strengthen replay as a research asset

Goals:

- use replay not just for debugging, but for comparative analysis and auditing

Suggested work:

- derive session summaries automatically
- compute change-over-round plots
- highlight candidate lineage and incumbent transitions
- compare replay trajectories across strategies

## 7. R1: Better Human Interaction Research

### 7.1 Move beyond rating-only interaction

Current gap:

- although the system supports multiple feedback schemas, the current UI still centers ratings

Research opportunity:

- compare rating-based interaction with true pairwise and ranking interactions
- measure cognitive load and speed differences
- measure whether richer critique improves update quality

### 7.2 Evaluate user consistency and fatigue

Goals:

- understand how stable user judgment is across rounds
- understand when the session length starts harming data quality

Suggested work:

- hidden repeat judgments
- forced calibration rounds
- round-count versus confidence tracking
- fatigue self-report prompts

### 7.3 Study interface bias

Goals:

- ensure the UI is not shaping results more than the underlying algorithm

Suggested work:

- randomize candidate order in controlled experiments
- compare metadata-hidden vs metadata-visible views
- compare grid sizes and density
- compare replay-rich vs replay-light workflows

## 8. R1: Synthetic Data Research Direction

### 8.1 Build realistic synthetic steering trajectories toward an anchor

Research motivation:

- real user studies are expensive and noisy
- early-stage algorithm comparison needs more coverage than human evaluation alone can provide
- a synthetic user should not be random preference noise; it should behave like a user steering toward a latent target or anchor

Core question:

- can we generate realistic synthetic steering traces that approximate how a user would move toward a desired visual anchor over multiple rounds?

Target capability:

- define an anchor state, anchor image, or anchor attribute profile
- simulate round-by-round user preferences based on distance to that anchor
- include imperfect but structured behavior rather than perfect oracle choices

Detailed roadmap items:

- define anchor types:
  - latent steering anchor
  - reference image anchor
  - attribute-vector anchor
  - text-derived anchor
- build a synthetic user model that prefers candidates moving closer to the anchor
- inject bounded inconsistency so the synthetic user is realistic rather than omniscient
- model user behaviors such as:
  - near-tie uncertainty
  - occasional reversals
  - fatigue-induced noise
  - critique text consistent with the chosen winner
- compare synthetic trajectories against real user traces to calibrate realism
- study whether synthetic traces preserve:
  - round count distributions
  - winner stability
  - preference consistency
  - typical path shapes in steering space

### 8.2 Build diversity-oriented synthetic sampling around one or more steered locations

Research motivation:

- realistic steering is not only about converging to one target
- many useful workflows involve exploring neighborhoods around one promising location or several distinct promising locations

Core question:

- how should synthetic data generation represent a user who wants diversity around one or more already-steered locations rather than only direct convergence?

Target capability:

- sample diverse candidates around one selected steer location
- sample around multiple local attractors to model ambiguity or multi-modal user intent
- label both quality and diversity utility

Detailed roadmap items:

- define one-center diversity tasks:
  - hold core concept fixed
  - vary composition, lighting, material, pose, or background
  - reward local novelty without collapsing semantic identity
- define multi-center diversity tasks:
  - two or more steered centers
  - user prefers batches covering multiple plausible directions
  - synthetic preference balances desirability and coverage
- formalize diversity objectives:
  - distance from anchor center
  - distance between candidates
  - coverage of local manifold neighborhoods
  - avoidance of trivial duplicates
- test several synthetic preference policies:
  - best-single-sample preference
  - shortlist preference
  - winner-plus-diversity bonus
  - coverage-seeking ranking
- compare whether diversity-seeking synthetic users produce trajectories distinct from pure anchor-seeking users
- measure whether algorithms tuned on one synthetic regime transfer to the other

### 8.3 Use synthetic data to pretrain and stress-test steering algorithms

Goals:

- reduce dependence on scarce human-in-the-loop collection
- identify weak samplers and updaters before real studies
- create large controlled corpora for ablations

Detailed roadmap items:

- generate synthetic session corpora with known hidden targets
- train or tune preference/update components on those corpora
- use synthetic runs for regression testing of strategy changes
- build challenge sets with:
  - misleading local optima
  - seed-sensitive candidates
  - high-similarity near-ties
  - diversity-versus-quality tradeoffs
- measure sim-to-real transfer by comparing behavior tuned on synthetic traces against later human traces

### 8.4 Treat synthetic-user realism itself as a research problem

Research motivation:

- poor synthetic data can mislead the whole program
- the simulator should be evaluated, not assumed

Detailed roadmap items:

- define realism metrics for synthetic traces
- compare synthetic and real sessions on:
  - win/loss structure
  - rating distributions
  - critique patterns
  - stop-time distributions
  - path geometry in steering space
- fit simulator parameters to better match observed human behavior
- study which simulator simplifications are harmless and which bias conclusions
- maintain multiple synthetic-user families instead of one universal simulator

### 8.5 Extend steering research to richer diffusion workflows

Research motivation:

- many real creative workflows do not begin and end with text-only prompting
- user intent is often expressed through images, masks, layout hints, or structural controls
- a steering method that only works for plain text-to-image may be too narrow to matter in practice

Core question:

- does iterative steering remain useful and interpretable when the generation pipeline is conditioned by reference images, masked edits, or explicit structural controls?

Target directions:

- image-prompt or image-variation steering
- inpainting steering
- ControlNet-guided steering

Detailed roadmap items:

- study whether the same preference-update logic transfers across pipeline families or whether each needs its own update geometry
- compare how users steer when the anchor is:
  - a text prompt
  - a reference image
  - a masked region edit target
  - a structural control target such as pose, edge, or depth
- analyze whether preference signals mean different things in different workflows:
  - global style preference in text-to-image
  - local correction preference in inpainting
  - structure-preserving refinement in ControlNet workflows
- build task families for:
  - image-to-image refinement toward a more premium or more faithful result
  - localized defect repair through inpainting
  - structure-constrained exploration using ControlNet inputs
- test whether steering helps users balance faithfulness versus creativity differently in each pipeline type
- study cross-workflow transfer:
  - can a strategy tuned on text-to-image sessions help in inpainting?
  - can a synthetic user model calibrated for image-prompt steering transfer to ControlNet tasks?
- add comparative metrics for pipeline-specific goals, such as:
  - background preservation in inpainting
  - structure adherence in ControlNet
  - content faithfulness to a reference image in image-prompt workflows

## 9. R2: Strategy Research Expansions

### 8.1 Add richer steering representations

Suggested expansions:

- token-level steering
- pooled-embedding steering
- hybrid low-dimensional plus token mask approaches

### 8.2 Add stronger samplers

Suggested expansions:

- Thompson-style sampling
- quality-diversity or archive-based exploration
- critique-conditioned candidate proposals
- adaptive trust-region sampling

### 8.3 Add stronger updaters

Suggested expansions:

- Bradley-Terry style preference updating
- Bayesian preference models
- contextual bandit approaches
- critique-aware updates

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

1. define baseline comparison matrix
2. define pilot protocol and prompt/task sets
3. add stronger confound logging
4. add analysis-ready exports
5. define anchor-seeking synthetic-user tasks
6. define diversity-seeking synthetic-user tasks
7. add replay-based comparative summaries
8. extend task design to image-prompt, inpainting, and ControlNet steering studies
9. compare feedback modalities
10. compare samplers and updaters
11. expand representation strategies

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
