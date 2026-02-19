# ARCHITECTURE_GUARDRAILS

Purpose: enforce simple, composable, and reliable engine evolution.

## 1) Design Principles (Non-Negotiable)

1. **Simplicity first**
   - Prefer fewer concepts over clever abstractions.
   - Reject feature-specific branches when a shared primitive can solve it.
   - No duplicate logic paths for the same behavior.

2. **Composability over special-casing**
   - Build reusable primitives (systems, components, events, policies).
   - New features should be assembled from existing building blocks where possible.
   - API surfaces must remain orthogonal and predictable.

3. **Safe evolution**
   - Significant changes require: tests, observability, rollback plan.
   - Migrations must be explicit and reversible.
   - Backward compatibility decisions must be documented.

4. **Explicit tradeoffs**
   - Every change states complexity cost and maintenance impact.
   - Hidden coupling is a defect.
   - If speed and reliability conflict, reliability wins by default.

5. **Reliability over speed**
   - Avoid non-deterministic behavior unless explicitly required.
   - Flakiness budget is near-zero for core runtime loops.
   - Performance optimizations must prove value with measurements.

---

## 2) Feature Acceptance Checklist

A change is not ready unless all applicable items are satisfied.

### Problem & Scope
- [ ] Problem statement is concrete (who/what breaks, expected behavior).
- [ ] Scope is bounded; non-goals are explicit.
- [ ] Existing primitives were evaluated before adding new ones.

### Architecture Quality
- [ ] Solution reuses or extends shared primitives.
- [ ] No feature-specific spaghetti in core loops.
- [ ] Interfaces remain coherent (no leaky abstractions).
- [ ] Coupling and invariants are documented.

### Safety & Reliability
- [ ] Unit/integration tests cover happy path + edge/failure paths.
- [ ] Determinism impact assessed (timing/order/retry semantics).
- [ ] Rollback path exists (flag, config gate, or reversible migration).
- [ ] Failure modes are explicit (timeouts, retries, degradation behavior).

### Operability
- [ ] Telemetry added (metrics/logs/traces/events as required below).
- [ ] Alerting/SLO impact assessed for production-facing runtime features.
- [ ] Runbook notes included for debugging and rollback.

### Performance
- [ ] Baseline and post-change measurements included.
- [ ] Resource impact (CPU/memory/IO/network) quantified.
- [ ] No premature optimization without evidence.

### Change Management
- [ ] Incremental rollout plan (dark launch / staged enablement) for risky changes.
- [ ] Compatibility/migration plan documented.
- [ ] Technical debt introduced (if any) is logged with owner + due date.

---

## 3) Rejection Criteria

Reject immediately if any of the following apply:

1. Duplicates existing behavior with slight feature-specific variation.
2. Adds special-case branching in core runtime where a generic primitive is possible.
3. Ships significant runtime behavior without tests + telemetry + rollback.
4. Increases flakiness (timing sensitivity, race risk, nondeterministic ordering) without compelling measured value.
5. Introduces hidden global state or implicit cross-system coupling.
6. Expands API surface with one-off verbs/types that do not generalize.
7. Uses “temporary” hacks with no owner/date/exit criteria.
8. Claims performance improvement without benchmark evidence.

Default disposition for promising but messy proposals: **REVISE**.

---

## 4) Good vs Hacky Change Examples

### Example A: New runtime trigger
- **Good**: Add a generic `TriggerPolicy` interface with composable conditions and shared evaluation pipeline; new trigger implemented as policy config.
- **Hacky**: Add `if (featureX)` branches in update loop and a bespoke trigger evaluator only used by one mode.

### Example B: Retry behavior
- **Good**: Reuse centralized retry/backoff utility with standard jitter/limits and telemetry hooks.
- **Hacky**: Inline retry loops in three call sites with inconsistent limits and silent failures.

### Example C: Feature rollout
- **Good**: Guard by feature flag, emit adoption/error metrics, provide one-command rollback.
- **Hacky**: Hard-enable in production with manual code revert as rollback plan.

### Example D: Data model extension
- **Good**: Extend shared schema with versioned migration and compatibility reader.
- **Hacky**: Add optional ad-hoc fields parsed differently per subsystem.

---

## 5) Required Telemetry for Runtime Features

For any runtime feature affecting execution path, reliability, or performance:

### Metrics (mandatory)
- Success/failure counts (`feature_exec_total`, `feature_exec_failed_total`)
- Latency distribution (p50/p95/p99)
- Retry counts and terminal failure counts
- Resource usage deltas when relevant (CPU, memory, queue depth)

### Structured Logs (mandatory)
- Correlation/request/session id
- Feature/version/flag state
- Decision points (selected strategy/policy)
- Failure reason codes (stable enums, not free-form only)

### Tracing (required for async or multi-step flows)
- Parent/child spans across subsystem boundaries
- Explicit annotations for retries, timeouts, fallbacks

### Events (recommended)
- Lifecycle events: started, succeeded, degraded, failed, rolled_back
- Config/flag transition events

### Alerting Hooks (required for prod-critical features)
- Error-rate threshold alerts
- Latency regression alerts
- Saturation/backlog alerts where queues are involved

### Telemetry Quality Bar
- Names and labels are stable and documented.
- Cardinality is bounded.
- Dashboards exist before broad rollout.

---

## 6) Architecture Decision Review Template (Use for all feature requests)

- **Problem statement:**
- **Proposed approach:**
- **Simpler alternative considered:**
- **Complexity impact:** Low / Medium / High
- **Risk impact:** Low / Medium / High
- **Decision:** APPROVE / REVISE / REJECT
- **If REJECT, minimal viable alternative:**
- **Debt introduced (if any):** owner, due date, removal criteria

---

## 7) Architecture TODO / Debt Register

Track only concrete, actionable debt.

1. **ID:** ARCH-001  
   **Title:** Unified ClickTargetResolver (text + image fallback)  
   **Why debt exists:** Current click behavior is primarily text-driven; introducing image-based fallback risks branching logic unless unified under a single resolver abstraction.  
   **Risk:** Medium (flakiness + maintenance if implemented ad hoc)  
   **Owner:** Engine team  
   **Due date:** Before enabling image-click by default in production  
   **Exit criteria:** Single resolver interface with deterministic strategy order, confidence thresholds, telemetry, and tests across resolution scaling cases.

Entry format:
- ID:
- Title:
- Why debt exists:
- Risk:
- Owner:
- Due date:
- Exit criteria:
