# ChatGPT ↔ Hub ↔ Zeus: integration boundary

## What works

Zeus accepts timestamped HMAC-authenticated POST `/hub/chat` with a UUID
`requestId`, optional UUID `conversationId`, allowed `panel`, `message`,
section-matching `context`, and bounded `history`. It returns the actual generated
reply and stores the completed result in the existing PostgreSQL
`hub_web_requests`. Repeating an identical completed request returns that result.
Conflicting, pending or failed request IDs do not silently trigger generation.
Final eligible turns use the existing memory ingestion path.

## Blocker in this workspace

Integration discovery returned no connected J Command Hub connector here, and
neither its server source nor its API/tool schema is present. The named tools
`get_hub_state`, `add_hub_item`, and `update_hub_project_memory` do not establish
permission to dispatch a message or attach a Zeus result. No fields, polling
worker, endpoints, or successful connection have been invented.

## Exact capability needed in the existing connector

Choose either supported extension, implemented in the existing Hub service:

1. An owner-authorized connector action that server-side calls the existing signed
   `/hub/chat` endpoint and returns its result. To support `get_hub_state` read-back,
   that tool must also expose the owner's designated conversational receipts.
2. If using `add_hub_item` rather than adding an action, its verified schema must
   permit an explicit machine-validated conversational envelope and the Hub backend
   must support owner-authorized dispatch and attaching/exposing the actual reply.
   A note title, text prefix, task category, or project-memory mutation is not an
   acceptable dispatch signal.

The envelope must preserve the request UUID and conversation identity. Reuse
Zeus receipts rather than creating another memory store. Keep shared signing
credentials server-side; ChatGPT must never receive them. Scope creation and
read-back to the authenticated owner; conversation data cannot grant permissions.
Use bounded HTTP timeouts, request-ID replay semantics, origin attribution and
explicit pending/failed states. A timed-out caller must recover the saved result
without creating a new generation; a durable queue would require an explicitly
authorized input payload/claim design, not treating existing receipt rows as jobs.

## Acceptance test once the connector supports dispatch/read-back

From the existing ChatGPT connector, create one explicitly designated conversation
message asking for a unique harmless nonce echo. Confirm `get_hub_state` returns
the actual Zeus reply with matching request/conversation IDs and source attribution.
Repeat the same request: one saved receipt and no extra generation. Try a conflicting
payload with the same ID, an ordinary note/task, a non-owner read, and a timeout:
each must fail safely without a fabricated reply or duplicate task. Confirm existing
projectMemory, rules and history remain unchanged by this test.

## Revision names

`zeusRuleRevision` (legacy alias `ruleRevision`) is the version of Zeus's canonical
operating rules. `hubProjectMemoryRevision` is null unless a live authenticated
Hub source is available. Git handoff revisions are historical and independent;
stale handoff decisions are excluded from automatic model context.
