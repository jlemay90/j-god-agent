# Scoped Pattern Investigator handoff — 2026-11-22

**Canonical repo:** https://github.com/jlemay90/j-god-agent
**Canonical owner guidance:** private J Command OS Manual v0.2.0 Sections 7–9, 22–25; Hub Pattern Investigator Idea id `4615433f-b6a7-4f13-8927-da76639b06dd` in NEXT. Refer to those private sources only within authorized systems.
**Purpose:** build an evidence-based self-auditing personal pattern investigator, not a standalone task app, diagnosis engine or unverified autonomous bot.
**Branch and PR:** see GitHub ref where this file is committed (do not assume merged or deployed). This branch is deliberately isolated from ongoing Context Resolver, J RUN and Zeus development.
**Existing foundation:** PR #8 context retrieval draft; PR #9 bounded work-cycle controller draft; GitHub Issue #2 multi-agent coordination. They were not merged or altered by this work.
**Changes:** new Python standard-library read-only `pattern_investigator` package, synthetic tests, and `PATTERN-INVESTIGATOR.md`. No changes to live system, permissions or stored private records.
**Test command:** `python -m unittest discover -s tests -p test_pattern_investigator.py -v` from repo root. Tests validate only the core with synthetic fixtures. Do not infer provider connection or scheduled execution from results.
**Known blockers:** real authorized source ingestion, model-supported but evidence-limited thematic extraction, protected private evidence storage, durable run controller integration, separate independent worker health monitor, owner-only notification receipt and live owner approval of pilot/deployment.
**Acceptance:** three real, owner-approved cases, one disputed case, source readback, honest receipts, restart/failure drill, externally witnessed missed-run alert, then a measurable read-only pilot. Explicit separate approval for merge/deploy/external actions.
**Rollback:** close PR and delete isolated branch only after review; existing main and site/bot unaffected.
**Safety:** Public GitHub files must contain no personal evidence, identifying records, tokens, transcripts or cached connected-source content. Do not silently write to Hub or medical/financial sources.
**Next step:** review isolated PR, validate authenticated read-only Hub adapter with one case and live receipts. Adapt existing context and run draft components with explicit conflict checks instead of duplicating them.