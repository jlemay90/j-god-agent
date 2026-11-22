# J Command Hub Site

This is the existing J Command Hub Site source, kept inside the J God Agent repository as its Hub UI subproject. It is not a separate prototype.

The app continues to use its existing Hub API and storage, auth and integration flows, Zeus bridge, and existing record IDs. The Home and navigation redesign is implemented in the source here.

## Build and checks

From this directory, run `node scripts/build.mjs`, `node scripts/validate.mjs`, `node scripts/test.mjs`, and `node scripts/test-zeus.mjs`. The build writes the deployable Worker bundle to `dist/`. Hosting settings are read from `.openai/hosting.json`; deployment is a separate action and is not performed by these checks.

Personal assistant conversation links and personal goal defaults are intentionally excluded from this public repository copy. Runtime data remains in the existing Hub backend.


## Restricted Zeus → Hub read-only preview (2026-11-22, NOT LIVE)

The isolated branch agent/chatgpt/hub-readonly-preview-20261122 descends from existing Antigravity work feature/hub-capability-router-ui at SHA 205602fe2e1d5cdf4e2b0a194fc3f3afebd48a7e. It embeds the same read-only request handler from [PR #13](https://github.com/jlemay90/j-god-agent/pull/13) in the existing Worker build without replacing the current UI, bridge, state routes or R2 keys. It adds a dedicated GET /api/zeus-link/probe route behind an independent HUB_ZEUS_LINK_SECRET and disabled-by-default HUB_ZEUS_LINK_READ_ENABLED. The private Sites platform SIWC gate is **not** tested in GitHub Actions.

To check locally or in GitHub Actions from this branch, run:

    node hub-site/scripts/build.mjs
    node hub-site/scripts/validate.mjs
    node hub-site/scripts/test.mjs
    node hub-site/scripts/test-zeus.mjs
    node --test hub-site/worker/test_zeus_hub_probe.mjs
    node hub-site/scripts/test-hublink-preview.mjs

Tests use ONLY synthetic R2-like objects and fake secrets. CI never contacts the private Site, Replit, or real Hub storage; it does not read or change production data. The limited payload contains a generated timestamp, Pulse date, item count and an exact test marker boolean. No arbitrary item text is returned.

**Source-of-truth limitation:** Neither this GitHub snapshot nor the Antigravity branch is verified as the actual deployed private Site source. This branch is a source-level build/test rehearsal, NOT an authenticated live Sites preview. For acceptance, inspect the real Site source in the authorized Sites editor, establish rollback/version baseline, port the approved diff without clobbering other work, configure secrets privately and test wrong/missing SIWC and scoped credentials against actual Site preview. No merge, publish or production deployment is authorized by these tests. See Issues [#6](https://github.com/jlemay90/j-god-agent/issues/6), [#12](https://github.com/jlemay90/j-god-agent/issues/12), [#2](https://github.com/jlemay90/j-god-agent/issues/2) and the existing continuity policy.
