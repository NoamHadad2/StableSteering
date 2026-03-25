# StableSteering

StableSteering is a research documentation repository for an interactive system that studies prompt-embedding steering for text-to-image diffusion models.

The current repository contains the specification set used to define the project before implementation:

- [Motivation](./docs/motivation.md)
- [Theoretical Background](./docs/theoretical_background.md)
- [System Specification](./docs/system_specification.md)
- [System Test Specification](./docs/system_test_specification.md)
- [Pre-Implementation Blueprint](./docs/pre_implementation_blueprint.md)
- [Documentation Audit Ledger](./docs/document_audit.md)

## Repo Status

This repository currently contains documentation only. It is intended to be the foundation for a future implementation of the research platform.

## Recommended Reading Order

1. [Motivation](./docs/motivation.md)
2. [Theoretical Background](./docs/theoretical_background.md)
3. [System Specification](./docs/system_specification.md)
4. [System Test Specification](./docs/system_test_specification.md)
5. [Pre-Implementation Blueprint](./docs/pre_implementation_blueprint.md)

## Legacy Source

The original combined specification is preserved as:

- [Legacy Combined Spec](./docs/system_spec_legacy_combined.md)

## Next Suggested Steps

- finalize implementation defaults in the blueprint
- add a decision log for locked choices
- scaffold the FastAPI backend and simple HTML frontend
- implement the storage, replay, and test foundation first
