# J RUN — isolated Gemini read-only five-cycle pilot

**Status as of 2026-11-22:** Draft branch only. A Python worker, 15 mocked worker tests and one five-cycle SQLite integration test exist. **Not live**: Gemini inference, authenticated five-cycle provider run, hosting, scheduling, Hub/Zeus integration, deployment, billing verification, or owner-facing notification.

## Objective and source boundaries

Prove five authentic Gemini-assisted, read-only evidence reviews using existing J RUN v0.1 checkpoints, a time limit, explicit cost estimation, an approved public evidence manifest, and human-reviewed source receipts. This is an incremental child of draft PR #9, not a new task manager or parallel memory database.

Worker accepts **pre-reviewed public snapshots only**, restricted to source links on github.com, docs.github.com and ai.google.dev. It never fetches a link, invokes a model tool, writes the Hub, sends email, bids, purchases or contacts a third party. Only the official Gemini Developer API receives the prompt; assume supplied excerpts are transmitted to Google. The "public" boolean is a manual owner/operator assertion, not a secret-detection guarantee. Do NOT put personal Hub data, credential values, account records or private documents into the manifest or public repository.

## Owner authorization and verified provider rate (2026-11-22)

The owner approved a **single five-cycle pilot** with **up to $0.05 of estimated Gemini API model usage**. This does NOT authorize other spending, new hosting, model changes, production credentials being exposed or altered, automatic retries, or future paid recurring jobs. Current real model calls and billed usage for this pilot: **none verified**. Execution is BLOCKED until the existing Google Cloud/Gemini project, isolated runner, credential access and billing tier are confirmed.

Candidate model: `gemini-2.5-flash-lite`, using Gemini Developer API **standard** text rates independently checked 2026-11-22: **$0.10 per million input tokens, $0.40 per million output tokens**. Official primary source: https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-flash-lite . Rate estimates are not hard billing caps; the runner must separately confirm this model's availability, account tier and project charges before authorizing a paid call.

The connected desktop remote agent was offline at inspection, and this ChatGPT execution environment has no Gemini credentials. No production Zeus settings have been changed.

## Two-step gate

**1. Offline preview, no credentials or network:**

    python -m run_controller.gemini_pilot \
      --manifest run_controller/examples/public_evidence_five.json \
      --db "$HOME/.local/state/jrun-private/gemini-five.sqlite" \
      --model gemini-2.5-flash-lite \
      --input-price-per-million 0.10 \
      --output-price-per-million 0.40 \
      --max-usd 0.05 --max-seconds 300 --preview

**2. Only after the owner verifies the current exact model, billing tier, per-million rates and approves a bounded model call:**

Place GEMINI_API_KEY in the authorized isolated host's *private secret manager*, not this repository, source manifest, command arguments, chat, logs or screenshots. Execute the same command WITHOUT "--preview" but WITH "--authorize-model-calls" in an isolated host where the working directory/database is private, not a shared deployment. No automatic retries.

Model access and pricing vary by project. Validate the model with the provider before authorization. Reference: https://ai.google.dev/gemini-api/docs/pricing and https://ai.google.dev/gemini-api/docs/tokens .

## Guards implemented

- Exactly five public source tasks for the pilot; small fixed source/prompt size caps and approved HTTPS hostnames.
- Refuses group/other-accessible checkpoint directories and files; new mission state is created with private permissions, without changing existing unrelated directories.
- Requires BOTH GEMINI_API_KEY and explicit --authorize-model-calls before creating a model mission.
- Gemini REST countTokens preflight; no generateContent call when estimated remaining budget is inadequate.
- Per-request socket timeout 15 seconds by default; 256-token output cap; no model tool calls or provider grounding.
- Estimates cost with an explicitly supplied rate card and usageMetadata after each model call; stores source URL, source-text SHA-256, response ID, provider token counts, estimated USD and a human-review flag in SQLite via the existing controller.
- Rejects missing usage, wrong source ID, malformed JSON, invalid checkpoint, empty credential or overbudget response. In-flight errors transition to needs_review in J RUN; do not automatically replay uncertain inference.
- Restart requires SAME public manifest hash, model, rates, estimated budget and a READY state; no release of an unresolved in-flight cycle.

**Important limitations:** Actual provider billing may differ from these estimates because rates, free-tier eligibility, ancillary charges and model behavior change; a per-request socket timeout is not a hard end-to-end process deadline. Preflight is best-effort risk reduction, not an absolute billing or latency guarantee. Failed calls can still incur charges. The underlying controller's wall-clock limit is enforced *between* cycles. A completed AI answer is **not independently verified factual accuracy**, and every finding is marked for human review.

## Verification

Locally tested 15 mocked worker tests plus one five-cycle SQLite interrupted/resumed integration test with the exact original parent controller source (controller git blob SHA matched PR #9). External Gemini API was **not** contacted. The already-existing controller in PR #9 reports 13 local deterministic tests. Before claiming an integrated pass: execute full original and new suites together against the EXACT checked-out branch, run a five-cycle real Gemini pilot with manually reviewed public sources, verify response IDs/usage from the provider, test injected outage and restart recovery, inspect actual charges, and record negative-auth and concurrent duplicate-dispatch behavior.

For a new or interrupted run, use the existing J RUN controller's signed human/operator reconciliation; never automatically resume a needs_review mission based on a model guess.

## Coordination and next promotion gate

Scope is restricted to new files under run_controller and tests; the parent PR #9 remains draft, and main/live Sites/Zeus are unchanged. Follow Issue #2 multi-agent collision rules, Issue #6 live Sites source reconciliation, and the existing app-continuity handoff. This draft branch can be abandoned without data migrations or changes to production. Approval for any separate hosting, automation, merge or deployment remains a distinct gate.

**Completion criteria:** five authentic AI inference cycles, five verified provider usage receipts, five source-hashed evidence records, actual restart/no-duplicate test, observed billing limits, owner review of usefulness and safety; then an informed decision on an authenticated read-only private runtime.
