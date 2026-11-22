# J Command Hub Site — Living Agent Handoff

Updated: 2026-11-22 · Workstream: read-only Zeus → existing Hub

## Owner-approved restricted-access decision — 2026-11-22 (latest)

- **OWNER APPROVED:** Build toward a separate, narrowly scoped, read-only credential/endpoint for Zeus, **not** distributing native Sites v28's broad HUB_RECORD_READ_TOKEN to Zeus. Keep changes in isolated development/unpublished staging and seek separate approval before deployment, production sharing/configuration changes or credentials provisioning.
- **Current true deployed Site:** native **Sites v28**, source commit fa822b5311677880c6ed7bbf2b5799dfeb473980, saved version appgprj_6aac2d807a2881918dc28045c3b5bea6~appgver_dff1902f8d9c8191842eb3785fa66084, reported by the native Sites Work read-only source audit. It is NOT a commit in the public GitHub repo; querying GitHub for that SHA returned no matching commit. DO NOT overwrite this private Site source with PR #16's public older snapshot; live My Qualities and Review Loose Ends exist but were absent in the GitHub preview output.
- **Recovery:** Native v27/v28 recovery entries exist. Sites recovery archive file_000000002fd081f5bf77ca1c5672f760 records digest sha256:4ad6edfe1c334da64f530124f78150f6539f4871c34adbaa98714b7962f0edd4; byte-level equality with a locally built tar and an actual restore remain UNVERIFIED. Native Site Work refused to edit when asked for a saved preview until this recovery gate could be proved.
- **Preview isolation:** Another in-flight native Sites/Pattern Investigator workstream observed the native Site tooling offered no isolated runtime preview URL, and its save-only path may push to the configured source branch. Its 2026-11-22 receipt stopped without editing. Do not interpret a save-only operation as an isolated preview or claim positive real R2/SIWC tests.
- **Current API security:** Sites v28 ALREADY has GET /api/v1/records/{type}/{id} authenticated by Authorization: Bearer and broad HUB_RECORD_READ_TOKEN. Full record contents are returned; it covers multiple types and has no per-record credential, so that native token is NOT the least-privilege credential authorized for Zeus. In anonymous tests, missing and synthetic invalid tokens both returned HTTP 401; a real authenticated Zeus read remains BLOCKED.
- **Existing restricted prototype:** This PR #16 provides a separate Hub-route secret HUB_ZEUS_LINK_SECRET, default-off HUB_ZEUS_LINK_READ_ENABLED, read-only GET /api/zeus-link/probe, metadata-only output and negative-auth tests. GitHub Actions exact-branch run 45069073416 PASS; **synthetic only**, against older GitHub Site source. It is useful as a reviewed implementation to PORT onto native v28 only after safe staging/source and rollback conditions are met, not as a direct deployment.
- **Alternative draft:** PR #17 adds a Zeus client calling the existing v28 broad record route (26/26 tests at run 45073063880) but is NOT selected for live deployment because it requires placing broad bearer access in Zeus. Keep PR #17 unmerged and credentials unchanged unless the owner explicitly revisits that security decision.
- **Concurrent work:** Antigravity Phase 2 project and Pattern Investigator PR #15 have independent drafts. Another Site agent has been examining native v28. Do not silently edit the same native branch, advance another agent's source, or merge competing drafts.
- **Site visibility:** Settings displayed "Visible to everyone" for the Site shell; the signed-in Hub page labels its shared data private. This public-site choice is unresolved; data API denied anonymous reads. Do NOT alter sharing without explicit owner approval.
- **Next EXECUTABLE gate:** Find an authorized **read-only export or immutable isolated checkout of native v28 source**, validate integrity/hash and review any dirty agent modifications, then build PR #16's scoped handler into a **separate local/staging runtime** with synthetic R2. Verify unauthorized access denial, zero writes, and metadata-only responses. **Do not save/publish to the native source branch** until a genuinely separate preview and recovery plan are demonstrated. Only afterward configure distinct per-route credentials privately with separate owner approval. No secrets in GitHub.

## Identity and recoverability

- App: **existing** private J Command Hub, not a replacement application. Canonical code repository: https://github.com/jlemay90/j-god-agent
- Owner goal: securely let Telegram Zeus read *current authenticated Hub storage*, first with a minimal metadata-only probe, then (only after independent live-read verification and separate authorization) consider a narrowly scoped idempotent test-note write.
- Original intent: J Command OS is a full personal operating system, not merely a task manager. Preserve current UI, owner-only access, records, R2, signed Hub→Zeus bridge, other agents' work and long-term agent/automation roadmap. Canonical manual: https://docs.google.com/document/d/1Ovl-q4PRSFYX0jwUJfyfroFIUasr9cBLLjup55yROB8/edit
- GitHub original revision: **not established** as the real deployed Site's original baseline.
- GitHub snapshot available for recovery: draft/mobile-v3 @ b2b21de512e9b0b3e98ba19731f730651e25020e, worker blob 96856282cb034ffcfd1dc52dfa19161b362ee025.
- Active Antigravity UI/Zeus baseline: feature/hub-capability-router-ui @ **205602fe2e1d5cdf4e2b0a194fc3f3afebd48a7e**, whose changes relative to draft/mobile-v3 are only hub-site/app/zeus.js and hub-site/worker/zeus.js.
- Last accepted **deployed** source revision / stable tag / recoverable live backup: **UNKNOWN — must inspect in native Sites editor before live preview or publication**. GitHub branches are not proof of deployment.
- Current isolated experiment: branch agent/chatgpt/hub-readonly-preview-20261122, draft pull request https://github.com/jlemay90/j-god-agent/pull/16 targeting the existing Antigravity branch. Do not merge it automatically.
- Related draft implementation: PR #13, https://github.com/jlemay90/j-god-agent/pull/13; exact read-only probe helper copied from there without owner data.

