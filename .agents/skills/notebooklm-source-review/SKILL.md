---
name: notebooklm-source-review
description: Review owner-provided NotebookLM/Gemini Notebook source material, trace original project vision and decisions, compare with current implementations, and propose evidence-based corrections without duplicating canonical data.
version: 0.1.0
---

# NotebookLM Source Review (read-only bridge)

## Trigger
Use this skill when the owner asks to inspect a NotebookLM (also called Gemini Notebook), analyze its notes/sources, compare an early notebook to a current app or project, or turn NotebookLM research into a trustworthy project handoff. Apply alongside the existing `.agents/skills/app-continuity/SKILL.md` for app work. This skill is a review workflow, **not a credential or a live NotebookLM API connector**.

## Access rules
1. Discover whether a NotebookLM connector or owner-authorized browser tab is actually available. Do not claim that a skill itself enables private notebook access.
2. If a user provides a public/shared notebook URL, use only an available authorized reader and report whether the *actual sources* were accessible. A login wall or notebook title is not source content.
3. If private access is unavailable, request **one** safe handoff: a selected notebook source/report exported to Google Docs/Drive, an uploaded PDF/text file, or a copied source list plus relevant notes. Prefer private exports over changing the notebook's sharing settings.
4. Never change sharing to public, copy a private notebook into a public repository, solicit credentials/cookies, or silently add new data connectors. If the source includes sensitive personal information, limit reads and output to the owner's requested scope.

## Review workflow
1. **Identity:** Establish the notebook's exact title, source author/date, original source list, and relevant creation/modification dates where actually available. Do not infer origins from later summaries alone.
2. **Read:** Read the requested notebook's actual original materials. Label exports, AI-generated NotebookLM summaries, and secondary notes separately. If sources are missing or clipped, state it.
3. **Reconstruct:** Extract the earliest supported project objective, user's original wording where available, critical design principles, roles, constraints, and unresolved questions. Preserve chronology; distinguish proposed vs accepted decisions.
4. **Compare:** Consult current canonical project records and GitHub/source documents through authorized connectors. Compare **original vision / current verified state / differences / proposals**, linking each claim to exact source files and dates. Do not assume a PR merge equals deployment or assume one notebook is the only origin of a long-running project.
5. **Challenge:** Identify attractive but unsupported claims, invented capabilities, security/privacy risks, duplicates, old prompts that could bloat active context, and missing evidence. Suggest source-backed high-leverage improvements rather than reflexive praise.
6. **Report:** Produce a short verdict, source inventory, evidence table, what we should preserve, potential drift, recommended next small test, and limits/unknowns. If user asked for teaching materials, produce concise NotebookLM-ready prompts and exercises.
7. **Write-back:** Ask for approval before altering canonical memory, publishing, changing app source, merging/deploying, or sharing sensitive data. If authorized, update the existing source-of-truth record in place and verify readback, preserving original evidence and the superseding decision.

## Context budget and provenance
- Never send an entire notebook, all past conversations, or full project-memory archives as a single system prompt by default.
- Pass a compact topical context packet with exact source links/IDs, timestamps, decisions, unknowns, and excerpts within a measured budget.
- NotebookLM is a **research/learning surface**, not automatically J Command Hub's operational memory or authoritative repository.
- Do not label speculative patterns as learned personal truths. Record origin and confidence of interpretations.
- Keep all private content out of public GitHub. Store only generic tooling and non-sensitive review contracts here.

## One-page deliverable shape
- **Notebook actually reviewed?** yes/no; access path.
- **Earliest verified vision:** date, original source and concise quote.
- **What survives today:** current sources and evidence.
- **What drifted / was lost:** each with source on both sides; unknown where unavailable.
- **Top 3 justified improvements:** benefit, risk, first small reversible test.
- **What remains unverified / not done:** explicit.
- **Next request from owner:** only the essential missing source or approval, if needed.

## Acceptance checks
- A fresh agent can explain access limits and never invent notebook contents.
- An exported note preserves source/date distinction and cannot rewrite canonical history without approval.
- The review catches conflict between an old AI-generated summary and an earlier owner decision.
- Sensitive source content remains out of public repos, prompts, and logs.
- A model/chat change does not erase verified source pointers and accepted decisions.
