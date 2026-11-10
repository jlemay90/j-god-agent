---
name: app-continuity
description: Preserve an application's original vision and code, maintain recoverable stable and experimental versions, and produce complete, evidence-based handoffs whenever building, debugging, revising, or transferring an app between AI agents.
version: 1.0.0
---

# App Continuity & Multi-Agent Handoff

## Trigger
Use this skill whenever the owner asks to create, continue, debug, redesign, audit, export, or hand off **any app** (web, mobile, desktop, AI, or no-code), including switching among ChatGPT, Codex, Gemini/Google AI Studio, Claude, Replit, Lovable, and other agents. It applies to future projects, not only Reality Layers. Also use it when the user requests a prompt for another agent. Follow the owner's specific instructions if they override a default.

## Non-negotiable intent
Never lose the **original vision**, working implementation, rationale, rejected alternatives, or meaningful work from prior agents. Support experimentation without turning each agent's branch into a conflicting source of truth. Preserve owner decisions and distinguish requests from assumptions, recommendations and tested results. Don't claim that a repository, deployment, skill, memory, or handoff was updated unless the tool operation and readback succeeded.

## Three reference points (the owner's idea)
1. **ORIGINAL** — first available trustworthy baseline: requirements + code at a pinned tag/commit. Do not silently rewrite history or invent an absent baseline.
2. **PREVIOUS STABLE** — last accepted, tested working revision before this change, pinned by tag/commit with test evidence.
3. **CURRENT WORK** — latest agent's own experimental branch/commit, with clear provenance and unmerged status until approved.

These are three *recoverable states* in one Git repository, not three separate apps. Each agent may experiment on its own branch, preserving original and stable versions. New agents start from the latest approved stable baseline (or explicit owner-chosen branch), review pending experiments, and port useful work by reviewed merge/cherry-pick. Do not overwrite another agent's branch or merge competing proposals automatically. If Git is unavailable, preserve immutable timestamped source archives and checksums, then migrate to Git when practical.

## Before changing anything
- Identify the **canonical repository and project**; if unknown, inspect connected sources first and ask only if choosing the wrong one would cause damage.
- Read existing source, README, instructions, project docs, current branch/HEAD, tags, open PRs, pending work, and relevant user corrections.
- Capture exact purpose, user journeys, non-negotiables, design direction and accepted decisions; protect secrets and user data.
- Check for dirty/uncommitted work and build/test status. Never destroy uncommitted changes.
- Label **VERIFIED / OWNER-REPORTED / INFERRED / PROPOSED / UNKNOWN**, with dates and source links.
- Establish a safe branch (suggested `agent/<agent-name>/<task>`) before substantive modifications. Preserve ORIGINAL and PREVIOUS STABLE if they exist; otherwise explicitly record why they cannot be established.

## Documentation contract
Keep **one canonical copy** of each document per app, updating rather than duplicating:
- `PROJECT-OVERVIEW.md`: original vision, owner priorities, scope, non-goals, UX and key invariants; change requests may evolve current scope but never erase the initial intent.
- `ARCHITECTURE.md`: stack, components, API/data flows, storage, deployment, secrets handling, dependencies and environment.
- `DECISIONS.md`: dated decision log (ADR-style): context, owner decision vs recommendation, tradeoffs, alternatives/rejections, supersession, evidence.
- `CHANGELOG.md`: chronological change history, branch/commit, agent, what/why, compatibility and rollback.
- `KNOWN-ISSUES.md`: reproducible defects, severity, evidence, current workaround, owner, status.
- `TEST-REPORT.md`: commands, environment, actual results, screenshots/log references, failed and untested cases. Never invent passing tests.
- `AGENT-HANDOFF.md`: **current living handoff**, overwritten with the latest accurate state after each agent finishes; older handoffs live in Git history, optionally `handoffs/YYYY-MM-DD-agent-topic.md` only for milestone decisions that need immutable snapshots.

If files already exist under different names, update and cross-reference the existing canonical docs rather than creating duplicates. Keep docs proportional to project size; a tiny prototype may combine architecture/issues/tests until complexity warrants splitting.

## Handoff MUST contain
1. Project identity, canonical repo URL, branch, HEAD SHA, last stable tag/SHA and original baseline SHA (or explicitly unavailable).
2. Owner's **actual goal**, current scope, original intent, non-negotiables, and relevant user wording/corrections.
3. What existed before the agent; what was changed, why; precise files, commits, environment, dependencies and migrations.
4. What works **with test evidence**, what is broken/untested, reproducible errors and limitations.
5. Approved decisions vs suggested alternatives; rejected approaches and reasons; unresolved questions, risks, security/rights concerns.
6. Next **smallest executable step**, acceptance criteria, rollback instructions, whether merge/deploy/spend/outreach needs approval.
7. Links to source files, relevant prior docs/PRs/issues, screenshots, demos and logs; clear timestamps and data provenance.
8. Explicit statement of what was **not** done (not deployed, not synced, not sent, etc.).

Make the package self-contained so the next agent doesn't have to interrogate the user for context already present. Keep a concise entry summary followed by detailed references. Respect destination message limits, splitting text without losing context.

## Workflow per agent
**Inspect → Baseline → Branch → Implement smallest reversible change → Test → Compare against original vision → Update docs/logs → Handoff → Owner review → Merge/tag stable → Repeat.**

- Never present a mock or placeholder as functioning. Test the actual end-to-end user flow (mobile and desktop where relevant).
- Maintain regression tests around previously working behavior; investigate version drift before a redesign.
- For overlapping agent branches, compare diffs and evidence; choose or combine explicitly, never blind overwrite.
- No merges to stable, production deploy, purchases, external messages, secrets transfer, destructive changes or migrations without appropriate owner approval.
- When changing intent, preserve the original statement and append a dated superseding decision rather than deleting it.
- Define clear acceptance/rollback for every major change. After approved merge, tag stable and verify the target contains the intended changes.
- Keep app-specific state in that app's repo; the J Command Hub may index project links, high-level decisions, and open loops but must **not** become another copy of the source or logs.
- A file called SKILL.md in GitHub does **not** automatically install this skill into ChatGPT or any third-party agent. Explicitly load/reference the file in each environment until native installation is independently verified.

## Ready-to-use new-agent bootstrap
"Before you edit this application, read the canonical repository's app-continuity SKILL.md, PROJECT-OVERVIEW.md, ARCHITECTURE.md, DECISIONS.md, CHANGELOG.md, KNOWN-ISSUES.md, TEST-REPORT.md and AGENT-HANDOFF.md, plus current code/branches/tags. Identify ORIGINAL, PREVIOUS STABLE and CURRENT WORK by real Git references. State verified facts, unknowns, current defects, owner intent, and the single safest next change. Work on your own branch; preserve all accepted functionality; test and document modifications; update the living handoff; do not deploy or merge without approval. If any required doc is absent, create the minimum viable version from verified evidence and label gaps rather than invent history."
