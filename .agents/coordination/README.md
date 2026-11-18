# Multi-agent coordination — phase 1 preflight (draft)

Source of truth: https://github.com/jlemay90/j-god-agent/issues/2
Canonical app-continuity and handoff policy: ../skills/app-continuity/SKILL.md

This directory implements a small test utility. It is **not** a second policy, task ledger, or memory database.

## Goal and boundaries

The read-only preflight.mjs checks a proposed agent change against *supplied* snapshots of current Git head, active file claims, and Hub record revisions. It blocks exact-file conflicts, stale Git baseline, stale or unknown Hub record revisions, missing handoff, unsafe scope, and requests to deploy or merge. It **does not** reserve a file, perform a write, lock the Hub, validate source freshness, contact GitHub, or authorize deployment.

## Run

Requires Node.js 20+. From the repository root:

    node --test .agents/coordination/preflight.test.mjs
    node .agents/coordination/preflight.mjs proposal.json verified-state.json

Proposal fields: agent, task, isolated branch (prefix agent/), action set to "propose", a real 40-character baseSha, explicit files, recordUpdates with key/expectedRevision for Hub changes, and a handoff with summary, tests, unknowns and nextStep.

Verified-state fields: currentBaseSha from a fresh Git read, activeClaims listing branch/status/files, and recordRevisions from an authenticated source. The preflight refuses missing claims/revisions but **cannot authenticate** a snapshot supplied by an agent.

## Required before actual parallel writes

1. Introduce an authoritative shared claim ledger with authentication, expiry, atomic compare-and-set or lease operations and an auditable identity. Static JSON cannot prevent races.
2. Recheck actual Git head and Hub revision immediately before *every* write, with atomic rejection of stale changes and recoverable prior versions. Exact-file detection does not catch semantic or directory-level conflicts.
3. Install protected merge gates and required checks before describing the policy as enforced; no GitHub branch protection or CI enforcement is added by this draft.
4. Require owner approval for production, privacy, financial changes or consequential overwrites. Verify live Sites deployment separately from GitHub/Replit; these are distinct runtimes.
5. Run two real agents on isolated branches, exercise intentional overlap and stale-revision cases, and verify fresh-session handoff recovery and owner-only controls. Record evidence in the existing living AGENT-HANDOFF.md.

Keep credentials, sensitive Hub records and private owner context out of this public repository.

**Status:** Draft logic simulation only. No agents dispatched, locks installed, merges, deployments, production changes or live Hub writes.
