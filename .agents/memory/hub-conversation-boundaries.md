---
name: Hub conversation boundaries
description: Product constraints for completing ChatGPT to Zeus conversations through the existing Hub.
---

Use the existing Hub and Zeus PostgreSQL request receipts for conversational
exchange. Never consume ordinary Hub notes or tasks as messages to Zeus; dispatch
requires an explicitly designated conversational message and owner-only access.
Do not create another agent or memory database to substitute for this connection.

**Why:** The user asked to make the existing ChatGPT conversation their connection
to Zeus through J Command Hub, without duplicate tasks or a duplicate memory silo.

**How to apply:** Verify the real connector schema and permissions before adding
dispatch or reply read-back. Missing capabilities are blockers, not permission to
invent fields or repurpose project-memory writes. Current Hub projectMemory revision
requires live authenticated provenance; Zeus rule and historical handoff revisions
must remain separate counters.
