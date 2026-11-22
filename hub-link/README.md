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


## Owner-approved narrow live Pulse route, native v28 source (2026-11-22)

Owner approved progressing to a live Zeus-to-Hub connection using a new, narrowly scoped Pulse metadata-only credential, NOT the broad record bearer. Native Sites v28 source was exported and authenticated on user's computer: ZIP sha256 097ca0ce4820dd98ce40fe6668d7d4a21b80dd8fff9b77258bf379c302e87e29 and 19/19 internal file checksums. Native v28 commit fa822b5311677880c6ed7bbf2b5799dfeb473980 is NOT in public GitHub repository.

Existing native artifacts on the authorized desktop:
- Downloads/J-Command-Hub-v28-Zeus-scoped-unpublished.patch, sha256 28d671d329e1293cfadeb3ea7338c8bc011af517ea79380496f1c6a6ae05d702, four changed source files.
- Downloads/J-Command-Hub-v28-Zeus-scoped-test-receipt.md, original regression suites PASS, 6/6 scoped bundle security tests PASS, loopback HTTP tested 401 missing, 401 wrong, 200 correct synthetic bearer, one synthetic Pulse read, zero writes. Homepage HTML hash identical before and after.
- Neither live R2 nor real secrets used in these tests.

New native proposed route: GET /api/zeus-link/probe?requestId=ZEUS-HUB-LINK-YYYYMMDD-XXXXXXXXXX. It requires a NEW distinct HUB_ZEUS_SCOPED_READ_TOKEN (64 lowercase hex) and HUB_ZEUS_SCOPED_READ_ENABLED=true, checks HMAC, reads ONLY existing R2 hub/v1/pulse.json. Returns the date and minimal structured receipt with zero writes; never item text, bulk records or item listings.

This isolated branch adds hub_scoped_pulse.py and owner-only /hublink verify-scoped. Features: exact pinned HTTPS host, one request per explicit command, no redirects or automatic retries, required feature flag and new credential from private environment, strict source/identity/scope/read-count checks, bounded JSON and timeout, no secrets or item contents in Telegram. Optional SIWC service header if authorized Sites private gateway requires it. DOES NOT use HUB_RECORD_READ_TOKEN or superseded broad-token PR #17.

LIVE preconditions:
1. Check native Sites v28 source/recovery, current source HEAD and no other agent overlap. Check whether save-only moves configured source branch and whether automatic production publication is possible. Do not overwrite or force push.
2. Safely port the reviewed native patch only to current verified Site source, never the public GitHub snapshot; run regressions and save an undeployed version with verified ID, preserving v28 rollback. Do not declare live if version save is blocked.
3. Provision a fresh separate scoped token in the Site AND authorized Zeus runtime private secret managers without showing it in prompts, logs, GitHub or Telegram. No token rotation. Avoid exposing the broad bearer.
4. On explicit owner production approval, deploy exact verified version and independently test 401 missing/wrong bearer, 200 authorized Pulse-only response and matching independently authenticated Hub Pulse date, zero writes and original Zeus command functionality.
5. Never treat offline tests as live receipt, or a Replit Agent update in progress as a deployed bot.

Rollback: retain the native v28 Sites deployment and original v28 source ZIP, revert any source branch commit, disable scoped route flag or revert to v28 saved version if necessary. Keep Replit deployment and source changes isolated until verified.
