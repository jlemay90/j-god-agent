# J RUN — bounded mission controller v0.1 (isolated draft)

**Status: locally tested control plane, not deployed and not an autonomous AI worker.**

This is a small provider-independent foundation for the proposed J Command OS RUN, WATCH, and RESUME capabilities. The owner wants an assistant that can work for a specified time or count of work cycles, save verified progress, and restart without repeating risky actions. The existing Zeus autonomy builder has a *different*, narrowly scoped purpose. This prototype does not change it.

## Implemented in this isolated module

- Create a mission with a hard maximum number of work cycles, elapsed wall-clock deadline, and an optional ceiling based on a worker-reported usage cost.
- Assign a unique idempotency key per cycle. Save durable SQLite checkpoints and timestamped events in transactions; support process restart.
- Re-check cycle, time and reported usage limits between cycles. Record a receipt for each completed checkpoint.
- If a worker throws an error or a process disappears during an in-flight action, fail closed instead of automatically replaying uncertain side effects.
- After independently verifying the outcome, an operator may record a completed external action WITHOUT replay or mark an action verified to have had no effect before resuming.
- Separate worker execution from controller logic so future adapters can use a bounded, authorized and independently verified read-only tool set.

## Test on a local machine

Python 3.10+; no extra dependencies.

Run: python -m unittest discover -s tests -p test_run_controller.py -v

Run demonstration: python -m run_controller.cli --db /tmp/j-run-demo.sqlite demo --cycles 5 --seconds 3600

This demonstration records five deterministic local checkpoints. It is NOT five real AI research cycles. Do not commit the resulting SQLite database, token records, or private mission content to the public GitHub repository.

## Important safety and deployment limitations

- There is NO AI provider, live Hub connector, Zeus bridge, business API, marketplace monitor, Telegram job, scheduler, background daemon, external email or shopping/payment capability here. The program cannot continue when the host process is stopped.
- The controller cannot forcibly interrupt a blocked Python worker call. Future worker adapters MUST enforce independent per-call timeouts, allowlisted actions, permission gates and per-call cost ceilings. A reported budget is not proof of real billing and cannot by itself prevent overspending within a single call.
- SQLite transactions protect controller state, but exactly-once external side effects require the provider's idempotency or an authoritative external receipt. No human can be replaced by a fabricated AI confirmation.
- The default no-cost limit (0) means no *accounted* dollar limit is configured, NOT authorization for spending or model calls.
- Do not place private Hub history, sensitive case records, secrets, or live tokens in this public repository or a shared test database.

## Next acceptance gate before any real execution

1. Choose one low-cost READ-ONLY mission adapter and confirm its source environment, permissions, billing, and version independently.
2. Add measured usage receipts, a worker-call timeout, safe external provider idempotency, and owner-only access. Test actual crash recovery and rejection of concurrent duplicate worker claims.
3. Execute five actual read-only AI-assisted cycles, inspect checkpoints against their sources, quantify costs and elapsed time, and record failure cases.
4. Separately test hosted scheduling/continuation, secure persistent storage and the actual private Hub integration; obtain owner approval for any merge/deployment.

## Source and handoff

Original owner intent: J Command OS is a persistent personal AI operating system, not a task list. Its canonical private manual, Hub records and Index remain separate; GitHub main is NOT proof of the deployed private Sites app. Reuse the existing repository continuity policy at .agents/skills/app-continuity/SKILL.md and coordinate against Issue #2 and Issue #6. This draft branch touches only run_controller/ and tests/test_run_controller.py. It does not overwrite AGENT-HANDOFF.md, already part of other active agent coordination work. The draft PR is the scoped review and rollback record.

Baseline main commit: 0c15ebb323c072aa4a748b31089e3e91bf2b1221. Rollback: close the draft PR/delete this isolated branch; no production migration or data mutation occurred.
