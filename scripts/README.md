# Scripts Folder

This folder contains developer-facing helper scripts.

## Files

- `run_dev.py`
  Starts the FastAPI app locally.

- `setup_huggingface.py`
  Downloads and prepares the expected local Hugging Face model snapshot layout.

- `smoke_real_diffusers.py`
  Runs a real-model smoke test through the orchestration path and writes output artifacts.

- `create_real_e2e_example.py`
  Executes a real multi-round steering session on GPU and writes a standalone HTML walkthrough plus a trace bundle under `output/examples/real_e2e_example_run/`.

- `run_e2e_debug.ps1`
  Launches the Playwright suite headed in Chrome for interactive debugging.

- `bootstrap.ps1`
  Creates a local virtual environment, installs dependencies, installs npm packages, and can optionally prepare the Hugging Face model snapshot.

- `build_release_zip.ps1`
  Builds an optional source release zip from tracked repository files into `output/releases/`.

- `build_pages_site.py`
  Converts the repository Markdown set into a static HTML site under `site/` with rewritten inter-document links for GitHub Pages.

## Usage

These scripts are convenience entry points for setup, release packaging, smoke testing, local development, and browser debugging.
