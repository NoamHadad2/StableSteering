# Templates Folder

This folder contains the Jinja/HTML templates rendered by FastAPI.

## Files

- `index.html`
  Home page with the experiment list and quick links into setup and diagnostics.

- `setup.html`
  Session and experiment setup form.

- `session.html`
  Main interactive session page for round generation, rating input, feedback submission, replay access, and trace visibility.

- `replay.html`
  Round-by-round replay view of a session.

- `diagnostics.html`
  Runtime diagnostics page showing backend, model source, device, CUDA status, and full diagnostic payload.

## Template style

These templates are intentionally simple and readable so debugging with browser dev tools stays easy.
