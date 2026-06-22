# Oracle Progress Diagnosis Analysis

This compact study tests why oracle steering often stops making visible round-by-round progress. The comparison keeps the same hidden-target recovery scaffold while changing proposal geometry, feedback modeling, and oracle selection.

## Scope

- targets: `3`
- policies: `5`
- total runs: `15`
- total rounds: `90`

## Policy summary

| policy | clip final | clip delta | dinov2 final | late improvements | incumbent selection share | plateau share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline CLIP oracle | 0.863 | 0.020 | 0.553 | 0.33 | 0.73 | 0.67 |
| Bradley-Terry progress-aware | 0.854 | 0.033 | 0.610 | 0.00 | 0.60 | 0.67 |
| Quality-diversity sampler | 0.863 | 0.044 | 0.611 | 1.00 | 0.53 | 0.67 |
| Plackett-Luce listwise | 0.851 | 0.021 | 0.565 | 1.00 | 0.67 | 0.33 |
| Pareto listwise | 0.862 | 0.049 | 0.655 | 0.67 | 0.20 | 0.00 |


## Interpretation

- The baseline still shows heavy incumbent lock-in, with incumbent selection share `0.73`.
- The strongest anti-stagnation policy by late-round movement is `Quality-diversity sampler`.
- The strongest final CLIP target-recovery policy in this compact slice is `Quality-diversity sampler`.
- The key question is therefore not only which policy ends highest, but which policy preserves challenger pressure without sacrificing final target recovery too heavily.

## Figure

![Oracle progress diagnosis](figures/oracle_progress_diagnosis.svg)
