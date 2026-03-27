# Appendix: Controlled Slices and Submission Package Notes

## Appendix A. Sampling, Feedback, and Update Modules

The main manuscript describes the steering loop at a systems level. This appendix records the concrete module behavior implemented in the repository snapshot used for the paper.

### A.1 Implemented Sampler Families

| Sampler | Operational behavior | Typical roles |
|---|---|---|
| `random_local` | Produces one near-incumbent exploit proposal and several farther exploratory proposals with deliberate directional separation inside the trust radius. | `exploit`, `explore` |
| `exploit_orthogonal` | Uses a fixed directional pattern that mixes near-incumbent and cross-axis probes. | `exploit`, `refine`, `orthogonal`, `mirror` |
| `axis_sweep` | Sweeps positive and negative moves along steering axes with small jitter. | `axis_positive`, `axis_negative` |
| `uncertainty_guided` | Increases the perturbation span across the batch so later candidates are more exploratory. | `explore`, `validation` |
| `incumbent_mix` | Mixes conservative refinements with one broader challenger proposal. | `refine`, `mix`, `challenger` |
| `diversity_shell` | Places challengers on a wider shell around the incumbent with deliberate pairwise separation. | `shell_probe`, `shell_counterprobe` |
| `line_search` | Probes forward, backtrack, and lateral moves around the current direction. | `forward_probe`, `far_forward`, `backtrack`, `lateral_probe`, `counter_lateral` |
| `annealed_shell` | Starts with a wider shell around the incumbent and gradually narrows that shell as rounds progress, with paired probe and counter-probe directions plus controlled jitter. | `annealed_probe`, `annealed_counterprobe` |
| `spherical_cover` | Greedily selects angularly separated challenger directions on the trust-region sphere to cover the available region more uniformly. | `cover_probe` |
| `two_scale_cover` | Mixes short-radius and long-radius challenger probes over separated directions so one round can contain both local refinements and farther alternatives. | `near_cover_probe`, `far_cover_probe` |
| `plateau_escape` | Proposes one carried-forward incumbent plus forward, lateral, and counter-probe challengers designed to escape visible late-round repetition. | `forward_escape`, `lateral_plus`, `lateral_minus`, `counter_probe` |
| `quality_diversity_mix` | Mixes incumbent-adjacent proposals with angularly separated challenger probes inspired by quality-diversity coverage search so the batch preserves both local refinement and broader behavioral diversity. | `elite_probe`, `diversity_probe`, `counter_probe` |

All samplers are bounded by the configured trust radius. In round one, the system also inserts a pinned `baseline_prompt` candidate with zero steering. In later rounds, the previous winner is inserted as a carried-forward incumbent before the sampler fills the remaining candidate slots.

Two stagnation-control parameters now modify this process. `stagnation_patience` counts repeated selected-image reuse across rounds, and `stagnation_trust_radius_scale` widens the effective trust radius once that plateau detector fires. The widened trust radius is recorded in candidate metadata so later analysis can tell when escape logic was active.

### A.2 Implemented Feedback Modes

| Feedback mode | Raw payload | Normalized winner signal |
|---|---|---|
| `scalar_rating` | mapping from candidate id to numeric rating | highest-rated candidate after deterministic tie-breaking |
| `pairwise` | winner id and loser id | winner id plus loser id |
| `winner_only` | winner id | winner id |
| `approve_reject` | mapping from candidate id to boolean approval, optional preferred winner | preferred approved winner plus approved and rejected sets |
| `top_k` | ranked list of candidate ids | top-ranked candidate plus full ranking |

The current implementation validates that referenced candidates belong to the current round and rejects malformed pairwise, ranking, and approval structures before update.

### A.3 Implemented Updaters

