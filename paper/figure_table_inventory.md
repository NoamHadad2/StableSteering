# Figure and Table Inventory

## Figures that can be made now

### Figure 1: system architecture

Purpose:

- explain the replayable steering loop at a glance
- foreground prompt -> candidates -> preferences -> update -> replayable inspection
- make trace and storage outputs visually first-class

Source:

- [docs/assets/illustrations/runtime_flow.svg](E:\Projects\StableSteering\docs\assets\illustrations\runtime_flow.svg)

Paper use:

- Section 3

Caption guidance:

- what it is: workflow/architecture schematic
- what it shows: how the replayable steering loop traverses frontend, orchestrator, generation, storage, and trace layers
- why it matters: makes the systems contribution legible as one loop rather than a list of components

### Figure 2: session lifecycle

Purpose:

- explain baseline, feedback, update, and next-round flow
- make baseline, incumbent carry-forward, and steering-state update explicit

Source:

- [docs/assets/illustrations/session_lifecycle.svg](E:\Projects\StableSteering\docs\assets\illustrations\session_lifecycle.svg)

Paper use:

- Section 3

Caption guidance:

- what it is: lifecycle schematic
- what it shows: baseline round, incumbent carry-forward, normalized feedback, and updater transition
- why it matters: clarifies what changes across rounds

### Figure 3: feedback modes

Purpose:

- summarize supported user preference channels
- clarify that multiple feedback forms are normalized into one updater-facing path

Source:

- [docs/assets/illustrations/feedback_modes.svg](E:\Projects\StableSteering\docs\assets\illustrations\feedback_modes.svg)

Paper use:

- Section 3

Caption guidance:

- what it is: feedback-mode schematic
- what it shows: supported feedback forms and their normalization role in the loop
- why it matters: shows the platform’s interaction modularity without implying comparative evaluation

### Figure 4: qualitative case study

Purpose:

- show baseline prompt candidate, one or two intermediate rounds, and final preferred outcome
- narrate qualitative progression rather than present a montage

Source:

- [output/examples/real_e2e_example_run/real_e2e_example_run.html](E:\Projects\StableSteering\output\examples\real_e2e_example_run\real_e2e_example_run.html)
- [output/examples/real_e2e_example_run/images](E:\Projects\StableSteering\output\examples\real_e2e_example_run\images)

Paper use:

- Section 5

Caption guidance:

- what it is: qualitative case-study figure
- what it shows: round-by-round trajectory, selected winner, and final preferred outcome
- why it matters: demonstrates the replayable steering loop as a qualitative artifact, not a benchmark result

## Tables to keep tight

### Table 1: case-study setup

Purpose:

- give the reader the exact prompt, config, backend, and stopping rule for the curated qualitative case study

Keep it to:

- prompt label
- prompt text
- negative prompt
- model/backend
- sampler
- updater
- feedback mode
- seed policy
- candidate count
- image size
- stopping rule

### Table 2: pilot workflow summary

Purpose:

- compress the executed minimal baseline matrix into one paper-ready comparison table
- make the pilot evidence readable without exposing the raw candidate table in the main text

Source:

- [paper/results/baseline_matrix/tables/baseline_summary.csv](E:\Projects\StableSteering\paper\results\baseline_matrix\tables\baseline_summary.csv)
- [paper/results/baseline_matrix/pilot_table.md](E:\Projects\StableSteering\paper\results\baseline_matrix\pilot_table.md)

Recommended columns:

- baseline label
- run count
- completed runs
- average rounds per run
- average feedback events per run

Interpretation note:

- keep heuristic visual-check counts out of the main paper table
- if mentioned at all, treat them as appendix-style artifact screening only, not human-quality judgment

Caption guidance:

- what it is: a compact pilot comparison summary
- what it shows: the smallest executed comparison across prompt-only manual iteration, no-update random sampling, and the StableSteering default loop
- why it matters: shows the paper now has a real workflow-comparison pilot, but still not a full benchmark

### Table 3: repeat-stability summary

Purpose:

- show that the tiny repeated pilot is stable at the workflow-count level
- make the evidence boundary explicit without pretending to have statistical quality comparisons

Source:

- [paper/results/baseline_matrix/tables/repeat_summary.csv](E:\Projects\StableSteering\paper\results\baseline_matrix\tables\repeat_summary.csv)
- [paper/results/baseline_matrix/seed_robustness.md](E:\Projects\StableSteering\paper\results\baseline_matrix\seed_robustness.md)

Recommended columns:

- prompt label
- baseline label
- seed count
- mean rounds per run
- std rounds per run
- mean feedback events per run
- std feedback events per run

Interpretation note:

- this table supports only workflow-level repeatability claims
- do not use it to imply final-image quality stability or policy superiority

### Figure 5: optional pilot comparison graphic

Purpose:

- only if the paper needs one quick visual cue for the pilot
- keep it tiny and redundant with Table 2

Source:

- [paper/results/baseline_matrix/tables/baseline_summary.csv](E:\Projects\StableSteering\paper\results\baseline_matrix\tables\baseline_summary.csv)

Recommended design:

- one small grouped bar chart for `avg_rounds_per_run`
- annotate `failing_candidate_count` as a subtle secondary label or footnote
- avoid any figure that looks like a claim of statistical strength

Caption guidance:

- what it is: a pilot summary graphic
- what it shows: the bounded 3-prompt x 3-policy comparison at a glance
- why it matters: it is a visual orientation aid, not the primary evidence display

### Figure 6: sampler comparison curve

Purpose:

- compare candidate-sampling strategies under a fixed updater and winner-only oracle
- show whether broader exploratory proposal policies improve target-recovery progress

Source:

- [paper/results/sampler_feedback_comparison/analysis/sampler_slice_curve.svg](E:\Projects\StableSteering\paper\results\sampler_feedback_comparison\analysis\sampler_slice_curve.svg)

Paper use:

- Section 8

Caption guidance:

- what it is: round-by-round oracle target-recovery curve for the sampler slice
- what it shows: `diversity_shell` and `line_search` reaching higher final proxy alignment than older local samplers under matched conditions
- why it matters: shows that the steering loop is sensitive to proposal geometry, not only updater choice

### Figure 7: feedback-model comparison curve

Purpose:

- compare richer preference models against winner-only updates under a fixed sampler
- show whether ratings and rankings can be exploited without changing the outer steering loop

Source:

- [paper/results/sampler_feedback_comparison/analysis/feedback_slice_curve.svg](E:\Projects\StableSteering\paper\results\sampler_feedback_comparison\analysis\feedback_slice_curve.svg)

Paper use:

- Section 8

Caption guidance:

- what it is: round-by-round oracle target-recovery curve for the feedback-model slice
- what it shows: richer feedback models remain competitive, but simple winner-centric updates are still strong under this small proxy study
- why it matters: motivates future work on preference modeling without overstating the present evidence

### Table 4: sampler and feedback proxy summary

Purpose:

- compress the new sampler/feedback comparison into one appendix-ready summary
- keep the main result readable without exposing candidate-level logs

Source:

- [paper/results/sampler_feedback_comparison/tables/policy_summary.csv](E:\Projects\StableSteering\paper\results\sampler_feedback_comparison\tables\policy_summary.csv)

Recommended columns:

- slice
- policy label
- sampler
- updater
- feedback mode
- mean baseline score
- mean final best score
- mean improvement

Interpretation note:

- treat this as a small controlled proxy study in CLIP space
- do not turn the ordering into a universal claim about preferred samplers or human-facing preference interfaces
