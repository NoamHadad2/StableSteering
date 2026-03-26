# Scripts Folder

This folder contains developer-facing helper scripts.

## Files

- `run_dev.py`
  Starts the FastAPI app locally.

- `setup_huggingface.py`
  Downloads and prepares the expected local Hugging Face model snapshot layout.

- `smoke_real_diffusers.py`
  Runs a real-model smoke test through the orchestration path and writes output artifacts.

- `run_e2e_debug.ps1`
  Launches the Playwright suite headed in Chrome for interactive debugging.

## Usage

These scripts are convenience entry points for setup, smoke testing, local development, and browser debugging.