| Updater | Update rule | Interpretation |
|---|---|---|
| `winner_copy` | `z_(t+1) = w_t` | exact replacement with the winning candidate state |
| `winner_average` | `z_(t+1) = 0.5 z_t + 0.5 w_t` | smoothed movement toward the winner |
| `linear_preference` | `z_(t+1) = 0.35 z_t + 0.65 w_t` | stronger heuristic move toward the winner |
| `score_weighted_preference` | `z_(t+1) = (1-\alpha) z_t + \alpha \, \mu_t^{+}` with score-weighted centroid `\mu_t^{+}` | uses ratings, rankings, or approvals as positive evidence instead of only the top winner |
| `contrastive_preference` | `z_(t+1) = z_t + \alpha (\mu_t^{+} - \mu_t^{-})` | moves toward preferred candidates and away from explicitly dispreferred candidates |
| `softmax_preference` | `z_(t+1) = (1-\alpha) z_t + \alpha \sum_j \pi_j z_t^{(j)}` with `\pi_j \propto \exp(\beta r_j)` over normalized scores | uses a softmax-weighted preference mixture so highly rated challengers dominate the next state without discarding the rest of the batch |
| `borda_preference` | `z_(t+1) = (1-\alpha) z_t + \alpha \sum_j \omega_j z_t^{(j)}` with Borda-style ordinal weights `\omega_j` derived from ranking position | treats the batch as an ordered list and moves toward a centroid that reflects the full ranking rather than only the winner |
| `bradley_terry_preference` | `z_(t+1) = (1-\alpha) z_t + \alpha \sum_j \rho_j z_t^{(j)}` where `\rho_j` is induced by lightweight Bradley-Terry latent utilities fit from pairwise comparisons implied by the batch | approximates a probabilistic pairwise preference model and uses the inferred utilities to weight the next steering state |
| `challenger_mixture_preference` | `z_(t+1) = z_t + \alpha \Delta_{\text{winner}} + \beta \Delta_{\text{challengers}}` where challenger weights depend on margin to the incumbent | allows near-tie challengers to influence the next state even when the incumbent still wins the round |
| `plackett_luce_preference` | `z_(t+1) = (1-\alpha) z_t + \alpha \sum_j \eta_j z_t^{(j)}` where `\eta_j` is induced by a lightweight Plackett-Luce-style listwise utility model fit from the ranked batch | uses the full ranked order to produce a probabilistic listwise update rather than a winner-only step |

These update rules are deliberately lightweight. They should be read as session-level control policies, not as full statistical preference estimators or learned reward models.

## Appendix B. Budget-Normalized Seed-Policy Slice

The seed-policy slice fixes the prompt subset, sampler, updater, and two-round steering-loop budget while comparing `fixed-per-round` and `fixed-per-candidate` seeding. Its purpose is methodological control rather than outcome-quality comparison.

| Policy | Runs | Completed runs | Total rounds | Mean rounds / run | Mean feedback events / run | Screening flags |
|---|---:|---:|---:|---:|---:|---:|
| Fixed per candidate | 9 | 9 | 18 | 2.0 | 1.0 | 7 |
| Fixed per round | 9 | 9 | 18 | 2.0 | 1.0 | 13 |

Interpretation boundary: both policies preserve the same workflow structure under matched conditions. The differing screening-flag counts are retained as descriptive diagnostics only and should not be read as evidence of visual superiority.

## Appendix C. Fixed-Sampler Updater Ablation

The updater ablation fixes the sampler, seed policy, prompt subset, and two-round budget while comparing `winner_copy`, `winner_average`, and `linear_preference`.

| Updater | Runs | Completed runs | Total rounds | Mean rounds / run | Mean feedback events / run | Screening flags |
|---|---:|---:|---:|---:|---:|---:|
| Linear preference | 9 | 9 | 18 | 2.0 | 1.0 | 7 |
| Winner average | 9 | 9 | 18 | 2.0 | 1.0 | 8 |
| Winner copy | 9 | 9 | 18 | 2.0 | 1.0 | 8 |

Interpretation boundary: the ablation demonstrates that the same controlled experiment scaffold can compare updater choices cleanly. It does not establish that one updater should be preferred scientifically.

## Appendix D. Oracle Target-Recovery Proxy Study

