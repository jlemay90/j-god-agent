---
name: Zep Cloud request compatibility
description: Live Cloud idempotency validation differs from permissive mock tests.
---

Cloud v4 requires UUIDv4-formatted idempotency keys, not arbitrary strings or UUIDv5.
Persist or deterministically derive a stable UUIDv4-formatted key per operation;
never generate a fresh retry key.

**Why:** Live requests rejected both prefixed strings and UUIDv5 with HTTP 400 while
the local SDK HTTP mock accepted them. SDK serialization alone cannot prove server compatibility.

**How to apply:** Enforce the version/variant in provider fakes and keep an isolated
live compatibility probe. Record failed live checks honestly; do not infer authentication
or correct recall from credential presence or passing mock transports.
