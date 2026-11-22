# J Command OS — Pattern Investigator v0.1 (isolated build)

**Status (2026-11-22): TESTED LOCALLY WITH SYNTHETIC DATA; NOT LIVE.**

Owner goal: an integrated, trustworthy detective that notices useful recurring circumstances, challenges easy explanations, proposes small consented experiments, learns from measured outcomes, and makes its own failures visible. The owner should **not** have to ask whether it did its job; operators should still be able to verify actual runs. This is not a replacement for the canonical Google Docs operating manual (Sections 7–9, 22–25), the Hub, the Context Resolver draft PR #8, or J RUN draft PR #9.

## Four logical roles, one governed feature

1. **Collector** (future connector adapter): read narrowly authorized sources, attach original source pointer, event date, source type and user permission; assign explicit themes from observed data; deduplicate shared events. Never use private Hub/Drive data in this public repository.
2. **Skeptic** (implemented deterministic gate): check independent events, evidence strength, source variety, contradictions, recency, sensitivity, intentions vs actions; abstain instead of inventing confidence.
3. **Experiment designer** (future AI-assisted proposal only): recommend the lowest-cost reversible experiment with baseline, success measure, stopping rule and explicit case-specific owner consent. Core returns **NOT_AUTHORIZED_NOT_RUN** by default.
4. **Auditor/watchdog** (implemented receipt freshness checker): distinguish a local analysis receipt from provider access, dispatch/delivery, experiment execution and real-world outcomes. Requires an **independently scheduled external watcher** to detect when the worker itself never runs. No alert, schedule or watcher was activated by this branch.

Avoid spawning four independently writing agents. Use a shared evidence contract and one canonical subject record with source pointers; do not add a new personal memory database.

## Executable component

- `pattern_investigator/engine.py`: pure, standard-library evidence gate. Accepts at most 300 observations / 30 themes, with source pointers, unique event IDs, timestamps, source quality, permission and sensitivity flags. Flags missing/unauthorized sources, contradictory evidence, single-day/single-event samples and stale observations; never claims causation or diagnosis. A repeated signal may be *possible* after 2 independent days/events; *supported recurrence* requires at least 3 events, 2 distinct sources and 2 primary/verified observations. It is still not proof of cause.
- `pattern_investigator/__main__.py`: stdin JSON CLI in `investigate` or `watchdog` mode; prints structured JSON receipt. No network, API calls, new stores, external messages or personal record updates.
- `tests/test_pattern_investigator.py`: synthetic unit/CLI tests including failures and false positives. Tests do not establish a functioning model or live connection.

From repository root:

```sh
python -m unittest discover -s tests -p test_pattern_investigator.py -v
python -m pattern_investigator investigate < /private/path/to/authorized_observations.json
python -m pattern_investigator watchdog --max-age-hours 36 < /private/path/to/latest_receipt.json
```

Do not put `/private/path/...` files in GitHub, issue comments, build artifacts, logs, or model-visible public messages. The connector that creates that data must enforce genuine owner-scoped authorization; a caller-provided `authorized=true` or `original_verified` is **not independent proof** of authentication. The engine currently labels source access `SUPPLIED_BY_CALLER_NOT_INDEPENDENTLY_VERIFIED` for this reason.

Minimal generic input (fictional):

```json
{
  "request_id": "case-a",
  "observations": [
    {"id":"a1","event_id":"evt1","source_ref":"private:ref-1","source_kind":"owner_reported","occurred_at":"2026-11-19T17:00:00-06:00","theme":"follow_through","basis":"owner_report","polarity":"supports","summary":"Fictional example action","goal":"growth","authorized":true,"sensitive":false},
    {"id":"a2","event_id":"evt2","source_ref":"private:ref-2","source_kind":"owner_reported","occurred_at":"2026-11-20T17:00:00-06:00","theme":"follow_through","basis":"owner_report","polarity":"supports","summary":"Second fictional example","goal":"growth","authorized":true,"sensitive":false}
  ]
}
```

Expected assessment: `POSSIBLE_RECURRENCE`; only source IDs, not private summaries, appear in the report. A pattern is a candidate explanation, not an established identity or medical conclusion. Real outcome data is required to validate value.

## Real reliability contract — NOT YET VERIFIED

A **production-ready** integration must satisfy all of these before declaring `VERIFIED LIVE`:

- **Actual data**: owner-approved Hub/Drive/etc read scoped to one subject with authenticated source receipt, current revisions and timestamps, documented missing coverage. Adapters must reject stale revs, ambiguous authorizations, sensitive records without separate consent, unsupported model inferences, duplicates, and prompt injection in retrieved text.
- **Actual analysis**: at least three separate real cases (one valid signal, one false positive, one conflicting/missing-source case); read-only, with source links and independent manual comparison. No fabrication when data is absent.
- **Actual schedule**: one verified authorized recurring worker; idempotent request ID, runtime time/cost limits, durable private run checkpoints; do not add an overlapping ChatGPT automation (five active task slots currently in use). Reuse existing J RUN/Hub and Pulse if and only if that runtime is connected and independently tested. No purchase or new paid integration without separate approval.
- **Independent watchdog**: separate scheduler/out-of-band observer checks expected run receipts and source freshness and delivers an owner-only *missed-run* notification. A watchdog implemented in the same process is insufficient; a scheduled job does not prove successful notification.
- **End-to-end evidence**: real worker log + exact read source/commit/revision + analysis receipt + actual Hub report readback + notification receipt (where configured). If any link fails, surface `BLOCKED`, `OVERDUE`, `DEGRADED`, or `UNKNOWN`; no silent success claims.
- **No autonomous consequential changes**: all financial, messaging, family, medical, legal, access, data-sharing, destructive or high-stakes actions require specific owner approval. Even small personal experiments are **proposed**, never silently conducted.
- **Proof of durability**: cold restart/resume, cancellation, expired authorization, wrong user, source outage, malformed model output, repeated run, source conflict, no data, stale findings, disconnected bot, and missing notification are deliberately tested.

## Scope and rollout

- **Now**: this isolated evidence gate and watchdog *logic* are tested offline; ready for security review and integration design.
- **Next**: validate one authenticated Hub read and process three owner-approved cases; reuse Context Resolver PR #8 for source retrieval and J RUN PR #9 for durable bounded execution once independently accepted. Do not blindly merge either draft.
- **After proof**: run a time-bounded read-only pilot in a private runtime, connect an independent watcher, test actual device delivery, and compare useful findings to false positives for a week. Only then recommend a permanent cadence.

**Operating principle:** A test that passes, an automation scheduled, an email sent, and a result delivered are distinct proofs. There is no way to guarantee “never check again”; the engineering goal is to automatically report failures so the owner rarely has to initiate checking.

## Repository safety / collision management

New paths only. No edits to existing production, bot, API, UI, `.agents/coordination`, `run_controller` or `j_context_resolver`; no branch merge, production deployment, schedule changes, database migrations, secrets, private data or financial actions. Canonical owner-approved goals remain in the private manual and Hub. Review PR against latest base before any integration work. This document is an implementation package, not a new operating manual or source of personal truth.