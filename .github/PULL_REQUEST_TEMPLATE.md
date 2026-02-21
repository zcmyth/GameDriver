## Summary
- What changed?
- Why now?

## Linked issue
- Refs #<id> (or Closes #<id>)

## Agent
- agent: <name>

## Governance Rubric (required)
### Simplicity Delta
- Score: `+1 | 0 | -1`
- What got simpler?
- If complexity was added, why unavoidable and how contained?

### Composability Gain
- Reusable primitive/boundary improved:
- Duplication reduced:
- Downstream slice/use-case unlocked:

### Traceability Coverage
For decision/action paths touched by this PR, confirm coverage:
- `reason` (typed stable enum):
- `correlation_id` (attempt/request lineage):
- `event` (typed event/category):

If partial, list gap + follow-up issue:
- Gap:
- Follow-up issue: #

## Validation
- [ ] Tests added/updated
- [ ] Relevant tests pass locally
- [ ] Rollback/failure mode considered

## Risk & blast radius
- Expected impact (low/med/high):
- User-visible risk:
- Operational/debugging risk:

## PR Governor policy note
Rubric omissions are warned for merge-velocity.
Blocking is reserved for substantive risk (correctness/operability/architecture):
- missing/incorrect traceability on touched decision paths
- unjustified high-blast-radius complexity increase
- composability regression causing duplicate stacks
- failure diagnosability regression
