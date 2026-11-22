# J Command Hub Site — Living Agent Handoff

Updated: 2026-11-22 · Workstream: read-only Zeus → existing Hub

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
- **This preview's own CI status must be read directly from PR #16 and its exact branch SHA.** Do not call it tested unless that run passes. Scope: existing build, Site validation, Hub state/action regression, Zeus regression, direct auth unit checks and full synthetic worker preview.
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
