# System Test Specification

## 1. Document Role

This document defines the verification contract for the research platform. Its purpose is to ensure correctness, comparability, and reproducibility rather than only basic functional behavior.

Related documents:

- [system_specification.md](system_specification.md)
- [pre_implementation_blueprint.md](pre_implementation_blueprint.md)

## 2. Test Objectives

The test suite must demonstrate that:

- the platform behaves correctly under normal flows
- plug-in components can be swapped without breaking orchestration
- deterministic replay is trustworthy
- schema evolution remains manageable
- failures are surfaced in a controlled and recoverable way

## 3. Test Categories

The system must include:

- unit tests
- integration tests
- end-to-end tests
- deterministic replay tests
- regression tests for schemas and exports

## 4. Test Environment Strategy

The suite should distinguish between:

- pure logic tests with no model dependency
- service tests with mocked generation
- limited end-to-end runs with lightweight fixtures
- explicit real-model smoke tests run separately from the default test suite

Real image generation should not be required for most tests.

## 5. Unit Tests

### 5.1 Steering representation tests

Verify:

- prompt encoding returns expected shape
- basis construction returns correct dimensions
- `E(z) = E0 + U z` applies valid tensor shape rules
- trust-region clipping behaves correctly
- anchor penalties reduce drift where expected
- invalid steering dimensions fail clearly

### 5.2 Sampler tests

Verify:

- candidate count is correct
- candidates respect trust radius
- orthogonal exploration reduces alignment with exploit direction
- deterministic sampling works under fixed RNG state
- diversity filtering removes near duplicates
- role tags are assigned consistently

### 5.3 Feedback normalization tests

Verify:

- ratings normalize correctly
- rankings derive pairwise preferences correctly
- invalid ranking payloads are rejected
- duplicate selections are rejected where required
- optional critique text is preserved
- skip or uncertain actions normalize correctly

### 5.4 Updater tests

Verify:

- winner-copy selects the winning candidate exactly
- averaging updater interpolates correctly
- linear updater moves in the expected direction
- pairwise updater handles symmetric cases correctly
- Bayesian updater changes uncertainty as expected
- trust-region clipping constrains updates

### 5.5 Seed policy tests

Verify:

- fixed-per-round uses the same seed
- validation candidates receive alternate seeds when configured
- seed manifests are stored for all candidates
- missing seed metadata is treated as a failure

### 5.6 Persistence and schema tests

Verify:

- sessions persist immutable config snapshots
- rounds persist in correct order
- candidate and feedback foreign-key relationships remain valid
- replay exports serialize required fields

## 6. Integration Tests

### 6.1 Session lifecycle test

Flow:

1. create experiment
2. create session
3. request first round
4. submit feedback
5. request next round
6. verify progression and persistence

### 6.2 Generation pipeline test

Use a lightweight mock or tiny test pipeline when full generation is too expensive.

Verify:

- embeddings flow from encoder through steering to generator
- generation failures are captured and surfaced
- successful candidates still persist when one candidate fails

### 6.3 Replay integrity test

Verify:

- exported replay matches stored rounds and feedback
- images and metadata align correctly
- round order is stable

### 6.4 Strategy plug-in test

Verify:

- samplers can be swapped by config
- updaters can be swapped by config
- controller logic does not depend on one concrete strategy implementation

### 6.5 API contract test

Verify:

- endpoints accept expected payloads
- structured errors are returned on invalid input
- response schemas remain stable

## 7. End-to-End Tests

Using browser automation or HTTP-level testing, verify:

- a user can create an experiment from the UI
- a user can start a session
- a user can provide at least two feedback modes
- a user can proceed to the next round
- a user can open replay for a completed session
- replay export API returns the expected round and feedback history
- recoverable errors are shown clearly

## 8. Deterministic Replay Tests

These tests are critical.

Given:

- fixed prompt
- fixed experiment configuration
- fixed RNG seeds
- mocked or deterministic generation backend

The replay must reproduce:

- the same candidate proposals
- the same candidate order
- the same update steps
- the same persisted metrics
- the same round summaries

## 9. Regression Tests

Regression coverage should include:

- historical export loading
- schema migration behavior
- known edge-case prompts
- known edge-case feedback payloads
- previously fixed replay bugs

## 10. Failure-Mode Tests

The test suite should verify controlled behavior for:

- one-candidate render failure
- duplicate feedback submission
- premature next-round generation while feedback is still pending
- invalid ranking payloads
- export generation failure
- database write interruption
- resume after crash

## 11. Test Fixtures

Required fixtures:

- deterministic prompt embedding fixture
- synthetic candidate set fixture
- fake user feedback fixture
- mock image generator fixture
- small replay log fixture
- schema snapshot fixture
- frontend/backend trace capture fixture where needed

## 12. Acceptance Criteria

The prototype is acceptable when:

- all unit tests pass
- core integration tests pass
- deterministic replay tests pass
- one sampler and one updater can be swapped by configuration only
- the UI supports at least two feedback modes
- exports can be generated and replayed
- browser smoke coverage includes replay export retrieval
- failure-mode behavior is covered for the major recoverable errors

## 13. Test Reporting Expectations

Test reporting should make it easy to identify:

- failing component area
- failing scenario
- whether the failure breaks replay trustworthiness
- whether the failure is isolated or systemic

## 14. Summary

The test suite is part of the research method, not an implementation afterthought. If replay, schema stability, and strategy interchangeability are not verified, the platform cannot support reliable experimental conclusions.
