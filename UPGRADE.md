Current operator guide: QUICKSTART.md. The tools upgrade supersedes earlier capability descriptions below.

# J continuity upgrade

## Implemented
- Source-backed structured memory: preferences, facts, projects, goals, decisions,
  constraints and commitments. Only model-proposed explicit records with a verbatim
  evidence excerpt in the current message are eligible for automatic storage.
- Stable keys and correction links; previous versions are superseded. Exact matching
  is deterministic, but model key selection and interpretation can still be wrong.
- Bounded keyword retrieval (up to 12 memories / 6,500 characters), plus up to ten
  recent turns / 16,000 characters. This is not semantic vector search. Inspection
  of all records is available through /memory; retrieval can miss relevant records.
- Rule changes, memories, response history, processed-update IDs and traces commit
  in one transaction. Completed updates are not replayed after history pruning.
  Telegram delivery itself is still not exactly-once.
- /status /memory /openloops /improvements /usage /trace. Owner-only private chat.
- Direct corrections: /memory correct ID replacement text.
- Deletion: /memory delete ID, then /memory delete ID confirm. Removes the linked
  correction chain. Does not purge conversations, provider data, Telegram or backups.
- Improvement backlog for model-suggested owner feedback and sanitized error classes.
  Records evidence references, expected benefit, risk, validation, status and counts.
  This does not execute engineering changes or scheduled background work.
- Gemini usage metadata saved per call; token totals and estimated cost shown in
  /usage. Reasoning/thinking counts are included when provided. Missing usage remains unknown and is flagged as incomplete; failed calls
  still count toward the request cap. Transient provider failures no longer pause
  all later calls for the day. This acknowledgment retains unknown counts and possible
  unrecorded charges; it does not fabricate usage.
- Default local limits: 100 model calls per UTC day; stop starting calls once recorded
  daily tokens reach 200,000; 60,000 combined text input/context characters; 2,048
  maximum output tokens per call. Voice can use two calls. These controls are not
  a provider-enforced dollar cap. A call already started can cross the token
  threshold. Other keys/apps/provider charges are outside this ledger.
- Recognizes common Google/OpenAI/Telegram credential patterns before model calls.
  This is best-effort detection, not comprehensive secret/PII anonymization.
- Existing spoken output paused until its usage path is metered; incoming voice
  transcription with text replies remains available.
- v5 continuity commitments appended to the canonical rule database on first
  upgraded startup. Existing owner rule revisions preserved; markdown refreshed.

## Configuration
GEMINI_MODEL remains gemini-3.1-flash-lite. No provider or pricing upgrade.
Optional environment configuration:
J_DAILY_REQUEST_LIMIT (100)
J_DAILY_TOKEN_LIMIT (200000)
J_MAX_INPUT_CHARS (60000)
J_MAX_OUTPUT_TOKENS (2048)
J_INPUT_USD_PER_MILLION (.25)
J_OUTPUT_USD_PER_MILLION (1.5)
Cost assumptions checked November 2, 2026, official Gemini pricing. Update them
when model/prices change. Costs exclude hosting and separately generated audio.

## Validation
python -m unittest test_j_core -v
python check_contract.py
The latter makes TWO synthetic live Gemini calls and writes only a temporary DB.
It checks explicit rule/preference extraction, quoted instruction/hypothetical
rejection, allowlist checks, inspection commands and actual usage metadata.
These tests sample behavior; they do not prove every future model interpretation.
PostgreSQL integration and hosted restart durability require a production database.
No continuous hosting has been configured by this upgrade.

## Recovery
A timestamped private_backups directory contains the pre-upgrade Python file,
markdown export and canonical rules/history/settings snapshot. This workspace
uses PostgreSQL; a JSON record snapshot was created without exporting credentials. It is excluded from Git. Back up these files
securely; the database snapshot contains personal conversation records.
Do not restore a database snapshot casually: it discards records written afterward.
For code-only rollback, stop the bot, restore the backed-up Python file and restart.
The original bot ignores added tables; v5 directive revisions remain in the DB.

## Remaining work
- 24/7 hosting, production PostgreSQL, monitored restarts and backups.
- Connected external action tools and permission-bounded engineering execution.
- Retrieval quality evaluation, advanced semantic search only if justified.
- More robust privacy scrubbing and provider-enforced budget controls.
- Due dates, scheduling, reconciliation across external canonical project stores.

## Replit environment fix
Automatic import guessing installed an unrelated telegram package. It is disabled
in .replit. The working bot runs from .venv with PYTHONPATH unset.
Install using: env -u PYTHONPATH -u PIP_TARGET -u PIP_PREFIX PIP_CONFIG_FILE=/dev/null PIP_USER=false .venv/bin/python -m pip install -r requirements.txt
Run using: env -u PYTHONPATH .venv/bin/python telegram_agent_bot.py
PostgreSQL migration/transaction/replay tests also passed in connection-local
temporary tables; no synthetic records were added to canonical tables.
