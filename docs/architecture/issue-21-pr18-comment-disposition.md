# Issue #21: Disposition of Remaining PR #18 Inline Comments

Context: PR #18 was merged to unblock Stage-1 boundary establishment for #11. This note explicitly dispositions the remaining inline comments raised during that review.

## Comment dispositions

1. **"Let's hide the min_confidence"**
   - **Decision:** DEFER (tracked)
   - **Rationale:** Current survivor strategy uses explicit thresholds extensively. Removing/tucking this knob in Stage-1 would force broad behavior changes.
   - **Plan:** Centralize threshold policy in a later stage once script rules are refactored to a policy/config layer.

2. **"Let's merge functions for image/template and text"**
   - **Decision:** DEFER (tracked)
   - **Rationale:** A safe unification requires a deterministic resolver abstraction (see ARCH-001) to avoid feature-specific branching and flakiness.
   - **Plan:** Handle in dedicated design slice under #11 Stage-2/3.

3. **"Specify the behavior of this" (debug/diagnostic methods)**
   - **Decision:** ADDRESSED
   - **Action:** Added explicit method-level contract semantics in `src/game_driver/contracts.py` docstrings.

4. **"sleep is better. wait sounds like we want to wait for something to happen."**
   - **Decision:** ADDRESSED (clarified)
   - **Action:** Documented `wait(seconds)` as passive delay (sleep semantics) to remove ambiguity.
   - **Follow-up:** Rename/alias can be considered in compatibility-safe pass.

5. **"Make sure to document the difference between click and try_click"**
   - **Decision:** ADDRESSED
   - **Action:** Added explicit behavior semantics for `click_*` vs `try_click_*` in contract docstrings.

6. **"this is too complicated. let's remove this one." (cycle-stuck helper)**
   - **Decision:** RETAIN FOR NOW (explicit rationale)
   - **Rationale:** `is_cycle_stuck` is currently used by survivor strategy; removing in Stage-1 would increase migration risk.
   - **Plan:** Re-evaluate after boundary cleanup and strategy simplification in later stage.

## Validation

- No behavior changes in runtime loop.
- This change is contract-clarification/documentation scoped.
