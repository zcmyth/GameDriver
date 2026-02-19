# Engine Progress Signal Plan (Issue #8)

## Summary
Introduce a stable, low-noise engine progress token API for no-progress detection that is robust to OCR churn and UI refresh loops.

## Proposed API (initial)
- `compute_progress_token(frame_bundle, window_cfg) -> ProgressSignal`
- `ProgressSignal`:
  - `token: str` (stable hash over structural anchors)
  - `changed: bool` (vs previous debounced token)
  - `confidence: float` (0..1)
  - `diagnostics: { anchors_used, ocr_regions_used, debounce_window_ms }`

## Architecture Rationale
- Moves progress semantics from strategy-local heuristics into core engine.
- Promotes composability and consistent observability across scenes/games.
- Allows strategies to consume one stable signal instead of bespoke loop-breakers.

## Complexity / Risk
- Complexity: Medium-High (cross-cutting signal pipeline + calibration)
- Risks:
  - false progress (over-sensitive anchors)
  - missed progress (over-debounced token)
  - game-specific UI variance
- Mitigations:
  - conservative defaults
  - per-scene diagnostics
  - phased rollout (opt-in)

## Rollback Plan
- Feature-flag all strategy consumption (`engine_progress_signal_enabled=false` by default in initial merge).
- Keep existing no-progress fallback path active.
- Disable flag to revert behavior without code rollback.

## Test Plan
- Unit: token stability under OCR text churn / minor redraw noise.
- Unit: token change under meaningful scene transitions.
- Integration: known `skill_choice` loop and escalation behavior with/without signal.
- Metrics: emit token-change rate, confidence histogram, no-progress escalation triggers.
