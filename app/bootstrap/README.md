# Bootstrap Folder

This folder contains helper code used before or around runtime startup.

## Files

- `huggingface.py`
  Utilities for preparing and naming local Hugging Face model snapshots, including the slugged local model directory layout used by the app.

- `__init__.py`
  Package marker.

## When to look here

Open this folder when you need to:

- understand how prepared model paths are resolved
- change model snapshot naming rules
- extend setup-time behavior for external assets
