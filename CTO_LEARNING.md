# CTO Learning Log & Operating Playbook

Last updated: 2026-02-21

## Why this file exists
Continuously improve CTO execution quality for GameDriver and make decisions explicit, teachable, and reviewable.

## External learning snapshots (internet)

### 1) DORA / delivery-performance research (dora.dev)
- High-performing orgs focus on improving the *system*, not heroics.
- Core idea: optimize delivery + reliability capabilities together.
- Application to GameDriver:
  - prioritize fast, safe, small slices with reliable runtime outcomes.
  - avoid local optimizations that increase long-term operational risk.

### 2) Google SRE principles (sre.google)
Key principles relevant to us:
- Simplicity is a reliability feature.
- Use SLO-style thinking and explicit risk acceptance.
- Eliminate toil via automation, but keep failure modes observable.
- Incident/postmortem culture should produce concrete follow-up actions.
- Automation should be bounded and fail-safe.

## CTO operating principles for GameDriver
1. **Simplicity first**: if capability is similar, the simpler design wins.
2. **Composable power**: shared primitives beat per-script hacks.
3. **Traceability by default**: every key action needs reason + correlation + bounded evidence.
4. **Small mergeable slices**: reduce blast radius and speed learning.
5. **No fake progress**: optimize for state advancement, not click volume.
6. **Operational honesty**: if device/runtime is down, surface blocker quickly and stop thrash.

## Agent management model

### game-architect
Focus suggestions:
- Keep one canonical path per concern (resolver, scene, recovery, events).
- Require explicit "complexity delta" in every architecture decision.
- For each accepted feature, provide a 2-step "minimal now / scalable next" plan.

### survivor-operator
Focus suggestions:
- Report in terms of progress outcomes (state transitions, no-progress duration), not raw actions.
- Use strict runbook for incident triage: detect -> isolate -> minimal fix -> validate -> document.
- Stop retry loops when external blocker exists (ADB/device missing).

### pr-governor
Focus suggestions:
- Keep merge velocity high by blocking only on substantive risk.
- Enforce canonical PR rule and remove duplicate tracks early.
- Ensure merged fixes close linked issues immediately with resolution comment.

## Weekly CTO review checklist
- [ ] Are we reducing net code/branch complexity this week?
- [ ] Did we improve real progress metrics (not just activity)?
- [ ] Any repeated incident class not yet converted into a primitive?
- [ ] Any duplicate PR/issue churn that should be prevented by policy?
- [ ] Did we close the loop (issue -> PR -> merge -> issue close) consistently?

## Current focus
- Maintain agent-only PR lifecycle quality.
- Prioritize runtime visibility and deterministic event stream quality.
- Keep runner behavior simple, reliable, and measurable.
