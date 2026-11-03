# Zeus context and capability supply

The runtime now supplies a timestamped local state snapshot on each conversational
request: model, usage ledger, limits, rule revision, memory counts, actual callable
tools, command shortcuts, available local skills and separately labelled outside
resources. This uses no extra model call. The request's own usage is recorded after
the snapshot; numbers are therefore accurate as of the supplied snapshot time.

`j_context.py` owns the runtime inventory and four application guidance skills:
capture, recover, challenge and verify. Relevant skills are selected for a turn.
They do not install ChatGPT's hosted skills or grant account access.

`resource_catalog.json` records ten GitHub repositories verified through the
owner's ChatGPT connector on November 3, 2026. This is a dated metadata inventory,
not a code import or live GitHub connection. Empty repos are labelled. The existing
J Command Hub, Drive, Gmail, Calendar and NotebookLM remain separate systems;
Zeus does not inherit their authentication. No personal Hub records were copied.

## History and recall

The PostgreSQL database remains canonical for Zeus state. The archive migration
copies the conversation turns still retained at upgrade time; it cannot recover
older pruned messages. New completed conversational turns are archived atomically
with memories, rules and traces. Recent context remains ten turns (bounded to
16,000 characters), while the archive retains future turns through restarts.

Relevant history is selected lexically from the latest 2,000 archived turns, with
owner wording weighted higher than assistant prose. At most three excerpts are
automatically supplied, bounded to 3,200 characters. These are dated/source-ID
references, not new instructions or verified facts. Older migrated turns have no
invented capture timestamp. This is keyword retrieval, not exhaustive semantic
search or access to other ChatGPT conversations.

`/recall topic words` returns matching retained excerpts. The model can request
`recall` or `inspect` using evidence from the current owner message. Inspection
is restricted to usage, status, capabilities, projects, improvements, tasks and
reminders. It has no account, shell, purchasing or external-send privileges.

`/forget confirm` now deletes both recent turns and the searchable archive. Rules,
separate durable memories, Telegram messages, traces, provider retention and
backups remain separate. No history was deleted during commissioning.

## Commands

- `/usage`, `/status`, `/improvements`, `/openloops` and `/tasks` have readable reports.
- `/capabilities` distinguishes callable tools, commands and unavailable integrations.
- `/projects` shows the dated repo inventory.
- `/recall words` searches retained Telegram conversation.
- Clear direct usage/status/capability/recall requests can run locally without a
  model call, even during a provider outage. Other usage questions can be answered
  from fresh supplied state, with no
  additional model call. Explicit inspection requests can use the read-only tool.

## Remaining integration work

An actual Hub/Drive/Gmail/Calendar bridge requires separately scoped account access
and authentication. Do not copy ChatGPT's credentials or claim a catalog entry is
a connection. Reuse the existing Hub as its source of truth if a bridge is added;
avoid creating independent copies of its tasks. Alternative model providers and
uninterrupted hosting remain separate work. Historical sensitive records are not
imported by this upgrade.
