# oracle_caption_metric_extension

Oracle target-recovery extension on a curated Flickr8k test subset. The study compares human captions against AI-generated captions and compares single-metric versus multi-metric oracle feedback policies under a fixed image-generation budget.


## Scope

- Caption artifact images: `8` curated Flickr8k examples
- Experiment subset: `6` selected targets
- Total runs: `36`
- Total rounds: `144`
- Total scored candidate rows: `576`
- Caption model: `Salesforce/blip-image-captioning-large`

## Headline Results

- Strongest caption-source condition: `BLIP selected detailed caption`
  - final CLIP: `0.810`
  - final SigLIP: `0.786`
  - final DINOv2: `0.478`
  - final LPIPS: `0.676`
- Strongest oracle-policy condition by CLIP: `CLIP oracle`
  - final CLIP: `0.834`
  - final SigLIP: `0.778`
  - final DINOv2: `0.473`
  - final LPIPS: `0.686`

## Artifacts

- `runs.csv`: run-level summary rows
- `round_rows.csv`: candidate-level rows for every round
- `tables/caption_source_summary.csv`: caption-source aggregate summary with bootstrap confidence intervals
- `tables/oracle_policy_summary.csv`: oracle-policy aggregate summary with bootstrap confidence intervals
- `analysis/analysis_summary.md`: paper-facing summary

