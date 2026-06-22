# Static Assets Folder

This folder contains browser-side assets shared by the HTML templates.

## Files

- `styles.css`
  Shared visual styling for the dashboard, setup, session, replay, diagnostics, tables, cards, and trace log UI.

- `app.js`
  Browser behavior for form submission, round generation, feedback submission, derived feedback payload building, and frontend trace posting.

## Important note

`app.js` is where the UI converts rating inputs into the currently selected feedback mode before sending the request to the backend.