The oracle target-recovery bundle introduces a more outcome-facing but still tightly bounded evaluation setting. Each task begins from a real target image paired with a manually written caption and negative prompt. The generator receives only the text inputs. The hidden target image is used exclusively by an oracle that scores each generated candidate by CLIP image-similarity and selects the highest-scoring candidate as the winner for the next steering update.

This protocol preserves the conceptual framing of StableSteering. It still starts from language, still uses candidate proposals and winner-based updates, and still never exposes the target image directly to the generator. The hidden target is therefore an evaluation device and an oracle-feedback source, not a conditioning signal.

### D.1 Protocol Summary

| Field | Value |
|---|---|
| Targets | 3 held-out real images with manual captions |
| Rounds per target | 10 |
| Candidates per round | 4 |
| Sampler | `exploit_orthogonal` |
| Updater | `linear_preference` |
| Feedback mode | `winner_only` |
| Seed policy | `fixed-per-candidate` |
| Steering dimension | 5 |
| Oracle metric | CLIP image-image cosine similarity |

### D.2 Aggregate Outcome

| Measure | Mean |
|---|---:|
| Baseline prompt-only similarity | 0.825 |
| Round-1 best-candidate similarity | 0.888 |
| Round-10 best-candidate similarity | 0.896 |
| Baseline to round-10 improvement | 0.071 |

All three targets improve relative to the baseline prompt-only render. Two targets achieve their best score in the first round and then plateau, while one target continues improving until round four. This pattern suggests that the current steering loop often finds a strong target-facing direction early, with later rounds serving mostly to preserve rather than substantially extend that gain.

### D.3 Interpretation Boundary

The oracle bundle is intentionally narrow.

1. It is a proxy target-recovery study, not a human-preference study.
2. The same embedding family is used for oracle selection and evaluation.
3. Improvement in CLIP space should therefore be interpreted as movement toward the hidden target under that proxy metric, not as general visual superiority.

Despite these caveats, the bundle matters because it demonstrates that StableSteering can support a round-by-round measurable alignment study in addition to workflow-level protocol slices.

## Appendix E. Repeated-Seed Multi-Metric Oracle Extension

The repeated oracle extension strengthens the proxy-evaluation story without changing the core target-recovery protocol. Each of the three held-out targets is run three times under different deterministic seed assignments, yielding 9 runs, 90 rounds, and 360 candidate rows. CLIP image-image cosine similarity still serves as the oracle metric used to choose winners, but final evaluation is reported under both CLIP and DINOv2 image embeddings.

### E.1 Protocol Summary

| Field | Value |
|---|---|
| Targets | 3 held-out real images with manual captions |
| Repeats per target | 3 |
| Total runs | 9 |
| Rounds per run | 10 |
| Candidates per round | 4 |
| Sampler | `exploit_orthogonal` |
| Updater | `linear_preference` |
| Feedback mode | `winner_only` |
| Seed policy | `fixed-per-candidate` |
| Steering dimension | 5 |
| Oracle metric | CLIP image-image cosine similarity |
| Auxiliary evaluation metric | DINOv2 image-image cosine similarity |

### E.2 Aggregate Outcome

| Metric | Baseline mean | Final mean | Mean improvement | Run-level sd |
|---|---:|---:|---:|---:|
| CLIP cosine | 0.828 | 0.881 | 0.053 | 0.035 |
| DINOv2 cosine | 0.452 | 0.595 | 0.142 | 0.179 |

### E.3 Target-Level Summary

| Target | Repeats | CLIP final (mean ± sd) | DINOv2 final (mean ± sd) |
|---|---:|---:|---:|
| Black-and-white cat portrait | 3 | 0.883 ± 0.016 | 0.565 ± 0.047 |
| Mountain lake landscape | 3 | 0.844 ± 0.005 | 0.505 ± 0.067 |
| Red bicycle street photo | 3 | 0.916 ± 0.011 | 0.715 ± 0.035 |

### E.4 Interpretation Boundary

1. CLIP still acts as the oracle that chooses winners.
2. DINOv2 is an independent evaluator, not a second oracle.
3. The extension reduces single-seed and single-metric risk but remains a proxy target-recovery study rather than a human-perception study.

