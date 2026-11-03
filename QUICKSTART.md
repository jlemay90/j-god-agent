# J — quick start
Open https://t.me/Lemayzeusbot. J's Telegram command menu lists its tools.

## Talk normally
J uses Gemini for conversation, a bounded recent window, and relevant durable memory.
Try: "Keep answers concise from now on."
Try: "Calculate (40+10)*1.1."
Try: "Remind me in 20 minutes to stretch."
For a public webpage, include its exact HTTPS URL and ask J to read it.
Task intentions can be captured naturally; /tasks lists saved open commitments.
Voice memos are transcribed and answered in text. Spoken output remains paused.

## Direct controls (no Gemini call for the command itself)
- /tools — tool guide
- /calc (40+10)*1.1 — bounded arithmetic
- /web https://example.com — read public HTML/text, no logged-in accounts
- /task add call the tax attorney — save a task
- /tasks — list open tasks and IDs
- /task done ID — complete a task
- /remind 20m stretch — relative reminder (m/h/d), 1 minute to 30 days
- /reminders — pending/failed reminders
- /reminders cancel ID — cancel a pending reminder

## Inspect and correct
- /status — runtime, model and capability information
- /memory — durable records; /memory show ID; /memory correct ID replacement
- /memory delete ID — shows the explicit deletion command
- /openloops — unfinished commitments
- /usage — recorded Gemini usage and estimated cost
- /trace — observable events from the last conversational request
- /rules — current directive export
- /improvements — evidence-backed improvement backlog
- /autonomy — code-builder scope and latest result
- /autonomy off — stop future automatic code builds

## Costs and availability
A normal text exchange typically uses one Gemini call. A voice memo typically
uses two. Natural-language tool interpretation uses the conversational call;
direct slash tools above require no Gemini generation. Automatic code improvement
may use up to two model calls in one daily attempt, when a matching issue is queued.
Local defaults: 100 calls and a 200,000 recorded-token threshold per UTC day.
The recorded-token threshold can be crossed by in-flight calls. Unknown provider
usage remains unknown; it is not counted as zero or represented as an exact bill.
Failed calls still count toward the request cap. The provider may enforce lower
per-minute/day quotas. Provider daily resets use Pacific time, separate from J's
local UTC accounting. Actual project quotas: https://aistudio.google.com/rate-limit
No free-tier or all-day-use guarantee is made.

Gemini supplies inference. Replit runs the process, supervisor and workers.
The working workspace has not been verified as permanent 24/7 hosting.
Reminders persist across restart and overdue reminders are attempted after recovery.
They can be late while the host sleeps. Network/crash timing can cause duplicate
delivery; retry failures are visible in /reminders. Do not rely on this alone for
critical deadlines until continuous hosting and delivery are proven.

## Data and boundaries
Records live in the app's canonical PostgreSQL database. GitHub stores code and
documentation; runtime credentials and personal backups are not committed.
Public-page reading blocks private addresses and follows only revalidated public
HTTPS redirects. Pages are untrusted data, not instructions.
Automatic code edits remain confined to the pure retrieval helper, with policy,
isolation, regression tests, benchmark improvement and Git history.
No email/calendar/account access, purchasing, general computer control, or broad
app-building authority has been connected. Core/hosting purchases are unchanged.
