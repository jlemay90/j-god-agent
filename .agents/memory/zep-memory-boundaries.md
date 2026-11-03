---
name: Zep memory boundaries
description: Scope and data-lifecycle decisions for shared Telegram and Hub memory.
---

Do not import personal archives or add Graphiti infrastructure.

**Why:** The user explicitly excluded both from the Zep integration.

**How to apply:** Extend Zep using new, finalized conversation events only unless
the user explicitly changes this scope.

The external Zep graph is derived context, not the canonical rules or structured
memory store. Confirmed local-memory deletion clears the whole derived Zep context,
rather than guessing which provider-extracted facts correspond to a local record.

**Why:** Local record identities do not map reliably to provider-extracted facts;
fuzzy matching could retain forgotten data or delete the wrong facts. Local history
and other canonical records retain their separate deletion semantics.

**How to apply:** Keep the full-reset consequence visible in deletion confirmation,
block external recall while cleanup is unresolved, and never reimport old local
history automatically after a reset.