### E.5 Plateau and Stagnation-Control Follow-ons

The repeated oracle extension also exposed a qualitative failure mode: visible later-round freezing. In the original repeated-seed oracle bundle, all `9/9` runs reused a previously selected image at some point and `8/9` runs ended with the same selected image in the last three rounds.

Three follow-on bundles were therefore run. The first replaced the older oracle policy with the new `plateau_escape` sampler and `softmax_preference` updater while keeping the same target family and repeated-seed protocol. The second added two stronger anti-stagnation controls on top of that bundle: temporary trust-radius widening after stagnation and oracle-side incumbent cooldown, which excludes the carried-forward incumbent from winner selection after repeated same-image reuse. The third kept the same compact `plateau_escape + softmax_preference` family but compared three incumbent-handling policies directly under a matched budget: carry-forward baseline, soft incumbent penalty, and hard incumbent cooldown.

#### E.5.1 Plateau-Escape Bundle

| Measure | Value |
|---|---:|
| Runs | 9 |
| Last-three-round identical-image plateaus | 8 |
| Runs still improving after round 4 | 6 |
| Mean final CLIP cosine | 0.886 |
| Mean final DINOv2 cosine | 0.554 |

Interpretation: `plateau_escape` and `softmax_preference` improved late-round movement relative to the earlier repeated oracle bundle, but visible incumbent freezing was still common.

#### E.5.2 Stagnation-Control Bundle

| Measure | Value |
|---|---:|
| Runs | 9 |
| Last-three-round identical-image plateaus | 0 |
| Runs still improving after round 4 | 8 |
| Mean final CLIP cosine | 0.869 |
| Mean final DINOv2 cosine | 0.598 |

Interpretation: the stagnation-control policy solved the visible freezing problem almost completely, but it reduced final CLIP recovery relative to the softer plateau-escape bundle. The most plausible explanation is over-exploration: hard incumbent suppression keeps the session moving, but sometimes away from the current best proxy solution.

#### E.5.3 Budget-Matched Incumbent-Policy Slice

| Policy | Runs | Final CLIP (mean ± sd) | Final DINOv2 (mean ± sd) | Improves after round 4 | Last-three-round plateaus | Mean unique selected-image ratio |
|---|---:|---:|---:|---:|---:|---:|
| Carry-forward baseline | 3 | 0.884 ± 0.037 | 0.583 ± 0.134 | 2/3 | 1/3 | 0.556 |
| Soft incumbent penalty | 3 | 0.891 ± 0.033 | 0.636 ± 0.112 | 1/3 | 2/3 | 0.389 |
| Hard incumbent cooldown | 3 | 0.856 ± 0.034 | 0.568 ± 0.132 | 1/3 | 0/3 | 0.556 |

Interpretation: the compact matched-budget slice sharpens the anti-stagnation story. Soft incumbent penalty achieves the strongest final proxy recovery on this small comparison, suggesting that milder incumbent discouragement can be helpful. Hard cooldown still removes end-of-run sticking most reliably, but again appears too aggressive for final alignment. The problem therefore looks less like a binary “freeze or move” issue and more like a tradeoff between retaining the best incumbent and preserving useful challenger pressure.

## Appendix F. Human Pairwise Evaluation Layer

The paper package now includes a small direct-human evaluation layer meant for prompt-faithfulness and coherence judgments. The layer is intentionally modest: it curates six pairwise comparisons and packages them for browser-based inspection plus CSV-based annotation.

### F.1 Package Summary

| Field | Value |
|---|---|
| Prompt families | 3 |
| Pair types | baseline vs StableSteering final; no-update vs StableSteering final |
| Total curated pairs | 6 |
| Annotation responses | `left`, `right`, `tie`, `invalid` |
| Browser preview | `pairwise_review.html` |
| Current annotations | 0 |

### F.2 Collection Question

Judges are asked a single fixed question:

> Which image better satisfies the prompt while remaining visually coherent?

