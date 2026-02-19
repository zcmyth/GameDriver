# Engine ↔ Script Boundary Refactor (PR-1 Skeleton)

Issue: #11  
Agent: game-architect

## Goal
Create a clear separation between core game engine and per-game scripts through a contract-first boundary.

## PR-1 Scope (contract-first, no behavior change)
1. Define interface contract between engine core and game scripts.
2. Define ownership map (what must live in engine vs scripts).
3. Define forbidden dependency directions and migration invariants.
4. Define staged migration plan and rollback plan.

## Boundary Contract (minimum surface)
Game scripts may consume only:
- Scene observation API (read-only structured scene data)
- Action primitives (tap/click/swipe/text actions)
- Deterministic retry/timeout helpers
- Decision logging + telemetry emitters

Game scripts must own:
- Game-specific policy (priorities, heuristics, fallback decisions)
- Scene-specific selectors and language/domain mappings
- Progression/strategy state machines specific to a game

Engine core must own:
- Device/runtime orchestration
- Generic interaction primitives
- Generic no-progress/time-budget enforcement primitives
- Cross-game observability contracts and shared error taxonomy

## Dependency Rules
- Allowed: `scripts/* -> engine/core/*`
- Forbidden: `engine/core/* -> scripts/*`
- Forbidden: cross-game script imports (`scripts/gameA -> scripts/gameB`)

## Migration Slices
- PR-1: contract + ownership + invariants doc (this PR)
- PR-2: add adapter/shim layer for old script entrypoints
- PR-3..N: move modules by capability (observation, actions, loop guards)
- Final: remove adapters; enforce lints/checks for forbidden imports

## Invariants
- Deterministic ordering/retry semantics in engine loops must not regress.
- No net loss in structured decision logs.
- Strategy-level behavior remains unchanged until specific migration PR states otherwise.

## Risk / Complexity
- Complexity: High (cross-cutting structure)
- Risk: Medium-High (dependency and regression risk)
- Mitigation: small staged PRs + adapter period + explicit checkpoints

## Rollback
- Keep compatibility adapters until migrations stabilize.
- If migration slice regresses behavior, revert slice PR while preserving contract docs.

## Acceptance Checkpoints
- Contract document approved and referenced by migration PRs.
- Every migration PR states moved modules and forbidden dependency checks.
- Adapter removal only after all target flows pass existing tests.
