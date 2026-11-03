# Bounded tool reasoning and reply recovery

Ordinary Telegram turns now support up to four model rounds, up to two tools per
round and six tools total, with a 90-second overall reasoning deadline. A turn
without tools still uses one model call. Existing model request/token limits apply
to every call, including synthesis and retries; tool-using requests may cost more.

Actual tool observations return to the model for analysis and subsequent permitted
steps. Tools remain limited to the existing registry and original owner-message
authorization. Page reads still require an exact owner-supplied public HTTPS URL;
this change does not add web search, account access or permission to follow arbitrary
links. Repeated identical calls are suppressed. Later observations cannot create
standing rules or durable memories: those proposals come only from the first model
response, grounded against the original message. If later reasoning fails or reaches
its limit, J returns available receipts as partial results, not a completion claim.

Completed turns and pending reply delivery are stored transactionally. A background
tick retries pending owner-only replies without rerunning model calls, tools, memory
writes or rule updates. Successful chunks are checkpointed, replies use a conservative
UTF-16 size bound, and pending delivery survives process restarts. Completed outbox
rows are deleted. `/forget confirm` clears pending replies with conversation history.
There is still a narrow external-API ambiguity if Telegram accepts a chunk and the
process dies before checkpointing it: a chunk may be repeated. Exactly-once delivery
is not claimed. Recovery depends on the bot running and its database being available.

Deploy all changed Python files together and restart the existing single bot process.
The new outbox table is created idempotently during Store initialization; no existing
records are rewritten. Current code supplies the loop contract on every turn, so no
manual database rule migration is needed. The staged Hub web bridge retains its
section-only proposal contract and is not activated or broadened by this patch.

Offline verification: `python -m unittest discover -v` includes page-to-calculation
reasoning, ordinary one-call chat, errors, repeated calls, step limits, URL scope,
outbox restart recovery, owner isolation, transactional rollback and Unicode chunks.
Model responses and page retrieval in the new tests are deterministic fixtures; a
live provider/Telegram round trip must be checked separately after deployment.
