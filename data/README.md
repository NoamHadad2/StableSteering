# Data Folder

This folder contains runtime-generated local state.

## What lives here

- `stablesteering.db`
  SQLite database for experiments, sessions, and rounds.

- `artifacts/`
  Generated image files written by the app.

- `traces/`
  Persisted backend and frontend trace logs.

## Safe cleanup

You can delete this folder when you want a fresh local environment.

If you do, you will lose:

- saved experiments
- saved sessions and rounds
- generated artifacts
- trace history
