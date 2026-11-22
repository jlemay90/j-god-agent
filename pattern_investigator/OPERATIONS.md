# J Command OS — Pattern Investigator: five-capability integration (v0.2)

**Revision:** November 22, 2026. **Status:** STAGED SOURCE + SYNTHETIC TESTS ONLY; not merged, installed, scheduled, connected or verified live. The owner's goal is an AI that helps him build an exceptional life through better evidence-backed decisions, recovered opportunities and effective learning—not an engagement or streak counter.

This package extends [the existing v0.1 evidence gate](../PATTERN-INVESTIGATOR.md) without editing Hub, Zeus, production code, private records or existing automations. No new memory database or public owner data. It must never be called a hands-off assistant until real integrated acceptance is complete.

## Five capabilities (truthful receipts)

| Capability | Staged file | What it really does | What is NOT done |
| --- | --- | --- | --- |
| **Eyes** | `eyes.py`, `site_evidence_route.mjs` | Pinned read-only HTTPS client with independent SIWC/route credentials; proposed Site handler returns ONLY explicitly approved structured evidence with owner-reported provenance. Negative auth must make zero storage reads. | Route is NOT on the live private Site. Existing Zeus probe returns metadata only and cannot substitute. Nothing reads general notes automatically. |
| **Brain** | `engine.py`, `brain.py` | Groups independently dated, source-linked recurring observations, detects counterexamples, considers alternatives and suggests small experiments that require approval. No causal or psychological diagnoses. | This is **deterministic** analysis of pre-tagged evidence, not a real autonomous LLM research worker or independent external verification. |
| **Schedule** | `worker_cli.py`, `ledger.py`, staged systemd timers | Atomic one-run-per-local-day claim, private 0600 SQLite receipts, local daily 07:35 CT timer template and manual CLI. | No installed timer, cloud worker or running automation. |
| **Supervisor** | `service.py`, staged hourly watchdog timer | A second process checks a dated run by 08:35 CT, queues deduped alerts, identifies failures, staleness and stalls. | No external monitor of VM/timer health; if the VM dies both processes can die. Cloud Monitoring or another independent monitor remains a release gate. |
| **Voice** | `voice.py`, alert outbox | Owner-only Telegram notifications, disabled by default. Provider `message_id` means accepted, **not handset delivered**. No source text sent, only status and counts. | No Telegram token, owner chat ID, delivery permission, test message or verified handset receipt configured. |

## Non-negotiable access control

The repository is **PUBLIC**. Never commit real Hub records, a token, raw experiment notes, transcripts, health information, family details or stored findings. Site access must remain owner-only. SIWC bypass tokens alone do not establish owner identity; require separate strong route secret and explicit item-ID allowlist. Use the currently issued SIWC token if owner-authorized; **never rotate it without inspecting consumers**. Only an inspected, exact Sites worker may host the new path `GET /api/pattern-investigator/evidence`. Its results are based on approved `patternEvidence` structured annotations, not scraping every task/note. The handler downranks every Hub annotation to `owner_reported`; an owner-entered tag cannot magically become `original_verified`. For original proof, compare with real external source separately.

**Site PRIVATE configuration (NOT installed):** `HUB_PATTERN_READ_ENABLED=true`, `HUB_PATTERN_LINK_SECRET=<distinct-secret>`, `HUB_PATTERN_ALLOWED_ITEM_IDS=<comma-separated-verified-opted-in-ids>`. Existing SIWC service controls stay enabled. The staged route is **never** authorized for write.

