# Zeus → Private J Command Hub: staged read-only link

Status: **DRAFT / NOT DEPLOYED**. Canonical engineering issue: GitHub #12. Operating manual: sections 12, 13, 22, 25.

## Verified architecture (2026-11-22)

- The owner's Telegram request ZEUS-HUB-LINK-20261122-K7M4 returned BLOCKED: Zeus has no callable live Hub reader/writer. Independent ChatGPT Hub read found no matching Note.
- GitHub j_hub.py reads a dated Git snapshot, **not** live Hub storage.
- Private Sites snapshot (hub-site/worker/index.js, draft/mobile-v3) uses R2 and a one-way Hub → Zeus bridge. The snapshot is **not verified as the actual deployed Site source** (Issue #6).
- ChatGPT Sites service access supports SIWC bypass tokens, but bypass requests have **no signed-in visitor identity**. A second scope-specific server credential is required. Do not expose the broad /mcp endpoint as a Zeus tool.

Official Sites source: https://learn.chatgpt.com/docs/sites/data-and-connections

## New isolated files and behavior

- hub-link/site_probe.mjs: proposed read-only private Site handler. Designed to be ported by a Sites specialist into the verified actual worker. It reads Site-owned R2 storage, returning only checkedAt, pulseDate, itemCount, and a boolean for the approved test marker. **No stored item texts leave the Site.**
- hub_link_probe.py: Zeus-side client, pinned to one HTTPS host and fixed path, with two secrets, no redirects, no writes, timeout and bounded response. It rejects unrecognized/non-live responses.
- j_runtime.py and telegram_agent_bot.py: on this isolated branch, add an owner-only /hublink status and /hublink probe MARKER command. Credentials absent or endpoint unconfigured → BLOCKED; never claim success without real source. These do not create new model-callable Hub tools.
- Tests run without credentials or external network. Existing /hub remains an explicitly dated snapshot; the resource_catalog.json status stays not_connected until live read is independently verified.

## Required authorized setup (not performed)

1. In ChatGPT Sites Work/Codex, inspect the **actual deployed** private Hub Site source, owner-only access, source commit and rollback. Compare with Issue #6 and ongoing Antigravity work. Do not overwrite other drafts or change sharing.
2. Port readOnlyHubProbe into that exact worker as dedicated GET /api/zeus-link/probe, injecting existing bucket(env), readObject, readItems and PULSE_KEY. Route it before the generic /api/ handler; do not attach to /mcp or /api/action.
3. In the Site's private environment, set a fresh random HUB_ZEUS_LINK_SECRET (>=32 characters) and HUB_ZEUS_LINK_READ_ENABLED=true. The Site platform must separately enforce private SIWC service access. Test missing/wrong route secret returns 403 and zero data reads.
4. Via Sites Work/Codex, generate or confirm the owner-controlled SIWC bypass token. **Generating a token replaces the previous one; review other consumers first.** Never paste the token here, in GitHub, in a screenshot or in Telegram. Store it in Zeus's private secrets as HUB_SIWC_BYPASS_TOKEN; store the distinct route key as HUB_ZEUS_LINK_SECRET; set HUB_ZEUS_LINK_READ_ENABLED=true. HUB_SITE_URL may be omitted; if supplied it must be exactly the pinned Site.
5. Distinctly verify Zeus's actual runtime code and existing test suite before a production promotion. Do not touch Telegram bot token, Gemini key, model, owner ID, database or live deployment without explicit separate approval.
6. Owner sends /hublink probe ZEUS-HUB-LINK-20261122-K7M4. A passing read-only receipt does NOT prove a write. Independently compare it against the current authenticated ChatGPT Hub connector.

## Pass/fail gates

- Missing/wrong route key → 403, no reads.
- Route off/missing key → 503.
- Invalid marker, method, path → 400/405/404, no reads.
- Storage failure → 503 and no false PASS.
- Client unconfigured, redirects, invalid/missing source, non-JSON response, or timeout → BLOCKED, no secret disclosure.
- Successful live read → source-labelled 200 with minimal metadata, timestamp and independently corroborated Hub state.
- **Writes remain NOT TESTED/NOT AVAILABLE.** A new idempotent single-test-note write path requires separate owner approval after the read stage works.

## Rollback and handoff

GitHub is PUBLIC. No private Hub content, credentials or personal records are committed. Isolated branch is reversible: close PR and delete branch without production impact. Original working Telegram, Hub, Custom Instructions, R2 records and Replit deployment are unchanged. Read-only Site integration belongs to the verified Site editor/owner, not a blind merge from GitHub. Follow existing Issues #2 and #6 and the canonical app-continuity skill.

Next executable step: use Sites Work/Codex to inspect actual private Site source; port endpoint into verified source preview; conduct auth/negative-auth live tests; then obtain approval before any publishing.


## Alternative discovery: native v28 already exposes a record read route (2026-11-22)

**VERIFIED by a read-only audit of the actual native Sites v28 worker source at commit fa822b5311677880c6ed7bbf2b5799dfeb473980. NOT YET VERIFIED end to end from Zeus.**

- Route: GET /api/v1/records/{type}/{id}. It reads the existing private R2 BUCKET and requires Authorization: Bearer plus an exact 64-character lowercase hexadecimal secret matching the Site's HUB_RECORD_READ_TOKEN setting. Missing/wrong bearer is HTTP 401 when configured; after authorization, invalid/missing record is HTTP 404; no writes.
- Response: top-level ok and record. The record has type, id, content, createdAt, updatedAt, revision, storageVersion. Content is the FULL original object; record API accepts item, goal, checkin, planning, project-memory and pulse types. It has NO per-field redaction, no owner-identity header check, and the bearer allows ALL supported record types.
- Anonymous negative tests from the authorized Windows device: missing bearer HTTP 401; fake bearer HTTP 401. Positive authenticated read from Zeus remains BLOCKED.
- The public Sites homepage was observed readable without credentials; private data APIs denied anonymous reads. The owner must separately review the actual Site audience settings before deployment.
- Native Sites deployed v28 source was found to differ from the public GitHub preview (including My Qualities and Review Loose Ends UI). Recovery versions v27/v28 exist, but archive byte equivalence and restore behavior were not verified. Do not replace the live source from GitHub.
- Original metadata-only /api/zeus-link/probe approach in PR #13 / PR #16 remains an option if a least-privilege backend authorization boundary is required. It is NOT DEPLOYED.

### Owner-only one-record client draft on this stacked branch

- hub_native_record_probe.py adds an independent, disabled-by-default verifier for exactly ONE preconfigured item UUID using only GET. No model can choose record type or ID. It cannot list items or write records. It discards full response content without returning, logging or persisting it.
- Existing owner-only Telegram /hublink routing is extended to support /hublink verify-native, which returns only an identity-match status, timestamp and hash of the configured ID; errors are generic and reveal neither secrets nor record contents.
- It requires HUB_NATIVE_RECORD_CHECK_ENABLED=true, HUB_NATIVE_TEST_ITEM_ID=<owner-approved, low-sensitivity existing item UUID>, and HUB_RECORD_READ_TOKEN=<the actual exact-format bearer> in the authorized Zeus host's private secret store. HUB_SIWC_BYPASS_TOKEN can be provided separately if Sites requires it; never generate/rotate it merely for this test or skip the independent Hub bearer. Do NOT paste these secret values into ChatGPT, GitHub, Telegram or logs. No credential access or transfer has occurred.
- Configuring the existing broad Site bearer in Zeus materially increases its exposure. Its broad scope cannot be fixed by filtering the Telegram output; therefore **obtain separate owner approval and independent security review before copying, configuring or executing the live credential**. Prefer a distinct restricted backend token if a native safe route becomes available.
- Test one approved low-sensitivity item, compare exact type/ID against the authenticated Hub connector, and report only PASS/FAIL/BLOCKED. Do not send the record's text, full JSON or revision content back to Telegram or any AI model.
- No Site code edits, new version, R2 mutation, production Zeus changes, automation, secret rotation, deployment, or new live connection result were performed by this branch. No continuous monitoring.

### Staged acceptance

1. Run offline Python regression and negative-auth tests (including missing token, invalid ID, method/host pinning, HTTP errors, invalid JSON, mismatched record, oversized response, secret non-disclosure). Check the exact GitHub Actions SHA.
2. Verify the actual deployed Zeus source/revision and owner-only command routing, plus existing private token consumers. Avoid collision with any active Replit changes or Antigravity work.
3. Obtain owner approval to configure a **single** controlled test with a broad token and to promote the new command. No unattended calls.
4. Check authorized, server-side, one-record HTTP 200 + exact identity match; independently read the same item from the authenticated Hub connector. A missing/wrong bearer must remain HTTP 401.
5. Keep writes unavailable. Obtain separate approval to develop a least-privilege single-note write path, if desired.

Rollback: leave this branch unmerged and un-deployed or close the draft stacked PR; production continues unchanged.
