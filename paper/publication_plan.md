# Publication Plan

## Target venue profile

Most credible near-term targets:

- workshop papers on generative AI tooling or human-in-the-loop generation
- demo/system tracks
- artifact-oriented submissions

Less credible right now:

- full conference methods paper with strong comparative claims

## Proposed submission package

### Core submission content

- manuscript draft grounded in implemented system behavior
- one architecture figure
- one session lifecycle figure
- one qualitative case-study figure from the checked-in example run
- one table summarizing system capabilities
- one table explicitly listing current limitations and planned evaluation

### Supplementary material

- checked-in sample bundle:
  - [real_e2e_example_run.html](E:\Projects\StableSteering\output\examples\real_e2e_example_run\real_e2e_example_run.html)
  - [session_trace_report.html](E:\Projects\StableSteering\output\examples\real_e2e_example_run\session_trace_report.html)
  - [manifest.json](E:\Projects\StableSteering\output\examples\real_e2e_example_run\manifest.json)
- docs site
- repository README

## Immediate pre-submission tasks

1. Add a small benchmark matrix with at least prompt-only and no-update baselines.
2. Create a reproducible prompt suite and fixed evaluation protocol.
3. Add one analysis notebook or export script for paper-ready summary tables.
4. Draft related work and bibliography.
5. Turn the manuscript draft into a venue-specific format.

## Recommended contribution statement

The primary contribution is a reusable, configurable, replayable system for studying interactive steering in diffusion image generation under explicit preference feedback, with real GPU-backed execution and strong observability.
