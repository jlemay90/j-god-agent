"""Single-owner polling bot. Python 3.11+. See DEPLOYMENT.md before hosting."""
import asyncio
import io
import json
import logging
import os
import sqlite3
import tempfile
import time
import wave
from pathlib import Path
from j_core import upgrade_store
from j_runtime import MemoryChange, DIRECTIVE_V5, model_generate, extra_command, handle_turn

from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

ROOT = Path(__file__).resolve().parent
LOG = logging.getLogger('j')


class ToolRequest(BaseModel):
    tool: str
    argument: str = ''
    text: str = ''
    explicit: bool = False
    evidence: str = ''


class Turn(BaseModel):
    tool_requests: list[ToolRequest] = Field(default_factory=list)
    memory_changes: list[MemoryChange] = Field(default_factory=list)
    improvement_category: str = ""
    reply: str
    # Separate user instructions from quoted material; no executable code here.
    explicit_rule_request: bool
    rule: str = Field(description='Only a clear owner-requested standing behavioral rule; otherwise empty')
    needs_clarification: bool


class Store:
    """PostgreSQL for hosted persistence; SQLite only for local development."""
    def __init__(self):
        url = os.getenv('DATABASE_URL')
        self.pg = bool(url)
        if self.pg:
            import psycopg
            self.db = psycopg.connect(url, autocommit=True, connect_timeout=15)
        else:
            if os.getenv('J_ENV') == 'production':
                raise RuntimeError('Production requires DATABASE_URL for durable state')
            path = Path(os.getenv('J_DATA_DIR', str(ROOT / 'data')))
            path.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(path / 'j.sqlite3', isolation_level=None)
        self.execute('CREATE TABLE IF NOT EXISTS rules (version INTEGER PRIMARY KEY, body TEXT NOT NULL)')
        self.execute('CREATE TABLE IF NOT EXISTS turns (update_id BIGINT PRIMARY KEY, user_text TEXT NOT NULL, reply TEXT NOT NULL)')
        self.execute('CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT NOT NULL)')
        if not self.execute('SELECT version FROM rules LIMIT 1').fetchone():
            self.execute('INSERT INTO rules(version,body) VALUES (?,?)',
                         (1, (ROOT / 'master_directive.md').read_text()))

    def execute(self, sql, args=()):
        return self.db.execute(sql.replace('?', '%s') if self.pg else sql, args)

    def directive(self):
        return self.execute('SELECT version,body FROM rules ORDER BY version DESC LIMIT 1').fetchone()

    def append_rule(self, rule):
        version, body = self.directive()
        version += 1
        body += f'\n\n## Owner rule — revision {version}\n{rule}\n'
        self.execute('INSERT INTO rules(version,body) VALUES (?,?)', (version, body))
        return version

    def history(self):
        rows = self.execute('SELECT user_text,reply FROM turns ORDER BY update_id DESC LIMIT 10').fetchall()
        return [{'user': u, 'assistant': a} for u,a in reversed(rows)]

    def setting(self, key, value=None):
        if value is not None:
            self.execute('INSERT INTO settings(name,value) VALUES (?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value', (key,value))
        row = self.execute('SELECT value FROM settings WHERE name=?', (key,)).fetchone()
        return row[0] if row else None


Store = upgrade_store(Store)


async def send_text(message, text):
    # Conservative UTF-16 bound, including astral characters.
    chunk, length = '', 0
    for char in text:
        size = len(char.encode('utf-16-le')) // 2
        if length + size > 3500:
            await message.reply_text(chunk)
            chunk, length = '', 0
        chunk += char
        length += size
    if chunk:
        await message.reply_text(chunk)


def owner(update, ctx):
    return (update.effective_user is not None and update.effective_chat is not None
            and update.effective_user.id == ctx.bot_data['owner_id']
            and update.effective_chat.type == 'private')


def mirror(store):
    """DB is canonical; this markdown file is an atomic, rebuildable mirror."""
    _, body = store.directive()
    temp = ROOT / 'master_directive.md.tmp'
    try:
        temp.write_text(body)
        temp.replace(ROOT / 'master_directive.md')
        return True
    except OSError:
        temp.unlink(missing_ok=True)
        return False


async def generate(ctx, contents, *, instruction, schema=None):
    return await model_generate(ctx,contents,instruction=instruction,schema=schema)



async def speak(message, ctx, text):
    model = os.getenv('GEMINI_TTS_MODEL')
    if not model:
        return
    response = await asyncio.wait_for(ctx.bot_data['ai'].aio.models.generate_content(
        model=model, contents='Read aloud exactly:\n' + text[:2500],
        config=types.GenerateContentConfig(response_modalities=['AUDIO'],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name='Kore'))))), timeout=75)
    audio = next((p.inline_data for c in response.candidates or []
                  for p in c.content.parts or [] if p.inline_data), None)
    if not audio or not audio.data:
        raise ValueError('TTS returned no audio')
    if not (audio.mime_type or '').startswith('audio/L16'):
        raise ValueError('Expected Gemini PCM audio; check TTS model format')
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(audio.data)
    buf.seek(0)
    await message.reply_audio(audio=buf, filename='j-response.wav')


