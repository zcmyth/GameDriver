# AGENT.md

Repository-level operating contract for all agents.

## 1) Goals (north star)
Build and operate GameDriver so it is:
1. **Easy to use** (low-ceremony script API)
2. **Flexible + powerful** (composable engine primitives)
3. **Debuggable + traceable** (typed events, reason codes, correlation IDs)

## 2) Mandatory workflow
1. **Issue-first**: every change starts from a GitHub issue.
2. **One canonical PR per slice**: no parallel PRs for the same issue scope.
3. **Per-agent worktree + branch**:
   - Worktree: `~/worktrees/<repo>-<agent>-<task>`
   - Branch: `agent/<agent>/<task>`
4. **Rebase before PR update**:
   - `git fetch origin`
   - `git rebase origin/master`
   - run validation
   - push (`--force-with-lease` only when needed)
5. **PR follow-through**:
   - respond to all comments
   - if no external response >10 min after meaningful update, post one concise polite ping
6. **Issue closure**:
   - when fix is merged/completed, close linked issue with resolution note + PR link.

## 3) Engineering principles
1. **Simplicity first**: same capability with less code/branching.
2. **Composable power**: shared primitives over strategy-local hacks.
3. **Quality-first pragmatism**: block on substantive risk/quality; warn on hygiene gaps by default.
4. **Traceability by default**: stable enums, bounded evidence, deterministic behavior.
5. **Small mergeable slices**: one intent per PR, tests + rollback + measurable AC.

## 4) Runtime policy
- Runtime should track latest `master` after updates (controlled restart).
- If ADB device is missing: **stop runner/watchdog and do not auto-restart** until explicit user start request.
- Monitor real progress (state/transition outcomes), not only activity (tap counts).

## 5) Current priority tracks
1. API simplification (`TargetSpec`, script ergonomics)
2. Trace/event coverage (reason/correlation/event envelope)
3. Deterministic replay utility from events
4. Recovery/state policies for no-progress loop prevention

## 6) Definition of Done (per slice)
A slice is done only when all are true:
- linked issue + canonical PR
- acceptance criteria met
- tests and evidence attached
- rollback note included
- related issue closed (or explicitly scoped follow-up opened)
