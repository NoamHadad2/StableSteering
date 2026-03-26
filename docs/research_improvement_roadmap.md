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

## 8. R2: Strategy Research Expansions

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

## 9. Study Program Milestones

### Milestone R-A: Pilot Validity

- establish baseline comparison tasks
- define prompt set
- define study protocol
- log confounds more explicitly

### Milestone R-B: Reliable Measurement

- add stronger metrics
- add analysis exports
- add notebooks and replay summaries

### Milestone R-C: Comparative Research

- compare samplers
- compare updaters
- compare feedback modalities
- compare representation strategies

## 10. Suggested Execution Order

1. define baseline comparison matrix
2. define pilot protocol and prompt/task sets
3. add stronger confound logging
4. add analysis-ready exports
5. add replay-based comparative summaries
6. compare feedback modalities
7. compare samplers and updaters
8. expand representation strategies

## 11. Summary

The next research phase should shift from “can the system run?” to “can the system support credible conclusions?”

That means focusing on:

- better baselines
- better measurement
- better confound control
- better analysis workflows
- better human-study structure
