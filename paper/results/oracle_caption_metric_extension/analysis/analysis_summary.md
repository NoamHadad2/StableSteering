# oracle_caption_metric_extension

Oracle target-recovery extension on a curated Flickr8k test subset. The study compares human captions against AI-generated captions and compares single-metric versus multi-metric oracle feedback policies under a fixed image-generation budget.


## Dataset and Caption Artifact

- Caption artifact images: `8` curated Flickr8k test examples
- Experiment subset: `6` selected target images
- Total runs: `36`
- Total rounds: `144`
- Total scored candidate rows: `576`
- Caption model: `Salesforce/blip-image-captioning-large`
- Mean human prompt length: `13.0` words
- Mean selected AI prompt length: `14.625` words

## Caption-Source Slice

| Condition | Final CLIP | Final SigLIP | Final DINOv2 | Final LPIPS |
| --- | ---: | ---: | ---: | ---: |
| BLIP selected detailed caption | 0.810 ([0.773, 0.845]) | 0.786 ([0.728, 0.841]) | 0.478 ([0.256, 0.693]) | 0.676 ([0.619, 0.737]) |
| BLIP caption | 0.786 ([0.735, 0.832]) | 0.750 ([0.698, 0.801]) | 0.391 ([0.168, 0.621]) | 0.692 ([0.642, 0.733]) |
| Human caption | 0.798 ([0.735, 0.854]) | 0.785 ([0.729, 0.842]) | 0.476 ([0.255, 0.686]) | 0.686 ([0.647, 0.725]) |

## Oracle-Metric Slice

| Condition | Final CLIP | Final SigLIP | Final DINOv2 | Final LPIPS |
| --- | ---: | ---: | ---: | ---: |
| CLIP oracle | 0.834 ([0.808, 0.860]) | 0.778 ([0.727, 0.827]) | 0.473 ([0.273, 0.653]) | 0.686 ([0.645, 0.730]) |
| Multi-metric oracle | 0.825 ([0.792, 0.862]) | 0.772 ([0.717, 0.824]) | 0.458 ([0.255, 0.662]) | 0.708 ([0.670, 0.740]) |
| SigLIP oracle | 0.796 ([0.761, 0.831]) | 0.789 ([0.725, 0.853]) | 0.476 ([0.258, 0.631]) | 0.718 ([0.681, 0.757]) |

## Notes

- Higher is better for CLIP, SigLIP, and DINOv2.
- Lower is better for LPIPS.
- Confidence intervals are nonparametric bootstrap intervals over run-level means.
