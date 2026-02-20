# Agent Workflow Policy (Mandatory)

This repo uses a strict multi-agent workflow.

## 1) Branching + worktree (required)
- Each agent must work in its **own git worktree**.
- Each agent must use its **own branch**.
- Never develop directly on `master` (or `main`).

Suggested branch naming:
- `agent/<agent-name>/<short-task>`

Required worktree path:
- `worktrees/<agent_name>/<feature_name>`

Cleanup ownership:
- The agent (or person) who created a worktree is responsible for cleaning it up after the PR is merged/closed.

## 2) No direct commits to master/main
- Direct commits on `master`/`main` are prohibited.
- All changes must land through PR.

## 3) Issue-first development
- Every feature request starts with a GitHub Issue.
- The issue must include:
  - Problem statement
  - Proposed change
  - Acceptance criteria
  - **Requesting agent name** (required)

Issue title convention:
- `[agent:<name>] <feature title>`

## 4) PR requirements
- PR must reference an existing issue (`Closes #<id>` or `Refs #<id>`).
- PR must include **Agent Name**.
- PR must explain tradeoffs and complexity impact.

## 4.1) Markdown formatting rule (GitHub)
- Do not pass escaped newline text (literal `\n`) in issue/PR bodies.
- Write body content to a markdown file and submit with `--body-file`.
- Before submit, quickly verify rendered body has real line breaks/headings.

PR title convention:
- `[agent:<name>] <short change summary>`

## 5) Architecture gate
- Follow `ARCHITECTURE_GUARDRAILS.md`.
- If a feature risks complexity growth, route to the game-architect decision path.

## 6) Default command sequence
1. Create issue
2. Create branch + worktree
3. Implement + test in agent worktree
4. Open PR referencing issue and agent name
5. Merge via PR only
