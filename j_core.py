"""Durable, provider-independent state for J. No model calls or secret logging."""
import contextlib
import datetime as dt
import hashlib
import json
import re
import time
import uuid

KINDS = {'preference', 'fact', 'project', 'goal', 'decision', 'constraint', 'commitment'}
ACTIVE = ('active', 'open', 'done', 'superseded', 'deleted')


def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def redact_secret(text):
    return bool(re.search(r'AIza[\w-]{20,}|\b\d{6,}:[\w-]{20,}|\bsk-[\w-]{16,}', text))


class LimitReached(Exception):
    pass


def upgrade_store(Base):
    class State(Base):
        def __init__(self):
            super().__init__()
            self.execute('CREATE TABLE IF NOT EXISTS memories (id TEXT PRIMARY KEY, kind TEXT NOT NULL, mkey TEXT NOT NULL, value TEXT NOT NULL, evidence TEXT NOT NULL, source_id TEXT NOT NULL, confidence TEXT NOT NULL, status TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL, supersedes TEXT)')
            self.execute('CREATE INDEX IF NOT EXISTS memory_lookup ON memories(kind,mkey,status)')
            self.execute('CREATE TABLE IF NOT EXISTS improvements (id TEXT PRIMARY KEY, category TEXT NOT NULL, evidence TEXT NOT NULL, benefit TEXT NOT NULL, risk TEXT NOT NULL, validation TEXT NOT NULL, status TEXT NOT NULL, occurrences INTEGER NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL)')
            self.execute('CREATE TABLE IF NOT EXISTS usage (id TEXT PRIMARY KEY, day TEXT NOT NULL, created TEXT NOT NULL, model TEXT NOT NULL, purpose TEXT NOT NULL, input_tokens BIGINT, output_tokens BIGINT, thinking_tokens BIGINT, total_tokens BIGINT, estimated_cost DOUBLE PRECISION, outcome TEXT NOT NULL, duration_ms INTEGER NOT NULL)')
            self.execute('CREATE TABLE IF NOT EXISTS traces (update_id BIGINT PRIMARY KEY, created TEXT NOT NULL, details TEXT NOT NULL)')
            self.execute('CREATE TABLE IF NOT EXISTS processed (update_id BIGINT PRIMARY KEY)')
            self.execute('INSERT INTO processed(update_id) SELECT update_id FROM turns WHERE 1=1 ON CONFLICT DO NOTHING')
            from j_context import setup as setup_context
            setup_context(self)

        @contextlib.contextmanager
        def atomic(self):
            if self.pg:
                with self.db.transaction():
                    yield
            else:
                self.db.execute('BEGIN IMMEDIATE')
                try:
                    yield
                    self.db.execute('COMMIT')
                except BaseException:
                    self.db.execute('ROLLBACK')
                    raise

        def seen(self, update_id):
            return bool(self.execute('SELECT update_id FROM processed WHERE update_id=?', (update_id,)).fetchone())

        def memory_rows(self, include_history=False):
            sql = 'SELECT id,kind,mkey,value,evidence,source_id,confidence,status,created,updated,supersedes FROM memories'
            if not include_history:
                sql += " WHERE status IN ('active','open')"
            sql += ' ORDER BY updated DESC,id'
            cols = ('id','kind','key','value','evidence','source_id','confidence','status','created','updated','supersedes')
            return [dict(zip(cols, r)) for r in self.execute(sql).fetchall()]

        def relevant(self, text, limit=12, max_chars=6500):
            records=self.memory_rows()
            ranking={}
            try:
                from j_ranker import scores
                ranking=scores(records[:1000],text)
            except Exception:
                pass  # retain deterministic baseline if extension fails
            words = set(re.findall(r'\w{3,}', text.lower())) - {'the','and','that','this','with','what','have','for','you','are','can'}
            def score(m):
                if m['id'] in ranking:
                    return ranking[m['id']]
                terms = set(re.findall(r'\w{3,}', (m['key']+' '+m['value']).lower()))
                overlap = len(words & terms)
                baseline = {'preference': 3, 'goal': 2, 'constraint': 2, 'commitment': 1}.get(m['kind'], 0)
                return overlap*5 + baseline
            candidates = sorted(records, key=lambda m: (score(m), m['updated']), reverse=True)
            selected, used = [], 0
            for m in candidates:
                if score(m) <= 0 or len(selected) >= limit:
                    continue
                compact = {k:m[k] for k in ('id','kind','key','value','confidence','status','source_id')}
                size = len(json.dumps(compact))
                if used + size <= max_chars:
                    selected.append(compact)
                    used += size
            return selected

        def _apply_memory(self, change, source_id, evidence):
            kind = change.get('kind')
            key = re.sub(r'\s+', ' ', change.get('key','').strip().lower())[:100]
            value = change.get('value','').strip()
            # Only explicit supported durable facts are eligible for auto-storage.
            if kind not in KINDS or not key or not value or len(value)>1500 or not change.get('explicit') or redact_secret(value):
                return None
            if len(evidence)>12000 or redact_secret(evidence):
                return None
            status = change.get('status','active')
            if status not in ('active','open','done'):
                return None
            if kind == 'commitment' and status == 'active':
                status = 'open'
            rows = self.memory_rows()
            target = change.get('target_id')
            old = next((m for m in rows if target and m['id']==target), None)
            if target and old is None:
                return None
            if old:
                kind, key = old['kind'], old['key']
            else:
                old = next((m for m in rows if m['kind']==kind and m['key']==key), None)
            if old and old['value']==value and old['status']==status:
                return None
            if old:
                self.execute("UPDATE memories SET status='superseded',updated=? WHERE id=?", (utcnow(), old['id']))
            now = utcnow()
            identity = uuid.uuid4().hex[:12]
            self.execute('INSERT INTO memories(id,kind,mkey,value,evidence,source_id,confidence,status,created,updated,supersedes) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                         (identity,kind,key,value,evidence,source_id,'explicit',status,now,now,old['id'] if old else None))
            return identity

        def improve(self, category, evidence, benefit='Reduce repeated failures and owner effort.', risk='Review required before engineering changes.', validation='Reproduce failure, add a regression check, compare before/after.'):
            # Canonicalized categories aggregate repeated failures without raw prompts.
            category = re.sub(r'[^a-zA-Z0-9_. -]','',category)[:100]
            identity = hashlib.sha256(category.encode()).hexdigest()[:12]
            now = utcnow()
            self.execute('INSERT INTO improvements(id,category,evidence,benefit,risk,validation,status,occurrences,created,updated) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET occurrences=improvements.occurrences+1,updated=excluded.updated',
                         (identity,category,evidence[:500],benefit,risk,validation,'proposed',1,now,now))

        def reserve_call(self, model, purpose, daily_requests=100, daily_tokens=200000):
            day = utcnow()[:10]
            with self.atomic():
                if self.pg:
                    self.execute('SELECT pg_advisory_xact_lock(?)', (847102031,))
                rows = self.execute('SELECT total_tokens,outcome FROM usage WHERE day=?', (day,)).fetchall()
                if len(rows) >= daily_requests:
                    raise LimitReached('Daily model request limit reached.')
                if sum(r[0] or 0 for r in rows) >= daily_tokens:
                    raise LimitReached('Daily recorded token threshold reached.')
                identity = uuid.uuid4().hex
                self.execute('INSERT INTO usage(id,day,created,model,purpose,outcome,duration_ms) VALUES (?,?,?,?,?,?,?)',
                             (identity,day,utcnow(),model,purpose,'reserved',0))
                return identity

        def finish_call(self, identity, metadata, outcome, duration_ms, input_price=.25, output_price=1.5):
            def field(name):
                value = getattr(metadata, name, None) if metadata else None
                return int(value) if value is not None else None
            inp, out, thought, total = (field('prompt_token_count'),field('candidates_token_count'),field('thoughts_token_count'),field('total_token_count'))
            # Missing optional thinking count is represented by the API as no thinking.
            if thought is None and metadata is not None:
                thought = 0
            cost = ((inp*input_price+(out+thought)*output_price)/1e6
                    if inp is not None and out is not None and thought is not None else None)
            self.execute('UPDATE usage SET input_tokens=?,output_tokens=?,thinking_tokens=?,total_tokens=?,estimated_cost=?,outcome=?,duration_ms=? WHERE id=?',
                         (inp,out,thought,total,cost,outcome,duration_ms,identity))

        def usage_summary(self):
            day = utcnow()[:10]
            rows = self.execute('SELECT input_tokens,output_tokens,thinking_tokens,total_tokens,estimated_cost,outcome FROM usage WHERE day=?', (day,)).fetchall()
            return {'day_utc':day,'calls':len(rows),'input_tokens':sum(r[0] or 0 for r in rows),
                    'output_tokens':sum(r[1] or 0 for r in rows),'thinking_tokens':sum(r[2] or 0 for r in rows),
                    'total_tokens_recorded':sum(r[3] or 0 for r in rows),
                    'estimated_usd_recorded':sum(r[4] or 0 for r in rows),
                    'calls_with_unknown_usage':sum(r[3] is None for r in rows),
                    'cost_estimate_incomplete':any(r[4] is None for r in rows),
                    'limits':'Local daily call cap; recorded-token threshold checked before each call. Not a provider dollar cap; in-flight calls can cross the token threshold.'}

        def finalize(self, update_id, text, reply, changes, rule, trace):
            with self.atomic():
                if self.seen(update_id):
                    return None
                saved = []
                for change in changes[:5]:
                    identity = self._apply_memory(change, 'telegram:'+str(update_id), text)
                    if identity:
                        saved.append(identity)
                revision = None
                if rule and not redact_secret(rule):
                    revision = self.append_rule(rule)
                if revision:
                    reply += '\n\nSaved rule revision '+str(revision)+': '+rule
                if saved:
                    reply += '\n\nMemory updated: '+', '.join(saved)
                trace.update(saved_memory_ids=saved,rule_revision=revision)
                self.execute('INSERT INTO turns(update_id,user_text,reply) VALUES (?,?,?)', (update_id,text,reply))
                self.execute('INSERT INTO conversation_archive(update_id,user_text,reply,captured_at) VALUES (?,?,?,?) ON CONFLICT DO NOTHING', (update_id,text,reply,utcnow()))
                self.execute('INSERT INTO processed(update_id) VALUES (?)', (update_id,))
                self.execute('INSERT INTO traces(update_id,created,details) VALUES (?,?,?)', (update_id,utcnow(),json.dumps(trace)))
                self.execute('DELETE FROM turns WHERE update_id NOT IN (SELECT update_id FROM turns ORDER BY update_id DESC LIMIT 100)')
                self.execute('DELETE FROM traces WHERE update_id NOT IN (SELECT update_id FROM traces ORDER BY update_id DESC LIMIT 100)')
                return reply

        def forget_memory(self, identity):
            # Purge the correction chain so superseded versions don't retain content.
            rows = self.memory_rows(True)
            linked = {identity}
            changed = True
            while changed:
                previous = len(linked)
                for m in rows:
                    if m['id'] in linked or m['supersedes'] in linked:
                        linked.add(m['id'])
                        if m['supersedes']:
                            linked.add(m['supersedes'])
                changed = len(linked)>previous
            found = any(m['id']==identity for m in rows)
            if found:
                with self.atomic():
                    for item in linked:
                        self.execute('DELETE FROM memories WHERE id=?', (item,))
            return found

        def install_directive(self, addition):
            if self.setting('continuity_upgrade') == 'v5':
                return
            with self.atomic():
                version = self.append_rule(addition)
                self.setting('continuity_upgrade','v5')
            return version
    return State
