# Feedback Folder

This folder handles normalization of user input into one internal feedback format.

## Files

- `normalization.py`
  Converts scalar ratings, pairwise inputs, and top-k/ranking inputs into normalized feedback events the updater layer can consume.

- `__init__.py`
  Package marker.

## Why it exists

Feedback normalization is separated from the frontend and updater logic so the UI can change without forcing each updater to learn multiple payload shapes.
