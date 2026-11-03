# Shared Zep memory

The existing PostgreSQL/SQLite records remain canonical. Rules, structured memories,
their correction chains, tasks, reminders and Telegram history are not migrated or
replaced. No archive is imported. Both transports use the same current rule revision
for voice/style; Telegram voice memos contribute only their accepted transcript.
Optional spoken output remains paused under the existing metering policy.

## Identity and ingestion

- A persisted opaque owner key maps to Zep's server-assigned user and graph UUIDs.
- Telegram has one private-owner thread. Hub has a separate thread per panel and
  optional `conversationId` UUID. Existing Hub clients use the stable panel default.
- Every newly finalized eligible turn queues exactly its original user text and its
  final assistant reply, including application storage/tool notices. Hub proposals
  remain proposals, not applied actions. Client-supplied Hub history is not imported.
- Metadata retains transport, source update/request identity and role. `reference_time`
  retains the Telegram source timestamp or Hub server acceptance timestamp, plus the
  final assistant timestamp. Assistant messages are stored but excluded from graph
  extraction so assistant assertions do not become owner facts.
- Finalization and queue insertion share one local transaction. Stable event keys
  and Zep request idempotency keys protect replay. The supervised single worker
  provisions mappings and drains bounded batches, with five attempts, exponential
  backoff, interrupted-claim recovery and explicit dead-letter state.
- `/memory sync` shows queue states and sanitized failure codes. `/memory retry confirm`
  explicitly permits another bounded attempt for dead work. Exception bodies, URLs,
  prompts and credentials are never used as error messages or logs.

## Retrieval and fallback

Before generated replies, both transports query the same owner's Zep graph with a
3,500-character server budget and a local truncation bound. The result is supplied
as untrusted reference, not system instructions, tool authority or a fresh request.
Current owner messages and canonical local corrections take precedence. Local
retrieval, rules and reply handling continue if Zep is unconfigured, unavailable,
empty or still processing. The first turn can use local context while the worker
provisions the external identity. Zep extraction is asynchronous; completion of an
ingestion request is not proof of immediate recall.

## Correction and deletion

Ordinary corrections propagate in their original conversation turn. Explicit
`/memory correct` commands also queue the original command and actual final reply.
Local supersession and provenance are unchanged; historical Zep evidence may remain,
but it is never authoritative over a current correction.

A confirmed `/memory delete ID confirm` deletes the local correction chain and
queues a **whole derived Zep context reset**. This conservative behavior is disclosed
in the confirmation prompt: extracted provider facts cannot reliably be mapped to
local record IDs. `/forget confirm` deletes the existing local Telegram history and
also queues that reset. Other local rules, memories, tasks and reminders retain
their existing semantics; Hub request receipts and Telegram messages are separate.

The reset removes queued copies of old turns, blocks Zep retrieval and newer ingestion
until cleanup succeeds, and requests deletion of the integration's Zep user/graph.
It then rotates the external identity and thread mappings for future turns. It does
not reimport retained local history. A failed cleanup remains visible and keeps Zep
recall disabled rather than serving forgotten data. Provider acceptance of deletion
does not guarantee removal from provider backups or other services.
If creation succeeded before its UUID was saved locally, cleanup first resolves
the persisted external owner key; an uncertain lookup cannot complete the reset
or discard the identifier needed for another attempt.

Run `sh build_j.sh` for the complete pinned Python 3.12 runtime dependency set.
`j_services.py` supervises the bot, Hub bridge and one Zep ingestion worker together.
