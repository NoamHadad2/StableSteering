# Paper Improvement Log

This file records the latest concentrated paper-improvement loop.

## Selected agents

The three highest-leverage agents for the current draft stage were:

1. `claim_evidence_mapper`
2. `reader_confusion_detector`
3. `storyline_architect`

## Ten focused improvement passes applied

1. Reframed the manuscript opening so the paper type is explicit on the first page: systems-platform paper, not benchmark paper.
2. Tightened the abstract so it describes a platform and research scaffold rather than implying a new steering method.
3. Defined the steering state earlier and more concretely as a session-level control abstraction.
4. Re-centered the whole paper around one loop: prompt, candidates, preferences, update, replay.
5. Reduced places where multiple samplers or updaters could be misread as comparative results.
6. Promoted the checked-in example run to the paper’s central qualitative proof-of-value artifact.
7. Added an explicit compact case-study setup description with prompt, config, backend, and stopping rule.
8. Softened verification language so software testing is clearly separated from research validation.
9. Tightened related-work positioning to avoid unsupported novelty or uniqueness claims.
10. Synced the contribution statement, title/abstract variants, readiness map, and reader-confusion notes with the revised manuscript framing.

## Result

The paper now reads more coherently as a traceable platform paper with a qualitative case study and explicit evidence boundaries.

## Follow-up agent pass after skill upgrade

After the paper-writing skills were upgraded to a stricter prestige-venue standard, a second focused agent pass used:

1. `reviewer_simulator`
2. `storyline_architect`
3. `claim_evidence_mapper`

That pass tightened the manuscript in four ways:

1. removed the stronger "research platform" phrasing from the title and abstract
2. moved related-work positioning earlier so readers understand the paper type before system details
3. merged the workflow and steering-loop story into one cleaner platform section
4. reframed the example run consistently as a single curated qualitative case study

It also replaced the old `Author note` ending with a real conclusion that states the current contribution and the next evidence threshold.

## Ten-cycle student-builder gap-closing loop

To close the paper-readiness gap after the manuscript rewrite, a ten-cycle student-builder loop pushed the repository from "missing baseline path" to "executed pilot baseline bundle":

1. locked the minimal baseline comparison question
2. created a fixed prompt suite YAML
3. wrote a bounded baseline protocol
4. implemented a reproducible runner script
5. created a paper-facing results directory contract
6. executed the full 3-prompt x 3-policy pilot on the real Diffusers backend
7. preserved per-run runtime bundles and trace reports
8. fixed the aggregate-results bug in the manifest generation
9. added a compact baseline summary table and pilot summary note
10. synced the manuscript and paper index to cite the executed pilot conservatively

The result is still not a prestige-venue-ready empirical paper, but it is a materially stronger submission package: the repo now contains an executed, inspectable comparative pilot rather than only prose about future comparisons.

## Pilot-integration quality pass

After the pilot bundle existed, a follow-up paper-quality pass focused on integration rather than new code:

1. added a real `Minimal Baseline Pilot` subsection to the manuscript
2. separated the qualitative case study from the comparative pilot more explicitly
3. replaced stale "no benchmark matrix exists" wording with a more accurate "no larger benchmark matrix exists"
4. added a compact paper-ready pilot table artifact
5. made the lightweight visual checks explicit as screening heuristics, not quality judgments
6. updated the claim/evidence map so the pilot is now a verified bounded-comparison artifact

This pass improved reviewer readability and evidence hygiene without inflating the empirical claim.

## Concrete protocol scaffold pass

The next student-builder pass materialized the minimal baseline comparison package on disk:

1. `paper/protocols/minimal_baseline_protocol.md`
2. `paper/protocols/minimal_baseline_prompt_suite.yaml`
3. `scripts/run_paper_minimal_baseline_matrix.py`
4. `paper/results/baseline_matrix/README.md`
5. `paper/results/baseline_matrix/manifest.json`
6. `paper/results/baseline_matrix/protocol_snapshot.yaml`

This turns the missing comparison path into a concrete artifact bundle while still being explicit that the comparative results corpus has not been generated yet.

## Repeated-pilot repeatability pass

After the one-shot pilot was integrated, the next reviewer-facing pass focused on the smallest repeatability extension that would materially improve credibility:

1. extended the bounded pilot to three independent repeats per prompt-policy cell
2. regenerated the real Diffusers bundle as a 27-run, 36-round, 144-candidate artifact set
3. added per-cell repeat summaries with means and standard deviations for rounds per run and feedback events per run
4. updated the manuscript to claim only workflow-level stability, not image-quality superiority
5. added a dedicated `seed_robustness.md` note so the reviewer can see exactly what the repeated pilot does and does not support

This pass does not make the paper a benchmark paper, but it closes one major reviewer concern: the earlier pilot is no longer only a single-shot comparison.

## Clarity and positioning pass

The next review-driven pass focused on publishability rather than new experiments:

1. added a blunt evidence-boundary sentence to the abstract and introduction
2. made `z` operationally explicit with a compact loop summary
3. inserted a small table separating the qualitative case study, workflow pilot, and software verification
4. upgraded the pilot table to expose unequal interaction budgets directly
5. rewrote related work around comparison axes instead of a flat paper list
6. expanded the bibliography just enough to support the new comparison structure

This pass made the paper easier to classify correctly as a systems/platform submission with bounded evidence, which should lower reviewer confusion and novelty-positioning risk.

## Student-builder analysis pass

The next student-builder pass improved both the project and the paper by adding a paper-facing analysis layer on top of the repeated pilot bundle:

1. implemented `scripts/build_paper_baseline_analysis.py`
2. generated normalized workflow summaries under `paper/results/baseline_matrix/analysis/`
3. added appendix-style analysis artifacts in both Markdown and HTML
4. updated the manuscript to cite the derived analysis conservatively
5. rewrote the paper-package README so the submission-facing path is much clearer

This pass did not add new scientific claims, but it made the existing empirical package easier to inspect, summarize, and cite without relying on raw CSV tables alone.

## Controlled-bundle execution pass

The next five-cycle block converted two planned experiments into completed paper artifacts:

1. generalized the paper runner so protocol YAML files can define bounded paper-facing experiment bundles
2. added and executed a budget-normalized seed-policy slice on the real Diffusers backend
3. added and executed a fixed-sampler updater ablation on the real Diffusers backend
4. derived appendix-style analysis summaries for both new bundles
5. updated the manuscript and paper-package README to cite the new bundles conservatively

This pass most directly improved publishability by replacing two “next experiment” bullets with real, reproducible evidence bundles.
