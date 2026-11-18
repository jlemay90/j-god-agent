# AGENT-HANDOFF — J Command OS multi-agent coordination

Updated: 2026-11-17 (America/Chicago)
Status: DRAFT / unmerged / not deployed
Canonical engineering issue: https://github.com/jlemay90/j-god-agent/issues/2
Review PR: https://github.com/jlemay90/j-god-agent/pull/5
Repo: https://github.com/jlemay90/j-god-agent
Working branch: agent/coordination-preflight-20261117
Starting main SHA: a983463a153b6215150509b084325b10c1baf97e
Last verified implementation SHA (before this handoff commit): a5e128c12ccd2dfb2f644dc5ed34849b2bb939b4
Original project baseline / last accepted deployed Sites SHA: NOT ESTABLISHED. This is not a live deployment branch.

## Owner goal and current scope

Keep the full J Command OS vision intact. Allow specialist agents to work concurrently without losing information, overwriting work, or silently touching production. Owner authorized an isolated implementation branch and draft PR for a controlled coordination test, **not** a merge, deploy, real-world data change, or unrestricted write access.

Read the existing app-continuity policy: .agents/skills/app-continuity/SKILL.md
Do not introduce a rival canonical policy, new private memory database, or public personal context.

## Verified starting state and dependencies

- Issue #2 remains open and defines agent claims, isolated changes, handoffs, stale-revision protection, review and deployment gates.
- Existing PR #1 (capability router) and PR #3 (Zeus context budget) both touch hub-site/worker/zeus.js; PR #3 is based on PR #1 (five commits ahead at inspection). They are separate from this proposed change.
- PR #4 is a separate notebook research workflow.
- GitHub main has the canonical continuity skill; the living root AGENT-HANDOFF.md did not exist on main when this work began.
- The live private Sites app, Replit service, and this GitHub repository are distinct systems; deployment and current runtime health were not verified.

## What changed

Proposed only, on the branch:
- .agents/coordination/preflight.mjs — pure read-only guard for exact file claims, Git baseline SHA, Hub revision map, handoff requirements, input safety, and no direct deploy.
- .agents/coordination/preflight.test.mjs — ten deterministic synthetic agent proposals and failure scenarios.
- .agents/coordination/README.md — usage and explicit limits.
- AGENT-HANDOFF.md — this single living handoff document.

## Tests / evidence

- Local Node.js v22.16.0, command: node --test .agents/coordination/preflight.test.mjs
- Local matching implementation before GitHub upload: 10 passed, 0 failed.
- Synthetic only: tests simulated independent Agent A/Agent B claims, same-file conflicts, stale Git and Hub revisions, missing state/handoff, unauthorized deployment, malformed claims.
- Not yet verified: CI execution of PR commit, real two-agent execution, atomic claims/leases, protected branch checks, merge gates, actual Hub revision guards, rollback behavior and production authentication.

## Risks and unknowns

- Preflight accepts caller-provided snapshots and cannot establish their freshness or authenticity.
- It has no atomic enforcement; two real writers could still race.
- Exact paths miss directory and semantic conflicts.
- Public repo must not contain private owner records, keys, or secrets.
- No action should be interpreted as authorization to merge/deploy or change connected Hub records.

## Next executable step / acceptance

1. Read back PR #5 and check committed files and current branch SHA; review code for input validation and zero writes.
2. Request owner review of the draft. Only with further authorization should the next agent design and test an authoritative shared claim ledger with atomic revision guards and protected merge checks.
3. Subsequently run two **actual** agents, including a deliberate collision and stale Hub revision; prove both histories survive and no live deployment occurs without owner approval.

No branches other than this isolated branch were modified. No merge, deploy, secret transfer, Hub write, or external message occurred.
