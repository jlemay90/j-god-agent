---
name: Optional recall latency budget
description: Keep Zep network retrieval from dominating the answer path during slowdowns.
---

Treat remote recall as optional within a short caller deadline, with bounded
outstanding work and canonical local memory as fallback. Do not shorten durable
ingestion retry policy merely to speed up answer generation.

**Why:** Latency investigation found recall serialized before generation with an
eight-second transport timeout, adding avoidable delay on top of cold starts.
The answer must remain available when the derived memory provider is slow.

**How to apply:** Preserve caller deadlines and the shared concurrency cap in both
transports. Retain source/privacy checks after a successful lookup; background
completion must not mutate the caller's Store or inject late context.
