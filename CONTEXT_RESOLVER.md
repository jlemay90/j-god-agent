# J Context Resolver — v0.1 isolated prototype and engineering handoff

**Status:** TESTED LOCALLY with synthetic records; **NOT MERGED / NOT DEPLOYED / NOT A LIVE CONNECTOR**. Issue: https://github.com/jlemay90/j-god-agent/issues/7

## Purpose
Find the right facts already held in an authorized source before asking the owner to repeat them. A dedicated, read-only context layer for the full J Command OS—not a new task manager, new long-term memory store, or a claim that the model has permanent automatic access to every application.

### Four user-facing journeys

- **Find** — “What happened to [case]?” Find subject aliases and return the linked canonical source rather than repeating an old question.
- **Verify** — “Is [fact] still true?” Identify when a source was fetched, how its claim was classified, and which current primary records are still needed.
- **Compare** — “Which status is right?” Flag incompatible unsuperseded claims. A later timestamp is not enough to erase an older fact.
- **Handoff** — “Pick up where we stopped.” Package only relevant references and verification gaps in a bounded payload rather than inserting an entire historical prompt.

## Existing source boundaries (verified as of 2026-11-20)

- **J Master Index:** pointer map, not a duplicate evidence warehouse.
- **J Command Hub:** latest *recorded* tasks, notes, links and project state when owner-authorized connector access is available; item state does not independently prove real-world completion.
- **Case/project dossier, operator emails, GitHub issue:** original domain evidence and dated decisions, consulted when relevant. A dossier is a secondary synthesis if its text says so.
- **Canonical Operating Manual:** policy/reference guidance; **Version Register:** historical instruction versions, test reports and supersession.
- **Zeus `j_context.py`:** retained Telegram history only. **`j_hub.py`:** dated repo handoff only. These do **not** silently inherit Hub/Drive or user credentials.

## Implemented

`j_context_resolver.py` implements input validation, topic/alias relevance, evidence-aware source ranking, stale-read notice, explicit shared canonical case-key conflict detection, bounded-result omission warnings, unresolved claim disagreement detection, no-match fallback, and bounded 3.5k-character context packet. It exposes two pure data adapters, `hub_items_to_records` and `doc_excerpt_to_record`, which accept data an already-authorized caller supplies. It has no network calls, no writes, no background work, no new database, and no secret handling. Source text is untrusted reference data, never executable instructions.

Use the same optional `canonical_key` in Hub and dossier records when a trusted source map confirms they refer to the same case; titles alone cannot safely establish identity. The `verified` status is *assigned by a trustworthy upstream reviewer/adapter*. The resolver cannot independently establish external truth from a URL or a claimed status. Evidence level, fetch receipt and real-world event date are separate concepts. A stale-read warning does not prove the historical record itself is false.

### Use offline with approved inputs

```bash
python -m unittest discover -p 'test_j_context_resolver.py' -v
python j_context_resolver.py --query 'What happened to Case Alpha?' --input /private/path/authorized-records.json
```

JSON input: `{"records":[{"id":"case-1","subject":"Case Alpha","aliases":["alpha"],"source_url":"https://example.org/case","source_role":"case_dossier","fetched_at":"2026-11-20T22:00:00Z","summary":"A supervisor made a dated decision","status":"owner_reported"}]}`.

Sources must be fetched by authorized tools before constructing the record bundle. The resolver must never be handed raw private source data for publication to a public repository, persistent logs, URL parameters, or other unauthorized surfaces. Do not commit private JSON inputs.

## Local validation results

- Python `unittest discover`: **23 / 23 synthetic tests PASS** in isolated workspace on 2026-11-20.
- Tests cover ten distinct topic routes, aliases, absent source, irrelevant query, direct evidence versus pointer, stale source, owner report, cross-source canonical-key disagreement, omitted-record warning, marked supersession, malicious embedded text treated as data, invalid URL/timestamp, packet budget, input upper bounds and pure Hub/Doc adapters.
- One *manual adapter smoke test* using a minimal case summary reproduced retrieval of a Hub case pointer plus its corresponding dossier excerpt, but this was not a connected API/production test.
- **Not tested:** live authenticated end-to-end connector calls from the deployed app; retrieval precision on real ten-case benchmark; UI; negative-auth; Hub ↔ Zeus bridge; latency and cost at scale; unattended / automatic ChatGPT startup behavior. Do not claim those pass.

## Recommended integration: small, guarded steps

1. **Owner-authorized connector reads:** A host function reads the current Hub state and J Master Index only when topic-specific context is relevant. Get a dated fetch receipt and scope. Avoid loading every private record into the LLM or public service.
2. **Targeted dossier fetch:** Follow only the canonical matching link with actual permission, extracting the relevant range and reporting access failures.
3. **Pack and evidence gate:** Run resolver on *supplied* records. Pass only a bounded packet and source IDs to the assistant, which must verify any unresolved claim before a definitive answer.
4. **Read-only owner UI:** Expose “Find context” with answer, date, source link, verification status and “needs confirmation” line. Offer “review changes” separately; do not auto-mark tasks done.
5. **10-case evaluation:** At least ten owner-approved cases, measure precision@1, correct supersession, false certainty rate, missing-source response, median latency and context byte count. Acceptance requires zero invented source receipts and no unauthorized disclosure.
6. **Live integration gate:** First identify the exact deployed Sites source and reconcile divergent GitHub source; do not treat a prototype passing tests as a deployed feature. Require owner approval to merge, deploy or change automated workflows.

## Architecture / security

No new data store. No cross-account access. No privacy-sensitive records in the public repository, issue, PR, model prompts beyond necessary approved context, or public URL. The feature is deterministic **after** the host supplies trustworthy, relevant records. A missing source means UNKNOWN, not “did not happen.” On content conflict, return explicit candidate sources and demand direct confirmation. Retrieval code does not execute source text or bypass authorization.

## Branch handoff

Canonical repository: https://github.com/jlemay90/j-god-agent . Work originated from verified `main` commit `a983463a153b6215150509b084325b10c1baf97e`, branch `agent/chatgpt/context-resolver-v1`. Production/private Sites SHA is not established from GitHub main; refer to issue #6. This feature avoids modifications to existing runtime, deployed Sites, credentials, automations, and core Custom Instructions. Next step: run a scoped connector integration proof using the live owner's authorized Hub/Drive reads and private benchmark fixtures, then review code/tests/authorization before any merge. Rollback: discard branch or remove the two new prototype files; no migration.