This wording is intentionally narrower than “which image is better overall.” It targets the central interaction claim of the paper: the steering loop should help move from prompt-only initialization toward images that better satisfy the intended prompt while preserving coherence.

### F.3 Interpretation Boundary

1. The current package is protocol-ready but contains no human judgments yet.
2. It therefore supports submission completeness rather than outcome evidence.
3. Once populated, the layer can support direct pairwise preference estimates with confidence intervals and agreement reporting.

## Appendix G. Sampler and Feedback-Model Comparison Slice

The final controlled bundle asks whether the same oracle target-recovery scaffold can reveal meaningful differences among candidate-proposal strategies and richer preference models. The bundle is split into two slices. The sampler slice fixes the updater at `linear_preference` with `winner_only` feedback and compares `random_local`, `exploit_orthogonal`, `diversity_shell`, and `line_search`. The feedback-model slice fixes the sampler at `exploit_orthogonal` and compares four update-and-feedback pairings: `winner_average` with `winner_only`, `linear_preference` with `winner_only`, `score_weighted_preference` with `scalar_rating`, and `contrastive_preference` with `top_k` ranking.

All runs use the same three real-image targets, the same manual captions, a five-round budget, `fixed-per-candidate` seeds, a five-dimensional steering state, and four candidates per round. The resulting bundle contains 24 runs, 120 rounds, and 480 candidate rows.

### G.1 Sampler Slice Summary

| Sampler | Mean baseline score | Mean final best score | Mean improvement |
|---|---:|---:|---:|
| `diversity_shell` | 0.829 | 0.882 | 0.053 |
| `line_search` | 0.829 | 0.882 | 0.053 |
| `exploit_orthogonal` | 0.828 | 0.867 | 0.038 |
| `random_local` | 0.844 | 0.876 | 0.032 |

The main qualitative pattern is that the newly added broader search policies, `diversity_shell` and `line_search`, finish higher than the older local baselines under this oracle proxy. This suggests that proposal geometry remains a meaningful scientific axis even when the update rule is held fixed.

### G.2 Feedback-Model Slice Summary

| Updater / feedback pairing | Mean baseline score | Mean final best score | Mean improvement |
|---|---:|---:|---:|
| `winner_average` + `winner_only` | 0.829 | 0.882 | 0.053 |
| `linear_preference` + `winner_only` | 0.839 | 0.885 | 0.046 |
| `contrastive_preference` + `top_k` | 0.827 | 0.873 | 0.045 |
| `score_weighted_preference` + `scalar_rating` | 0.845 | 0.883 | 0.038 |

The richer preference models remain competitive, but this small proxy study does not yet show that they dominate winner-centric updates. The more defensible interpretation is methodological: StableSteering can host different preference models and compare them under the same steering scaffold.

### G.3 Interpretation Boundary

This bundle should be read as an exploratory controlled slice rather than a definitive ranking.

1. The same CLIP family is still used for oracle selection and evaluation.
2. The target set is intentionally small.
3. The sampler slice and the feedback slice answer different questions and should not be compared directly.
4. The resulting ordering is therefore evidence of sensitivity to modeling choice, not proof of globally preferred policies.

## Appendix H. Method-Extension Comparison for New Samplers, Preference Models, and Oracle Policies

The earlier sampler and feedback-model slice established that the steering loop is sensitive to modeling choice. The next question is whether the framework can absorb genuinely different method families without changing the surrounding session scaffold. The method-extension bundle answers that question with one larger but still controlled hidden-target recovery study. It introduces two new sampler families, two new ordinal preference updaters, and two alternative oracle-selection policies on top of the earlier CLIP-only oracle.

All three slices share the same outer protocol: three held-out targets with manual captions, one repeat per target-policy cell, five rounds per run, four candidates per round, `fixed-per-candidate` seeds, a five-dimensional steering state, and a 512x512 Stable Diffusion v1.5 generation backend. The bundle contains 33 runs, 165 rounds, and 660 candidate rows in total.

### H.1 Sampler Extension Slice

