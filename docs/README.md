# Documentation Guide

This folder contains the specification set for the StableSteering research platform.

Published HTML version:

- [GitHub Pages Docs](https://apartsinprojects.github.io/StableSteering/)

The current repository also includes a runnable prototype. The most implementation-specific documents are:

- [quick_start.md](quick_start.md)
- [configuration_manual.md](configuration_manual.md)
- [student_tutorial.md](student_tutorial.md)
- [user_guide.md](user_guide.md)
- [developer_guide.md](developer_guide.md)
- [faq.md](faq.md)
- [system_improvement_roadmap.md](system_improvement_roadmap.md)
- [research_improvement_roadmap.md](research_improvement_roadmap.md)

Current implementation highlights reflected in these guides:

- GPU-only real Diffusers runtime by default
- prompt-first setup with editable per-session YAML configuration
- async round-generation and feedback jobs with visible progress
- SQLite-backed local persistence
- backend-saved per-session HTML trace reports
- real GPU-backed end-to-end example bundle under `output/examples/real_e2e_example_run/`
- Gemini-generated conceptual illustration assets plus precise SVG diagrams in the published HTML docs

## Core Documents

- [motivation.md](motivation.md)
  Explains the research problem, value, goals, non-goals, and success criteria.

- [theoretical_background.md](theoretical_background.md)
  Explains the theory behind diffusion conditioning, embedding steering, and preference learning.

- [system_specification.md](system_specification.md)
  Defines the functional system behavior, architecture, contracts, APIs, and constraints.

- [system_test_specification.md](system_test_specification.md)
  Defines the verification contract, replay guarantees, and acceptance criteria.

- [pre_implementation_blueprint.md](pre_implementation_blueprint.md)
  Converts the specification set into an implementation-ready plan with defaults, scope, and milestones.

- [student_tutorial.md](student_tutorial.md)
  Provides a student-oriented walkthrough from motivation and theory to the implementation structure and learning exercises.

- [assets/illustrations/steering_loop.png](assets/illustrations/steering_loop.png)
  Gemini-generated conceptual illustration of the steering loop.

- [assets/illustrations/system_architecture.png](assets/illustrations/system_architecture.png)
  Gemini-generated conceptual illustration of the main system layers.

- [assets/illustrations/trace_report.png](assets/illustrations/trace_report.png)
  Gemini-generated conceptual illustration of the saved HTML session trace report.

- [assets/illustrations/runtime_flow.svg](assets/illustrations/runtime_flow.svg)
  Precise SVG diagram of the main runtime architecture from frontend to generation, storage, and trace reporting.

- [assets/illustrations/session_lifecycle.svg](assets/illustrations/session_lifecycle.svg)
  Precise SVG diagram of the prompt-first session lifecycle, including async jobs and incumbent carry-forward.

- [assets/illustrations/feedback_modes.svg](assets/illustrations/feedback_modes.svg)
  Precise SVG diagram of the supported feedback modes and the signal each one sends to the backend.

- [assets/illustrations/config_to_generation.svg](assets/illustrations/config_to_generation.svg)
  Precise SVG diagram of how per-session YAML becomes a validated config snapshot and affects runtime behavior.

- [quick_start.md](quick_start.md)
  Gives the shortest path to installing, running, and trying the prototype.

- [configuration_manual.md](configuration_manual.md)
  Explains the per-session YAML configuration flow, parameter meanings, validation rules, and practical editing patterns.

- [user_guide.md](user_guide.md)
  Explains the current app from the perspective of a user running sessions.

- [developer_guide.md](developer_guide.md)
  Explains the code layout, extension points, and local development workflow.

- [faq.md](faq.md)
  Answers common questions about the prototype and its current limitations.

- [system_improvement_roadmap.md](system_improvement_roadmap.md)
  Tracks engineering, UX, observability, performance, and release priorities for the system itself.

- [research_improvement_roadmap.md](research_improvement_roadmap.md)
  Tracks study design, baselines, measurement, and analysis priorities for the research program.

## Supporting Documents

- [document_audit.md](document_audit.md)
  Records the top 30 improvements applied to each main document.

- [system_spec_legacy_combined.md](system_spec_legacy_combined.md)
  Preserves the original combined system specification as an archival source.

## Suggested Reading Order

1. [motivation.md](motivation.md)
2. [student_tutorial.md](student_tutorial.md)
3. [theoretical_background.md](theoretical_background.md)
4. [system_specification.md](system_specification.md)
5. [system_test_specification.md](system_test_specification.md)
6. [pre_implementation_blueprint.md](pre_implementation_blueprint.md)
7. [quick_start.md](quick_start.md)
8. [configuration_manual.md](configuration_manual.md)
9. [system_improvement_roadmap.md](system_improvement_roadmap.md)
10. [research_improvement_roadmap.md](research_improvement_roadmap.md)
