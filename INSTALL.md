# Install Guide

This document explains how to install and prepare StableSteering on Windows for local development or evaluation.

## Requirements

- Windows with PowerShell
- Python 3.11 or newer
- Node.js and npm
- Git

For the real generation backend you also need:

- a CUDA-capable GPU
- compatible PyTorch/CUDA support

## Fastest Setup

From the repository root run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
```

This will:

- create a local virtual environment in `.venv`
- install Python dependencies
- install npm dependencies
- optionally prepare Hugging Face model assets if requested

## Manual Setup

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install Python dependencies

Development dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

Real inference dependencies:

```powershell
python -m pip install -e .[dev,inference]
```

### 3. Install browser test dependencies

```powershell
npm install
```

## Prepare Model Assets

If you want to run the real Diffusers backend:

```powershell
python scripts/setup_huggingface.py
```

The prepared model snapshot is stored under `models/`.

## Run the App

```powershell
python scripts/run_dev.py
```

Open:

```text
http://127.0.0.1:8000
```

Useful runtime pages:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/diagnostics/view`
- `http://127.0.0.1:8000/sessions/{session_id}/trace-report`

## Run the Tests

Backend tests:

```powershell
python -m pytest
```

Default browser suite:

```powershell
npm run test:e2e:chrome
```

Headed browser debug run:

```powershell
npm run test:e2e:debug
```

Opt-in real-backend browser smoke:

```powershell
$env:STABLE_STEERING_E2E_REAL="true"
npm run test:e2e:real
```

## Common Notes

- The normal app runtime is GPU-only and uses the real Diffusers backend.
- The mock generator is reserved for tests and explicit test harnesses only.
- Round generation and feedback submission run as async jobs with visible progress in the UI.
- Trace logs are written under `data/traces/`.
- Per-session trace bundles and readable `report.html` files are written under `data/traces/sessions/<session_id>/`.
- You can generate a complete real GPU example bundle with `python scripts/create_real_e2e_example.py`.