The sampler slice fixes the updater at `softmax_preference` and compares four broader search geometries: `diversity_shell`, `line_search`, `annealed_shell`, and `spherical_cover`.

| Sampler | Final CLIP | CLIP delta | Final DINOv2 | DINOv2 delta |
|---|---:|---:|---:|---:|
| `annealed_shell` | 0.878 | 0.065 | 0.627 | 0.110 |
| `diversity_shell` | 0.877 | 0.065 | 0.595 | 0.127 |
| `line_search` | 0.878 | 0.052 | 0.660 | 0.095 |
| `spherical_cover` | 0.881 | 0.041 | 0.668 | 0.109 |

Interpretation: the sampler slice is competitive rather than decisive. `spherical_cover` finishes with the strongest final CLIP and DINOv2 scores, while `annealed_shell` remains competitive with both of the earlier diversity-forward baselines. The broader conclusion is that the proposal geometry remains a meaningful modeling choice: angular coverage and round-dependent shell narrowing both change the behavior of the same outer steering loop.

### H.2 Preference-Model Extension Slice

The preference-model slice fixes the sampler at `diversity_shell` and compares four update rules: `softmax_preference`, `score_weighted_preference`, `borda_preference`, and `bradley_terry_preference`.

| Preference model | Final CLIP | CLIP delta | Final DINOv2 | DINOv2 delta |
|---|---:|---:|---:|---:|
| `borda_preference` | 0.877 | 0.047 | 0.535 | -0.007 |
| `bradley_terry_preference` | 0.886 | 0.088 | 0.687 | 0.150 |
| `score_weighted_preference` | 0.869 | 0.047 | 0.643 | 0.180 |
| `softmax_preference` | 0.879 | 0.033 | 0.581 | 0.026 |

Interpretation: the richer ordinal models do not all behave the same way. `bradley_terry_preference` is the strongest new updater in this small study, suggesting that a lightweight latent-utility fit can extract additional information from the ranked batch. `borda_preference` broadens the method family conceptually, but its weak DINOv2 result is an important warning that richer ordinal structure does not automatically imply stronger target recovery.

### H.3 Oracle-Policy Extension Slice

The oracle slice fixes the steering loop at `annealed_shell + softmax_preference` and compares three hidden-target selection policies: CLIP-only, CLIP+DINO ensemble, and CLIP-plus-novelty bonus.

| Oracle policy | Final CLIP | CLIP delta | Final DINOv2 | DINOv2 delta |
|---|---:|---:|---:|---:|
| CLIP + DINO ensemble | 0.874 | 0.063 | 0.697 | 0.267 |
| CLIP + novelty bonus | 0.883 | 0.047 | 0.670 | 0.113 |
| CLIP oracle | 0.877 | 0.068 | 0.659 | 0.188 |

Interpretation: the oracle itself is a modeling choice, not only evaluation plumbing. CLIP-only retains the strongest direct CLIP improvement, but the CLIP+DINO ensemble produces the strongest DINOv2 recovery by a wide margin. The novelty-bonus oracle keeps exploration pressure alive but does not dominate either metric here. The most defensible conclusion is therefore that hidden-target steering can be steered by different notions of similarity, and those choices materially change the convergence behavior observed by the same outer loop.

### H.4 Interpretation Boundary

This bundle is intentionally exploratory.

1. The target set is still very small.
2. Each cell uses only one repeat per target.
3. The oracle slice changes the hidden-target selection rule, not only the evaluation metric.
4. The resulting comparisons should therefore be read as evidence that the framework can host richer method families and that those families matter, not as a final ranking of globally best policies.

## Appendix I. Oracle Progress Diagnosis and Focused Follow-up

The repeated oracle studies showed a concrete behavioral failure mode: later rounds often appeared frozen because the carried-forward incumbent kept winning and the same image was selected repeatedly. A focused compact diagnosis therefore asked a narrower question than the earlier bundles: what exactly is causing the visible lack of incremental progress, and can targeted changes improve either late-round movement or final target recovery?

