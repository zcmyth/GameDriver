# Issue #11: Engine ↔ Script Boundary Contract (Stage Plan)

## Decision trail

- **Problem statement:** Engine internals and game scripts are coupled through private fields and ad-hoc call patterns.
- **Proposed approach:** Introduce a minimal runtime contract (`EngineRuntime`) and migrate scripts to consume only that contract.
- **Simpler alternative considered:** Keep current structure and only document conventions (rejected: no enforcement, coupling remains hidden).
- **Complexity impact:** Medium
- **Risk impact:** Medium
- **Decision:** APPROVE (staged, contract-first)

## Contract ownership map

- **Engine core owns**
  - Device I/O and screenshot lifecycle
  - OCR + template integration
  - Runtime state signatures / stuck detection
  - Click/refresh/wait sequencing semantics
- **Game scripts own**
  - Scene interpretation and game policy
  - Action selection and fallback heuristics
  - Game-specific risk filters

## Stage plan

### Stage 1 (this PR): boundary contract + first migration slice

- Add `game_driver.contracts.EngineRuntime` protocol as explicit engine->script API surface.
- Expose `GameEngine.text_locations` as stable read-only boundary field.
- Migrate `SurvivorStrategy` to use boundary field rather than `engine._locations`.
- Add contract tests and migration notes.

Acceptance checkpoint:
- `GameEngine` satisfies `EngineRuntime` at runtime.
- `SurvivorStrategy` no longer reaches into `engine._locations`.

Rollback:
- Revert protocol + property + strategy call-site updates in one commit.

### Stage 2: dependency-direction cleanup

- Move strategy-facing abstractions into a dedicated `runtime/` (or `contracts/`) module.
- Add forbidden dependency checks (scripts cannot import device/analyzer internals).
- Introduce adapter shims only where needed.

### Stage 3: mechanical module separation

- Relayout files into explicit `core/` and `games/` boundaries.
- Keep behavior unchanged, measured with existing tests + telemetry logs.

### Stage 4: shim removal and policy hardening

- Remove temporary adapters.
- Finalize docs and enforce contract in CI/tests.

## Non-goals (Stage 1)

- No runtime-loop behavior changes.
- No broad file moves yet.
- No new game features.
