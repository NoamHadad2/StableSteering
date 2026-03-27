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
  Executes a real multi-round steering session on GPU and writes a standalone HTML walkthrough plus a trace bundle under `output/examples/real_e2e_example_run/`. The example is intended to demonstrate system value starting from a strong user text prompt and a clear objective.

- `run_paper_minimal_baseline_matrix.py`
  Executes bounded paper-facing experiment bundles from a protocol YAML and writes JSON/CSV summaries plus per-run runtime bundles under the chosen `paper/results/.../` directory.

- `run_paper_oracle_target_recovery.py`
  Executes the hidden-target oracle study that starts from manual captions, steers for multiple rounds, and scores progress in CLIP space against the held-out target image.

- `run_paper_sampler_feedback_comparison.py`
  Executes the controlled sampler and feedback-model comparison bundle and writes policy summaries, round curves, and paper-facing SVG plots under `paper/results/sampler_feedback_comparison/`.

- `run_paper_method_extension_comparison.py`
  Executes the extended method-comparison bundle for newer samplers, richer preference models, and alternative oracle-selection policies, then writes policy summaries, round curves, and paper-facing SVG plots under `paper/results/method_extension_comparison/`.

- `build_paper_baseline_analysis.py`
  Reads repeated experiment CSVs from a chosen `paper/results/.../tables/` directory and writes paper-facing analysis tables plus a short appendix note under the matching `analysis/` directory.

- `build_journal_manuscript_assets.py`
  Copies and prepares paper figures from repository-contained experiment bundles into `paper/figures/`.

- `build_journal_manuscript_html.py`
  Renders the self-contained journal manuscript HTML with justified text and MathJax equations.

- `build_journal_appendix_html.py`
  Renders the self-contained journal appendix HTML with justified text and MathJax equations.

- `build_paper_html.py`
  Renders the older Markdown manuscript draft into a standalone HTML document under `paper/`.

- `run_e2e_debug.ps1`
  Launches the Playwright suite headed in Chrome for interactive debugging.

- `bootstrap.ps1`
  Creates a local virtual environment, installs dependencies, installs npm packages, and can optionally prepare the Hugging Face model snapshot.

- `build_release_zip.ps1`
  Builds an optional source release zip from tracked repository files into `output/releases/`.

- `build_pages_site.py`
  Converts the repository Markdown set into a static HTML site under `site/`, rewrites inter-document links for GitHub Pages, and copies published image assets used by the docs.

- `generate_readme_banner.py`
  Uses the Gemini image-generation API to create the repository banner asset used in the main README.

- `generate_doc_illustrations.py`
  Uses the Gemini image-generation API to create conceptual illustration assets for the student tutorial and published HTML docs.

## Usage

These scripts are convenience entry points for setup, release packaging, smoke testing, local development, and browser debugging.