The diagnosis compared four policies under one shared protocol: the older baseline `exploit_orthogonal + linear_preference + CLIP-only oracle`, a new `two_scale_cover` sampler that mixes short- and long-radius challengers, a new `challenger_mixture_preference` updater that lets near-miss challengers influence the next state, and a fully progress-aware policy that combines both changes with a softer `clip_margin_mix` oracle. A small follow-up then swapped in the stronger ordinal `bradley_terry_preference` model to test whether a better ranking-based user model could recover a more favorable balance.

### I.1 Diagnosis Bundle Summary

| Policy | Final CLIP | CLIP delta | Final DINOv2 | Late improvements | Incumbent selection share | Plateau share |
|---|---:|---:|---:|---:|---:|---:|
| Baseline CLIP oracle | 0.884 | 0.054 | 0.557 | 0.00 | 0.80 | 1.00 |
| Two-scale cover sampler | 0.889 | 0.080 | 0.606 | 0.33 | 0.93 | 1.00 |
| Challenger-mixture updater | 0.873 | 0.055 | 0.535 | 0.33 | 0.73 | 1.00 |
| Full progress-aware policy | 0.882 | 0.058 | 0.496 | 0.67 | 0.47 | 0.33 |

Interpretation: the first compact diagnosis localizes the stagnation problem. A stronger sampler improves final proxy recovery but still leaves plateauing intact. A progress-aware oracle plus challenger-aware updater reduces incumbent lock-in and plateauing substantially, but the first version pays too much in DINOv2 recovery.

### I.2 Follow-up with Bradley-Terry Preference Modeling

| Policy | Final CLIP | CLIP delta | Final DINOv2 | Late improvements | Incumbent selection share | Plateau share |
|---|---:|---:|---:|---:|---:|---:|
| Two-scale cover sampler | 0.884 | 0.054 | 0.549 | 1.00 | 0.67 | 0.67 |
| Full progress-aware policy | 0.876 | 0.045 | 0.522 | 1.00 | 0.73 | 0.33 |
| Bradley-Terry cover | 0.878 | 0.018 | 0.631 | 0.67 | 0.80 | 0.67 |
| Bradley-Terry progress-aware | 0.883 | 0.063 | 0.630 | 1.33 | 0.60 | 0.33 |

Interpretation: the follow-up improves the compromise substantially. `Bradley-Terry progress-aware` preserves much of the late-round movement benefit while recovering strong final CLIP and DINOv2 scores. On this small study it is the clearest current candidate for a balanced anti-stagnation policy.

### I.3 Interpretation Boundary

1. Both compact bundles are still small three-target proxy studies.
2. They are designed to diagnose behavior, not to establish a final best policy.
3. The progress-aware oracle is still a handcrafted selection rule rather than a learned model of human preference.

## Appendix J. Reproducibility and Artifact Notes

The submission package rests on repository-contained artifacts:

1. A journal-style main manuscript.
2. A preserved five-round qualitative case-study bundle with trace report and HTML walkthrough.
3. A repeated minimal baseline matrix.
4. A budget-normalized seed-policy slice.
5. A fixed-sampler updater ablation.
6. An oracle target-recovery bundle with preserved targets, runs, analysis, and derived figures.
7. A repeated-seed multi-metric oracle bundle with preserved runs, tables, and derived figures.
8. A human pairwise evaluation package with curated pairs and annotation materials.
9. A sampler and feedback-model comparison slice with preserved runs, tables, and derived figures.
10. Plateau-escape and stagnation-control oracle follow-ons with preserved runs and analysis summaries.
11. A budget-matched incumbent-policy oracle slice with preserved summaries and a derived figure.
12. Focused oracle-progress diagnosis and follow-up bundles with preserved summaries and a derived figure.
13. Generated paper figures copied or built from repository-contained assets.

The core reproducibility claim is artifact traceability. Each experimental bundle preserves runs, rounds, candidate rows, summaries, and derived analysis outputs under fixed protocols. The present appendix therefore supports the main text by documenting controlled evidence and submission packaging, not by introducing new scientific claims.
