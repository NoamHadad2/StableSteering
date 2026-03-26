# Release Notes v0.1.1

## Summary

This release expands the research MVP into a more configurable and inspectable system.

Major themes in this release:

- richer sampling and preference-mode support
- stronger per-session YAML configuration
- better runtime trace reporting and portable HTML artifacts
- improved docs-site linking and roadmap detail
- real seed-policy behavior in the orchestration layer

## Highlights

### Sampling and preference updates

- added `axis_sweep` and `incumbent_mix` samplers
- added `winner_only` and `approve_reject` feedback modes
- documented the current sampler and preference-model behavior more clearly

### Session and orchestration updates

- first round always includes the unmodified prompt baseline
- later rounds carry forward the previous winner as the incumbent
- default candidate count is now `5`
- implemented seed policies:
  - `fixed-per-round`
  - `fixed-per-candidate`
  - `fixed-per-candidate-role`

### Reporting and examples

- improved HTML session trace reporting
- ensured initial prompt visibility in generated HTML reports
- regenerated the real end-to-end sample bundle
- added a configuration-matrix sample generator

### Documentation and publishing

- fixed broken Markdown links that pointed at machine-local paths
- regenerated the GitHub Pages site with corrected document and code links
- expanded the roadmap docs with:
  - why each item matters
  - implementation notes
  - success signals

## Verification

Validated before release with:

- `python -m pytest -q`
- `npm run test:e2e:chrome`
- `python scripts/build_pages_site.py`

## Known limitations

- `multi-seed averaging` is still specified in docs but not yet implemented
- mode-specific frontend controls are still incomplete for some preference modes
- the real-backend Playwright smoke remains opt-in
