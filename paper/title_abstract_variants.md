# Title and Abstract Variants

## Recommended title and abstract

Use this pair as the default manuscript framing.

## Systems-heavy

### Title

StableSteering: A Traceable Platform for Interactive Preference-Guided Diffusion Steering

### Abstract

StableSteering is a traceable platform for prompt-first, preference-guided multi-round diffusion refinement. It contributes a replayable steering loop in which the system proposes candidate images, records explicit user preferences, updates a steering state, and preserves replay, diagnostics, and trace artifacts for post-hoc inspection. The implementation is GPU-backed and configurable per session, and the repository includes a checked-in qualitative multi-round example session together with local verification of lifecycle behavior. The current paper presents a bounded platform artifact package, not a new steering algorithm or a benchmark showing superiority over prompt-only baselines.

## Alternative framings

These variants are archival options for venue retargeting. They should not redefine the current paper identity unless the manuscript is intentionally repositioned.

## Workshop / demo

### Title

StableSteering: A Demo System for Multi-Round Human-in-the-Loop Diffusion Image Refinement

### Abstract

We present StableSteering, a demonstration system for iterative human-in-the-loop refinement of diffusion-generated images. Instead of relying only on prompt rewriting, the system starts from a user prompt, generates candidate images, collects explicit preference feedback, updates a session-level steering state, and produces the next round. StableSteering includes replay export, diagnostics, backend and frontend tracing, and a real GPU-backed Diffusers runtime. A checked-in five-round example session illustrates the full workflow and preserved artifacts. The demo contribution is a runnable and inspectable platform for interactive steering experiments, with current scope centered on system capability and qualitative case-study evidence rather than comparative performance claims.

## Research-platform

### Title

StableSteering: A Research Testbed for Preference-Guided Interactive Diffusion Refinement

### Abstract

StableSteering is a research testbed for studying interactive preference-guided refinement in diffusion image generation. The system couples a prompt-first interface with configurable sampling, feedback, update, and seed policies, while preserving session replay, trace reports, and runtime diagnostics. Sessions maintain a steering state that is updated across rounds using explicit user judgments, enabling controlled experimentation over interaction and update strategies. The repository contains a real GPU-backed implementation, a qualitative end-to-end example session, and local verification of lifecycle and runtime behavior. StableSteering is positioned as infrastructure for future comparative studies, not yet as evidence that a particular steering policy outperforms prompt-only alternatives.