**Worker PRIVATE configuration (NOT installed):** `HUB_SIWC_BYPASS_TOKEN`, `HUB_PATTERN_LINK_SECRET`, `PATTERN_RUN_ENABLED=true`, `PATTERN_LEDGER_PATH=/var/lib/j-command-os/pattern/pattern.sqlite`. For notifications, separately enable `PATTERN_ALERT_SEND_ENABLED=true` and set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_OWNER_CHAT_ID` from existing owner-authorized secret store. **Never paste credentials into ChatGPT or GitHub.** `PATTERN_ALERT_SEND_ENABLED` remains false until owner authorizes messages. No chargeable model API calls occur.

## Private VM installation design (NOT performed)

1. Check correct Google Cloud VM ownership, deployed source, current Antigravity work, valid backups, host operating system, credential consumers, and GitHub PR conflicts. This is a staged design, not an instruction to overwrite running Zeus. Do **not** run systemd units in an unverified production VM.
2. After owner approves, use a separate `jpattern` service account, readonly code checkout at `/opt/j-command-os`, private `/var/lib/j-command-os/pattern` directory mode 0700, private environment `/etc/j-command-os/pattern.env` mode 0600 readable only by the service account. Do not grant root or blanket project permissions.
3. Validate the actual Sites handler in an isolated Site preview, including 403 with zero storage reads, missing route key, wrong Site token, zero write capability, and correct source revision. Compare retrieved read-only observations with existing authorized Hub state. Then run manually with a small opt-in evidence bundle.
4. Run syntax/unit/integration tests, at least three real consenting evidence cases, source contradictions, source-outage drills, duplicate run/restart, forged auth/redirect, and private log inspection. Confirm host local timezone and DST behavior. Ensure no source record appears in provider messages.
5. Install staged `deploy/j-pattern-run.{service,timer}` and `deploy/j-pattern-watchdog.{service,timer}` only after separate deploy approval. Verify service/timer status and last/next calendar trigger with `systemctl list-timers`; invoke one run and read the private SQLite receipt. The watchdog does not make itself independent merely by being in another service on the same VM.
6. Add an OUTSIDE-HOST health monitor (e.g. a Google Cloud Monitoring heartbeat/alert to the owner) that detects loss of the VM/timer/watchdog itself. Prove a forced missed-run and offline-host alert actually reaches the owner. Until verified, mark `SUPERVISION_NOT_INDEPENDENT`.
7. Obtain owner approval for the specific Telegram test; send a harmless synthetic alert; verify provider acceptance and **owner's actual handset reception** separately. Dedupe provider retries; exactly-once notification delivery cannot be guaranteed after an ambiguous network failure.
8. Run **seven real calendar days** with one daily read-only investigation, daily receipts, weekly review link, and independent alert logs. Measure source coverage, false patterns, unsupported certainty, missed-run detection latency, cost and actual practical value. No automation may send external case messages, change Hub records, purchase, diagnose, or run experiments without separate consent.

### Safe commands (only after authorized private installation)

`python -m unittest discover -s tests -p 'test_pattern_*.py' -v`  
`node --test pattern_investigator/test_site_evidence_route.mjs`  
`python -m pattern_investigator.worker_cli status --db /var/lib/j-command-os/pattern/pattern.sqlite`  
`python -m pattern_investigator.worker_cli run-once --db /var/lib/j-command-os/pattern/pattern.sqlite`  
`python -m pattern_investigator.worker_cli watch --db /var/lib/j-command-os/pattern/pattern.sqlite`  
`python -m pattern_investigator.worker_cli dispatch --db /var/lib/j-command-os/pattern/pattern.sqlite`  

The scheduled service uses `--notify` but real sends stay blocked unless `PATTERN_ALERT_SEND_ENABLED=true`.

## Acceptance and real-life feedback

A reliable pilot needs **zero unauthorized data reads/writes**, **zero confident personality/causality claims based on a single event**, **zero invented source checks**, a real fresh observation source, reproducible evidence IDs, a genuinely useful owner-approved recommendation, an independently detected missed-run and a delivered test alert. If no meaningful insight appears, report **NO_FINDINGS**, not an invented discovery. Every finding must say whether it is a hypothesis or verified outcome and preserve alternatives/counterevidence. Flag gaps; do not force patterns to fit.

**Unblocked next action:** Verify the exact deployed private Hub Site and the owner's VM, then review the staged security contract before enabling a read-only Site preview. This is an owner approval gate; it is NOT a request for credentials in chat.

Sources: canonical private J Command OS manual §§7–9, 22–25, 27–28; Hub Pattern Investigator Idea `4615433f-b6a7-4f13-8927-da76639b06dd`; GitHub issues #2, #6, #12; existing draft PRs #8, #9, #13, #14.
