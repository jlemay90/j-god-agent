# Zep verification — 2026-11-03

## Scope and safety

No owner database, messages, rules, tasks or reminders were queried or modified.
Local tests use temporary SQLite stores. Live probes used new opaque identities and
synthetic orchard labels only. No polling bot, Hub server, deployment, purchase,
Gemini call or deletion API was launched. Disposable remote test users were retained.
Some diagnostic creations did not retain their returned identifiers; they may need
manual identification as synthetic test users before any separately authorized cleanup.

## Setup and compatibility fixes

- Configured the missing post-merge hook to run `build_j.sh`, timeout 180 seconds.
  Post-merge installation, dependency checks and SDK imports succeeded.
- Runtime tested: Python 3.12.12, zep-cloud 4.1.0, Zep Cloud `/api/v4`.
- Added the generic display name `Owner` to Cloud user creation.
- Live Cloud rejected prefixed keys and UUIDv5 keys with HTTP 400. Cloud requires
  UUIDv4-formatted idempotency keys. Keys now use stable SHA-256-derived bytes with
  UUIDv4 version/variant bits, preserving retry identity across restarts.
- Strengthened fake-provider validation so tests reject the previously accepted
  invalid key format. The HTTPX transport test is still a mock, not Cloud proof.

## Evidence

`env -u PYTHONPATH .venv/bin/python -B -m unittest discover -v`

67 tests passed. Added regressions cover timeout and HTTP 429 fallback/recovery,
and an owner response preference correction reaching Hub's model input after
reopening the local database, with the superseded value absent from canonical
active reference. Existing tests cover source roles/times, accepted voice
transcripts, queue replay, lost acknowledgements, bounded dead letters, deletion
barriers, reminders, task-related controls, rules and the bounded retrieval scorer.
Provider and model calls in these tests are simulated.

`env -u PYTHONPATH .venv/bin/python -B verify_zep_live.py --live`

One live run passed:
- Authenticated Cloud ingestion: **passed**, 959 ms initial ingestion/provisioning.
- Stable owner UUID after closing and reopening the temporary store: **passed**.
- Separate Telegram-labelled and Hub-labelled threads with one owner graph:
  **passed**; synthetic fact retrieved within 5,492 ms including extraction wait.
- Queue: two completed events, no reported error.
- No actual Telegram or Hub UI requests/delivery were exercised.

The expanded live run returned **HTTP 409** during its first queued event.
Further provisioning was stopped. The sanitized integration error does not identify
the failing API operation or conflict cause; no account/quota conclusion is justified.
No subsequent live correction, second-user isolation or replay assertion ran.
The opt-in probe now returns nonzero when a recorded live check fails.

## Acceptance limits / remaining blockers

- Outage/rate-limit recovery and remote duplicate handling are **mocked**, not
  provider fault-injection successes. Local queue retries and restart behavior pass.
- Corrected preferences are supplied to Hub after restart in a mocked model test;
  final Gemini behavior across real channels is **not verified**.
- The live graph's correction freshness and cross-user isolation remain **blocked**
  by HTTP 409. Absence of these results is not a pass.
- Canonical local memories supersede old records, but Zep historical context is
  passed through as untrusted text with prompt-level precedence. There is no
  deterministic stale-fact exclusion, scope-aware correction layer, or guarantee
  that an old fact cannot appear in a generated reply.
- The existing feedback backlog and one-file bounded retrieval builder remain
  intact. Explicit feedback scopes, proposed remedies, and automatic conversion of
  repeated feedback into versioned executable regression cases are not added by
  this verification task. The broader behavioral-learning request is not complete.
- `/memory sync` exposes queue counts and a sanitized last error. Per-operation
  persisted Zep latency, authentication freshness, usage/cost accounting, and a
  dedicated Hub health surface are not implemented. Probe latency above is separate
  from Gemini and hosting costs, neither of which was incurred/tested by these probes.
- The integration's deletion API acceptance is asynchronous; tests do not prove
  provider deletion completion or backup removal.
- No services were running during the checks. Always-on operation and reply delivery
  remain unverified. No workflow was started just to obtain an apparent success.

## Rollback

The verification changes are limited to the post-merge hook, SDK call compatibility,
tests, probe, and documentation. They do not migrate or rewrite canonical owner
records. To stop external work without deleting records, stop the Zep worker and
leave its durable queue intact; do not start a second polling bot. Disabling external
calls preserves local retrieval. Reverting the SDK idempotency fix would restore
known HTTP 400 failures, so prefer keeping that fix while investigating other issues.
Any checkpoint rollback should preserve current local database records and pending
queue state; this task did not perform a rollback.
