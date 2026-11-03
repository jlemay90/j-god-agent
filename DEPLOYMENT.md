# J Telegram agent — deployment and limits

This is a deployment starter, not a live or production-certified service. Python
3.11+ required. No credentials are included. The five requested files are at the
root; this guide and .gitignore are supporting files.

## 1. Create your Telegram bot
Open https://t.me/BotFather, verify the official account, send /newbot, choose a
name and username, and copy the token directly into Replit Secrets. Never commit
or paste it into a chat. A token holder can control the bot. Revoke leaked tokens
through BotFather.

## 2. Identify the allowed owner
Open https://t.me/userinfobot and obtain your numeric user ID. This is a third-party
bot; alternatively get your own ID from Telegram's getUpdates response before
starting polling, using Telegram's official Bot API. Use your USER ID, not the bot
ID or username. Store it as ALLOWED_USER_ID. Group messages are always rejected.

## 3. Private GitHub repository
Create a PRIVATE repository named j-god-agent at https://github.com/new. Extract
the supplied archive, then upload its contents, including .gitignore. Do not
upload data/, .env, tokens, or real audit results. The running markdown mirror can
contain personal operational rules: review it before future commits.

## 4. Replit setup
Import the private GitHub repository in Replit and choose Python 3.11+.
Create a Gemini API key at https://aistudio.google.com/apikey. Review API pricing,
provider data handling, and account limits before using personal conversations.

Set these Secrets in the workspace AND published deployment:

- TELEGRAM_BOT_TOKEN: BotFather token
- ALLOWED_USER_ID: your positive numeric user ID
- GEMINI_API_KEY: Google API key
- GEMINI_MODEL: gemini-flash-latest (or a tested model available to your account)
- J_ENV: production for hosted operation
- DATABASE_URL: a dedicated production PostgreSQL connection string
- Optional GEMINI_TTS_MODEL: an available Gemini speech generation model

PostgreSQL is canonical for versioned rules, settings, and the last 100 completed
turns. The bot feeds the last ten turns into responses. master_directive.md is an
atomic export/mirror rebuilt from PostgreSQL on startup. Editing the seed markdown
after DB initialization does not overwrite stored rules. /rules exports current
rules. This avoids trusting a deployment's writable filesystem for persistence.
Use a production database, not the development database. Set up provider backups.

Build command:

    pip install -r requirements.txt

Run command:

    python telegram_agent_bot.py

Choose a Reserved VM background worker for long polling. Ordinary editor Run is
for testing, not a 24/7 deployment. Run exactly ONE instance per bot token; stop
the workspace test process before starting the deployment. Do not enable multiple
replicas. Hosting/API charges and outages still apply. Set provider spend alerts.

## 5. Acceptance checks before relying on it
1. Send /start and a text question from your account.
2. Check another Telegram account and a group receive no responses.
3. Send a short voice memo and verify the displayed transcript and text response.
4. Send “From now on, keep answers under 100 words.” Check the exact saved rule.
5. Send /rules, restart, and verify the rule remains.
6. Redeploy and verify the SAME production database retains that rule.
7. If TTS configured, send /voiceon and confirm an audio attachment arrives.
8. Disable/revoke a test API key and confirm the bot reports failure without secrets.

Optional spoken replies are WAV audio attachments, not Telegram OGG voice bubbles.
Incoming voice is transcribed via Gemini; speech errors can affect rule extraction.
Use text for precise rule changes. Empty/unclear transcripts request repetition.

## What is implemented
Owner/private-chat checks, bounded inputs, sequential processing, temporary audio
cleanup, structured model replies, natural-language rule extraction, append-only
rule revisions, bounded conversation storage, export, and optional speech output.
Masking and counterfactual auditing are standalone opt-in utilities; the bot does
not blindly remove useful identity context from ordinary conversation.

No API-backed live integration test has been performed without your credentials.
Dependency ranges are bounded but not a reproducible lockfile; after acceptance,
freeze the tested environment with pip freeze > requirements.lock.txt.

## Limits to address before critical production use
- In-process rate limiting; single-instance operation only.
- Model-classified rule extraction is fallible; review saved revisions.
- Rule insert and conversation insert are separate commits: a crash between them
  can duplicate a rule on replay. Delivery is not exactly-once.
- A long-lived database connection can fail; process restart may be needed.
- No scheduled jobs, live browsing, external actions, or autonomous self-edit loop.
- History is stored in plaintext in your database; audio is sent to Google and
  transits Telegram. Telegram bots are not end-to-end encrypted conversations.
- /forget confirm deletes conversation rows, not provider logs, Telegram messages,
  backups, or rule revisions. Keep credentials out of messages and rule requests.

## Capability growth is an engineering goal
A directive can drive improvement when the agent has tools to carry it out. A
next-stage builder should inspect failures, propose changes on a GitHub branch,
run tests in isolation, demonstrate results, and preserve rollback. Installing new
connectors, changing hosting and monitoring, and redeploying can improve tool
coverage and uptime. They require real integrations, credentials, budgets and
permissions; this starter does not yet implement that loop. Do not grant the live
chat process unrestricted shell execution as a shortcut.

## Bias utilities
identity_masker.mask(text, known_entities={"Jane Smith": "PERSON"}) returns masked
text plus a JSON-serializable restoration map. restore performs a single-pass
replacement. Heuristics are incomplete: this is not a privacy guarantee.

For the auditor, make a template file containing {demographic}, identical relevant
qualifications, and a precise binary decision criterion. Then run:

    python counterfactual_auditor.py template.txt --groups Christian Muslim --trials 5

This makes paid API calls. Output includes all model decisions/rationales, positive
rates, rate gap and modal agreement. Tied groups are excluded from modal agreement
and reported. Agreement is not proof of fairness, and differences can reflect
noise, prompting, relevant context or model bias. Do not use it as a standalone
employment, lending, medical or legal decision system.

## Official references
- https://github.com/googleapis/python-genai
- https://ai.google.dev/gemini-api/docs/audio
- https://ai.google.dev/gemini-api/docs/speech-generation
- https://docs.python-telegram-bot.org/en/stable/
- https://core.telegram.org/bots/tutorial
- https://core.telegram.org/bots/api#getupdates
- https://docs.replit.com/references/publishing/reserved-vm-deployments
- https://docs.replit.com/references/data-and-storage/production-databases
