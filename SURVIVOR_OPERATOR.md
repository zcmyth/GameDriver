# SURVIVOR_OPERATOR

## Objectives
- Keep `scripts/survivor.py` running whenever a device is attached and ADB-visible.
- Optimize for **real progression** (chapter/mission/loot advancement), not just tap activity.
- Detect and recover from no-progress loops quickly.
- Leave actionable artifacts for morning diagnosis (logs, screenshots, concise incident notes).
- Keep strategy changes minimal, explainable, and aligned with `ARCHITECTURE_GUARDRAILS.md`.

## Operating Principles (Guardrail-Aligned)
1. Simplicity first: prefer clean reusable rules over one-off branches.
2. Reliability over speed: deterministic behavior and stable recovery are prioritized.
3. Safe evolution: any meaningful behavior change needs evidence, validation, and rollback path.
4. Explicit tradeoffs: document complexity/risk for major changes.
5. If core capability is missing, request an engine/framework feature (do not pile complexity into local hacks).

## Run Loop
1. **Readiness checks (startup)**
   - Confirm process lock behavior is healthy (`artifacts/survivor.lock`).
   - Confirm ADB connectivity (`adb devices -l`).
   - Confirm runner process is active (`uv run python -u scripts/survivor.py`).
   - Confirm recent event flow (`artifacts/events.jsonl` advancing timestamps).
2. **Continuous operation**
   - Run survivor loop continuously.
   - Monitor scene hints (`home`, `battle`, `skill_choice`, `offer_popup`, `unknown`).
   - Track activity vs progression:
     - Activity: refresh/click counts increase.
     - Progression: mission/challenge transitions, skill picks, battle state movement, reduced repeated same-scene taps.
3. **Health monitoring**
   - Watch loop warnings in `artifacts/runner.log`:
     - `Detected stuck/cycle state`
     - `Detected persistent loop ... escalating recovery`
   - Watch engine metrics snapshots in `events.jsonl` for plateaus (e.g., high refresh/click with static scene/action pattern).
4. **Daily operator output**
   - Keep incident summaries in `artifacts/incidents_YYYY-MM-DD.md`.
   - Record recurring failure patterns + candidate fixes.

## Stuck-Handling Policy
Use incident workflow whenever no-progress loop is detected.

### Trigger conditions
- Repeated persistent-loop warnings.
- Repeated same target tap with no scene change.
- Event stream shows high activity but low semantic progress.

### Incident workflow (required)
1. **Collect evidence**
   - Save timestamps, warning excerpts, and screenshot paths from `artifacts/stuck/` or `artifacts/watchdog/`.
   - Note current scene hints and repeated decisions.
2. **Diagnose**
   - Classify issue: OCR miss, wrong priority rule, false scene inference, navigation dead-end, or engine capability gap.
3. **Patch minimally**
   - Apply smallest clean rule adjustment.
   - Avoid feature-specific branching in core loop unless unavoidable.
4. **Validate improvement**
   - Verify warning frequency drops and progression signals improve.
   - Confirm no regression to purchase-risk or dead-end interactions.
5. **Persist notes**
   - Append a short incident note with cause/fix/result.

## Escalation Matrix
- **L1 (auto-recover):** transient loop (single/few warnings)
  - Action: existing recovery tap/back/home cycle.
  - Exit: progression resumes.
- **L2 (operator tune):** repeated loop cluster without hard crash
  - Action: inspect logs/events/screenshots; adjust strategy priorities/thresholds minimally.
  - Exit: measurable reduction in repeated-loop warnings.
- **L3 (major design decision):** recurring pattern needing architecture change
  - Action: submit architecture review block with:
    - problem,
    - proposed change,
    - simpler alternative considered,
    - complexity/risk impact,
    - decision request (APPROVE/REVISE/REJECT).
- **L4 (engine/framework feature gap):** missing primitive prevents clean fix
  - Action: raise feature request to game-architect instead of adding local complexity.

## When to Request Engine Features (instead of local hacks)
Request engine/framework capability when any of the following is true:
- Reliable progression detection needs a shared primitive not present (e.g., semantic state transitions).
- Repeated local exceptions/special-cases would otherwise be added to strategy.
- Deterministic recovery requires core support (retry policy, state machine hooks, observability).
- Multiple games would benefit from the same capability.

Use this template:
- **Problem statement:**
- **Proposed approach:**
- **Simpler alternative considered:**
- **Complexity impact:** Low / Medium / High
- **Risk impact:** Low / Medium / High
- **Decision:** APPROVE / REVISE / REJECT
- **If rejected, minimal viable alternative:**

## Current Readiness Checklist
- [ ] Runner process active
- [ ] Device attached and authorized
- [ ] Event stream advancing
- [ ] Loop warning rate acceptable
- [ ] Incident log updated for latest recurring issue
