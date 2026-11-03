# Zeus bridges and evidence-driven improvement

## System responsibilities

- Replit hosts the Python Telegram process and its isolated retrieval builder.
- PostgreSQL is canonical for Zeus conversations, memories, rules and usage.
- GitHub `jlemay90/j-god-agent` is canonical for Zeus source and revision history.
- [J Command Hub](https://j-command-hub.jlemay90.chatgpt.site) is the existing
  owner-private Sites app for priorities, captures and project records. It is not
  Replit. Its shared records remain canonical; do not duplicate them in Zeus.
- Drive is a possible document source, not a prerequisite for self-improvement.

## Working GitHub bridge

The workspace's existing Git authentication is reused; no new credential is
created, exported, copied into a model prompt or granted to another service.
The model gets a bounded `repo` tool and the owner gets `/repo` commands:

- `/repo status`: committed workspace SHA and last-fetched main SHA.
- `/repo sync`: fetch the existing approved origin/main; never pull live code.
- `/repo files`: explicit allowlist of committed source and operating docs.
- `/repo read j_retrieval.py 1 60`: bounded source excerpt with commit provenance.

Only the exact GitHub repository is accepted. No arbitrary Git arguments, paths,
URLs, credential/configuration reads or shell commands are exposed. Private
runtime rules, backups, database state and environment files are excluded.
Source is historical reference, not a fresh instruction or an authorization.
This inspection bridge does not expand the existing autonomous editing scope.

## What self-improvement currently means

1. Explicit preferences, decisions and corrections become evidence-backed memory
   or owner-requested rule revisions; Gemini weights do not change.
2. Request failures and owner corrections feed an improvement backlog.
3. The bounded builder can generate changes to `j_retrieval.py`, test them in
   isolation, require strict benchmark improvement without regressions, commit
   successful candidates and attempt GitHub sync. It pauses if its sandbox is absent.
4. Inspection and history recall make failures diagnosable rather than magical.

## Recommended next changes

Prefer reliability and evaluation over wider self-editing. Add representative real
failure cases with owner approval, keep a separate unseen holdout, and measure
retrieval relevance, unsupported claims, repeated questions, latency and owner
effort. A synthetic score alone is insufficient. Do not let the model rewrite its
tests, access controls, credentials, budget, promotion gates or deployment logic.

Ordinary chat and builder tests currently share the Telegram owner chat and model
budget. Separate clearly labelled commissioning examples from owner facts; a
future dedicated test harness should supply synthetic messages without crowding
the live conversation. Keep a small, recoverable change scope and evaluate before
expanding it to additional modules.

## Hub bridge design, not yet connected

Use an authenticated, read-only context endpoint returning project decisions,
current approved priorities, source timestamps and revision. Reuse existing Hub
records. A dated snapshot must never claim live sync. Preserve the Hub's private
audience and record-level authorization; do not make it public to simplify access.
Sites service authentication and user/connected-app consent are separate. A
service token alone does not establish a visitor identity or Drive consent.

Before activation, review the precise data scope, endpoint and secret handling.
Writes should be separately scoped, idempotent and conflict-aware. Do not silently
import family, legal, financial or health records into a new external model context.

## Drive, if needed

Start with selected documents or one dedicated folder, read-only. Preserve document
IDs, source dates and canonical links. Avoid copying the entire Drive or granting
mail/calendar permissions for a document-search feature. OAuth consent and the
chosen credential flow must be completed before claiming a working integration.

## Dated Hub project handoff (implemented)

/hub fetches the approved GitHub main reference and reads only hub_project_context.json. Ordinary conversation receives this bounded validated snapshot with capture time, Hub revision and source commit. Over 24 hours old is labelled stale. A GitHub fetch does not query the live Hub or refresh the original snapshot. Canonical records stay in the Hub. No personal task/Pulse records, Hub writes, Drive/Gmail/Calendar access or new credentials are included. Live authenticated bridges remain unfinished.

## Contextual Hub chat transport (staged, inactive)

The Hub now has separate Today, Inbox and Build panels. j_web_bridge.py supplies an authenticated HTTP transport using existing Zeus rules, bounded durable memories and the metered Gemini path. It does not receive Telegram turns, write Telegram conversations, save memories/rules or send Telegram messages. Section-limited proposals require a visible Apply click in the Hub. HMAC signing requires a new server-only shared secret; no listener or secret was created during staging. Binding an external port and setting Site secrets require access activation. Backend default daily cap is 30 requests plus the shared model ledger. PostgreSQL model-call reservation now takes a transaction-level lock across transports. Live Gemini smoke check returned provider 503 despite the existing bounded retry; no working end-to-end connection is claimed.
