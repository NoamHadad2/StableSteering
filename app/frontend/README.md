# Frontend Folder

This folder contains the browser UI.

## Structure

- `templates/`
  Server-rendered HTML templates for the dashboard, setup page, session view, replay view, and diagnostics page.

- `static/`
  Static assets used by the templates, including CSS and browser-side JavaScript.

## Current behavior

The frontend stays intentionally light:

- server-rendered HTML for pages
- small JavaScript helpers for form submission and trace capture
- visible trace panel in interactive views
