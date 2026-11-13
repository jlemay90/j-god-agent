# J Command Hub Site

This is the existing J Command Hub Site source, kept inside the J God Agent repository as its Hub UI subproject. It is not a separate prototype.

The app continues to use its existing Hub API and storage, auth and integration flows, Zeus bridge, and existing record IDs. The Home and navigation redesign is implemented in the source here.

## Build and checks

From this directory, run `node scripts/build.mjs`, `node scripts/validate.mjs`, `node scripts/test.mjs`, and `node scripts/test-zeus.mjs`. The build writes the deployable Worker bundle to `dist/`. Hosting settings are read from `.openai/hosting.json`; deployment is a separate action and is not performed by these checks.

Personal assistant conversation links and personal goal defaults are intentionally excluded from this public repository copy. Runtime data remains in the existing Hub backend.
