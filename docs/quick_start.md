# Quick Start

## 1. Install

From the repository root:

```bash
python -m pip install -e .[dev]
```

## 2. Run the App

```bash
python scripts/run_dev.py
```

This server run is GPU-only by default and expects a CUDA-capable machine with
the real Diffusers backend configured.

Open:

```text
http://127.0.0.1:8000
```

## 3. Create Your First Session

1. open `/setup`
2. enter an experiment name
3. enter a prompt
4. keep the default sampler, updater, and feedback mode
5. submit the form

## 4. Run One Steering Cycle

1. click `Generate next round`
2. rate the candidates
3. click `Submit feedback`
4. click `Generate next round` again

## 5. Review Replay

Open the replay page from the session view to inspect the stored rounds and update summaries.

## 6. Run the Tests

```bash
python -m pytest
```

Browser end-to-end tests:

```bash
npm install
npm run test:e2e:chrome
```

Headed Chrome debug run:

```bash
npm run test:e2e:debug
```

The browser suite also includes a replay export API smoke test in addition to the click-through UI flow.

## 7. Prepare Hugging Face Model Assets

If you want to stage the real Diffusers model snapshot:

```bash
python scripts/setup_huggingface.py
```

Example with an explicit output directory:

```bash
python scripts/setup_huggingface.py --model-id runwayml/stable-diffusion-v1-5 --output-root models
```

Install inference dependencies and enable the real backend:

```bash
python -m pip install -e .[dev,inference]
set STABLE_STEERING_GENERATION_BACKEND=diffusers
python scripts/run_dev.py
```

Real Diffusers inference runs on GPU only. If CUDA is unavailable, the app
refuses to start instead of falling back to mock. The mock generator is test-only.

Tracing is enabled by default. Backend and frontend trace events are persisted under:

```text
data/traces/
```

## 8. Where to Read Next

- [User Guide](E:\Projects\StableSteering\docs\user_guide.md)
- [Developer Guide](E:\Projects\StableSteering\docs\developer_guide.md)
- [FAQ](E:\Projects\StableSteering\docs\faq.md)