## What changed in the experiment

All changes are in an isolated GitHub branch and remain unmerged/undeployed:

- hub-site/worker/zeus_hub_probe.mjs — PR #13's metadata-only read handler, separately authorized via scoped key, default disabled.
- hub-site/worker/index.js — inject read-only route before generic /api route, using EXISTING storage binding and item/pulse readers. No previous routes, data schemas, permissions or write handlers removed.
- hub-site/scripts/build.mjs — embed helper into the existing single-file Worker bundle. This preserves existing data-URL test runners and Site build workflow.
- hub-site/scripts/test-hublink-preview.mjs — synthetic R2 full-Worker tests, no network and no writes to actual Hub.
- hub-site/worker/test_zeus_hub_probe.mjs — ported PR #13 negative-auth handler tests.
- .github/workflows/hub-readonly-preview.yml — GitHub Actions checks existing and new behavior, zero private credentials.
- hub-site/README.md — updated source provenance, QA instructions and deployment restrictions.
- This living handoff.

## Tests and evidence

- PR #13 read-only helper had **13/13 offline tests passed** earlier, but it is not deployed.
- **TESTED (source-level synthetic only):** GitHub Actions run [45068979443](https://github.com/jlemay90/j-god-agent/actions/runs/45068979443) passed at parent preview HEAD `a88d6cfff268766d9e9fd7df0efb9a06bb0ddbdd` (the only subsequent change is this documentation update). It successfully built and validated the existing Site bundle, ran existing Hub state/action and Zeus bridge regression scripts, passed **6/6** isolated read-only handler tests, and passed **6** end-to-end bundled-Worker checks using a fake R2 store (zero writes). CI logs independently inspected. The tests do **not** establish native Sites SIWC/owner authentication, actual deployed source, or live R2 access.
- Browser connector returned: *"Browser access requires the originating browser context"*. This chat cannot inspect the private Sites source editor or authenticate into its preview.
- Connected Hub tool returned current Hub state successfully on 2026-11-22, with a current Pulse. That establishes Hub connector state access, **not** actual deployed source code or a Zeus read.
- No real SIWC token, scoped production key, private R2, owner records, or Replit production runtime has been used in this experiment.

## Decisions, risks and unresolved questions

- **OWNER APPROVED:** Safe isolated preview development, do not publish, deploy, rotate credentials, change production, overwrite agent work or modify production data.
- **PROPOSED:** Port the minimal tested route into the exact private Sites source after native inspection, keeping existing auth/private sharing, and ensure the Sites gateway checks the service SIWC token while handler enforces a distinct scoped read key.
- **UNKNOWN:** Current Sites deployment source SHA/backup, native editor source state, Antigravity uncommitted changes, actual source deployed, bypass-token consumers, exact preview authorization capabilities. Unknowns prevent a real live preview acceptance claim.
- **RISK:** SIWC bypass alone contains no signed-in owner identity; scoped route secret must be separate, no broad /mcp exposure. Do not transfer private keys to GitHub or model prompts.
- **RISK:** The synthetic Worker fixture is NOT live R2. A mocked source label is not proof of live storage. Require independent authenticated readback.
- **REJECTED:** Copying historical GitHub worker directly over the live Site, exposing arbitrary write endpoints, creating a second Hub, or treating a green CI badge as deployment proof.

## Next single executable step

In the **native, authorized ChatGPT Sites editor** or Work with the actual EXISTING Site attached, perform read-only inspection and capture the deployed source revision, current auth/storage bindings and reversible snapshot. Compare with Antigravity baseline and PR #16 diff. Only then port the existing preview route to a private native preview, run real missing/wrong SIWC and scoped credential checks, and use the same owner-owned R2 **without any writes**. Record fresh auth/readback receipts. Ask for owner approval before any production publish/merge/reconfiguration.

## Recovery and restrictions

- No production writes or migrations were performed; simply close PR #16/delete isolated branch to abandon this experiment. PR #13 and Antigravity remain untouched.
- Do not rotate SIWC until all existing token consumers are identified and owner approves. Do not store secrets in GitHub docs, Issues, ChatGPT messages or CI.
- Consult GitHub Issues #6 (live source divergence), #12 (Hub link), and #2 (agent collision), plus .agents/skills/app-continuity/SKILL.md.
- No live Site edit, deploy, hosted preview, Telegram command invocation, Site secret change, SIWC issuance, public access change, Gemini execution or production write has occurred.
