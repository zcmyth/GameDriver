# Event Stream v1 Contract (Canonical)

Owner: game-architect  
Issue linkage: Refs #38, Refs #40 (builds on closed #30)

## Purpose
Define a stable, typed event envelope for runtime visibility so operators and downstream tooling can reason about state/action transitions consistently.

This document is the canonical contract for the current in-process event stream emitted by `GameEngine._emit`.

## Envelope fields

- `ts`: event timestamp (float seconds)
- `correlation_id`: monotonic per-runtime sequence id
- `event`: event category
- `state_before`: bounded snapshot string
- `action`: bounded action name/string
- `state_after`: bounded snapshot string
- `reason`: stable reason enum (normalized)
- `match_evidence`: bounded structured evidence object

## Stable reason enum set (v1)

- `state_changed`
- `no_state_change`
- `no_match`
- `success`
- `miss`
- `attempt`
- `unknown`

Notes:
- Free-form reason text must be normalized into one of the above.
- New reason values require schema update + compatibility review.

## Bounded payload policy

To preserve reliability and avoid high-cardinality drift:

- Long strings are truncated.
- Nested evidence payload is size-limited.
- Full screenshots/raw OCR blobs are **not** embedded in-event.
- Heavy artifacts should be referenced out-of-band when needed.

## Failure semantics

Event emission is fail-safe and non-blocking:

- Listener exceptions are isolated and must not crash or stall runtime loops.
- Listener failures are observable via logs/metrics.

## Visibility gap follow-ups

Current v1 establishes canonical in-process envelope emission. Remaining visibility work is tracked by open issues:

- #38: telemetry contract standardization and consistency adoption
- #40: reliability/progress metrics and monitoring thresholds
- #31: bounded progress metric model over canonical events

## Rollout / rollback

- Rollout remains incremental by feature slice.
- If regressions appear, revert the specific slice PR; keep core runtime deterministic.

## Validation expectations

- Schema tests for required fields + reason normalization.
- Ordering/correlation monotonicity tests.
- Listener failure-path tests.