async def command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not owner(update, ctx):
        return
    message = update.effective_message
    cmd = message.text.split()[0].split('@')[0].lower()
    store = ctx.bot_data['store']
    if await extra_command(update,ctx,send_text):
        return
    if cmd == '/rules':
        _, body = store.directive()
        await message.reply_document(io.BytesIO(body.encode()), filename='master_directive.md')
    elif cmd in ('/voiceon', '/voiceoff'):
        if cmd == '/voiceon':
            await message.reply_text('Spoken replies are paused until metered. Voice memos with text replies work. Use /status and /usage to inspect J.')
            return
        if cmd == '/voiceon' and not os.getenv('GEMINI_TTS_MODEL'):
            await message.reply_text('Set GEMINI_TTS_MODEL to an available Gemini TTS model first. Text replies are active.')
            return
        store.setting('voice', 'on' if cmd == '/voiceon' else 'off')
        await message.reply_text('Spoken audio replies ' + ('enabled.' if cmd == '/voiceon' else 'disabled.'))
    elif cmd == '/forget':
        # Destructive operation requires a second explicit command.
        if ctx.args != ['confirm']:
            await message.reply_text('To delete stored conversation history, send /forget confirm. This also clears shared Zep context across Telegram and Hub. Local rules and separate memories are retained.')
        else:
            with store.atomic():
                store.execute('DELETE FROM turns')
                store.execute('DELETE FROM conversation_archive')
                store.execute('DELETE FROM reply_outbox')
                store.reset_zep('history-forget:'+str(getattr(update,'update_id',time.time_ns())))
            await message.reply_text('Stored recent conversation and searchable archive deleted. Zep context reset queued; Zep recall stays paused until cleanup succeeds. Rules and separate memories are retained. Telegram messages and provider backups are separate.')
    else:
        await message.reply_text('J is online. /status /memory /openloops /improvements /usage /trace show what is happening. Send text or a voice memo. Clear requests such as “From now on, keep answers under 100 words” update my rules. /rules exports them; /voiceon enables optional spoken replies; /forget manages history.')


async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await handle_turn(update,ctx,owner=owner,send_text=send_text,generate=generate,mirror=mirror,speak=speak,Turn=Turn)



async def on_error(update, ctx):
    LOG.error('Telegram handler error: %s', type(ctx.error).__name__)


async def startup(app):
    store=app.bot_data['store']
    if store.pg and not store.execute('SELECT pg_try_advisory_lock(?)',(app.bot_data['owner_id'],)).fetchone()[0]:
        raise RuntimeError('Another bot instance holds the owner lock')
    app.bot_data['started'] = time.monotonic()
    app.bot_data['store'].install_directive(DIRECTIVE_V5)
    mirror(app.bot_data['store'])
    from j_builder import loop
    app.bot_data['builder_task']=asyncio.create_task(loop(app))
    from j_tools import setup,reminder_loop
    setup(app.bot_data['store'])
    app.bot_data['reminder_task']=asyncio.create_task(reminder_loop(app))
    from telegram import BotCommand,BotCommandScopeChat
    try:
        await app.bot.set_my_commands([BotCommand(name,description) for name,description in [
            ('tools','Show tools and examples'),('repo','Inspect own source: status/files/read/sync'),('recall','Search retained Telegram history'),('capabilities','Map actual access and tools'),('projects','Show verified repository inventory'),('status','Inspect J runtime'),('memory','Review or correct durable memory'),
            ('tasks','List open tasks'),('task','Add or complete a task'),('remind','Set a reminder: 20m stretch'),
            ('reminders','List or cancel reminders'),('calc','Calculate arithmetic'),('web','Read a public HTTPS page'),
            ('usage','Check model usage and cost estimate'),('trace','Inspect latest request'),('autonomy','Inspect or disable retrieval improvements'),('rules','Export current operating rules')
        ]],scope=BotCommandScopeChat(chat_id=app.bot_data['owner_id']))
    except Exception as exc:
        app.bot_data['menu_last_error']=type(exc).__name__




async def shutdown(app):
    reminder=app.bot_data.get('reminder_task')
    if reminder:
        reminder.cancel()
        await asyncio.gather(reminder,return_exceptions=True)
    task=app.bot_data.get('builder_task')
    if task:
        task.cancel()
        await asyncio.gather(task,return_exceptions=True)
    await app.bot_data['ai'].aio.aclose()
    app.bot_data['ai'].close()
    app.bot_data['store'].db.close()


def main():
    logging.basicConfig(level=logging.WARNING)
    # Libraries can log token-bearing request URLs at INFO; leave them disabled.
    for name in ('httpx', 'httpcore', 'google_genai', 'telegram', 'zep_cloud'):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    token, key = os.environ['TELEGRAM_BOT_TOKEN'], os.environ['GEMINI_API_KEY']
    owner_id = int(os.environ['ALLOWED_USER_ID'])
    if owner_id <= 0:
        raise ValueError('ALLOWED_USER_ID must be a positive numerical Telegram user ID')
    app = (Application.builder().token(token).concurrent_updates(False)
           .post_init(startup).post_shutdown(shutdown).build())
    app.bot_data.update(owner_id=owner_id, store=Store(),
                        ai=genai.Client(api_key=key, http_options=types.HttpOptions(timeout=60000)))
    app.add_handler(CommandHandler(['start', 'help', 'rules', 'voiceon', 'voiceoff', 'forget', 'status', 'memory', 'openloops', 'improvements', 'usage', 'trace', 'autonomy', 'tools', 'calc', 'web', 'task', 'tasks', 'remind', 'reminders', 'recall', 'capabilities', 'projects', 'repo', 'hub'], command))
    app.add_handler(MessageHandler((filters.TEXT & ~filters.COMMAND) | filters.VOICE, handle))
    app.add_error_handler(on_error)
    # Retain pending updates across a restart; deduplicate completed requests.
    app.run_polling(allowed_updates=['message'], drop_pending_updates=False, bootstrap_retries=3)


if __name__ == '__main__':
    main()

