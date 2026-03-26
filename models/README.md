# Models Folder

This folder stores prepared local model assets for the real Diffusers backend.

## What lives here

- Hugging Face snapshots prepared by `scripts/setup_huggingface.py`

## Notes

- This folder is intentionally not committed except for this guide.
- The normal runtime expects a prepared model snapshot here unless remote model download is explicitly enabled.

## Safe cleanup

You can delete the prepared model snapshots to reclaim disk space, but the real backend will not start again until you re-run:

```text
python scripts/setup_huggingface.py
```
