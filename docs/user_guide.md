# User Guide

## 1. What This App Does

StableSteering is a research prototype for interactive image-generation steering. Instead of only rewriting prompts, it lets you evaluate candidate image variations across multiple rounds and provide feedback so the system can update its steering state.

The current version runs with a real Diffusers backend by default. The mock
generator exists only inside explicit test harnesses.

The app also records backend and frontend trace events so session behavior is easier to inspect while you work.

## 2. Main Workflow

The basic flow is:

1. create an experiment
2. start a session with a prompt
3. generate a round of candidate images
4. rate the candidates
5. submit feedback
6. generate the next round
7. review the session replay

## 3. Pages

### Home

The home page shows:

- the project overview
- the current experiment list
- a link to start a new session

### Setup

The setup page lets you choose:

- experiment name
- experiment description
- prompt
- negative prompt
- sampler
- updater
- feedback mode
- number of candidates per round

### Session

The session page lets you:

- generate the next round
- review current steering state
- inspect candidate images
- assign ratings to candidates
- submit feedback
- open the replay page
- inspect the live frontend trace panel

### Replay

The replay page shows:

- all completed rounds
- each round's candidates
- the stored update summary
- the persisted outcome of submitted feedback

## 4. How to Use the Current MVP

Recommended usage:

1. open the setup page
2. keep the default settings for your first run
3. enter a prompt you can easily recognize
4. generate the first round
5. give the strongest candidate the highest rating
6. submit feedback
7. generate another round and compare how the state evolves

## 5. Understanding the Candidate Cards

Each card shows:

- a generated candidate image
- the candidate identifier
- the sampler role
- the steering vector `z`
- a rating input

The rating inputs currently drive all three supported feedback modes:

- `scalar_rating` sends the ratings directly
- `pairwise` chooses the highest-rated candidate over the lowest-rated candidate
- `top_k` converts the ratings into a ranked list

## 6. Understanding Replay

Replay is useful for:

- reviewing how many rounds were run
- seeing which candidates were shown
- checking which candidate won each update
- comparing session progression over time
- confirming what feedback was stored for a round

## 7. Current Limitations

This prototype currently:

- requires the real Diffusers backend and a CUDA-capable GPU for normal app startup
- supports only a minimal set of interaction flows
- does not yet expose advanced controls from the full specification
- stores data locally
- is meant for one local user workflow

Trace data is persisted locally under `data/traces/`.

## 8. Best Practices

- start with short, concrete prompts
- keep candidate count small while learning the workflow
- use replay after each session to understand what changed
- treat this as a research tool, not a production image editor
