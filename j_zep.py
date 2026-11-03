"""Best-effort Zep Cloud v4 context and durable message ingestion."""
import datetime as dt
import asyncio
import contextlib
import hashlib
import json
import os
import uuid

CONTEXT_LIMIT = 3500
MAX_ATTEMPTS = 5
MAX_BATCH = 20


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def setup(store):
    store.execute(
        'CREATE TABLE IF NOT EXISTS zep_threads ('
        'transport TEXT NOT NULL, conversation_key TEXT NOT NULL, '
        'thread_key TEXT NOT NULL, thread_uuid TEXT, created_at TEXT NOT NULL, '
        'PRIMARY KEY(transport,conversation_key))'
    )
    store.execute(
        'CREATE TABLE IF NOT EXISTS zep_ingestion ('
        'id TEXT PRIMARY KEY, operation TEXT NOT NULL, transport TEXT NOT NULL, '
        'conversation_key TEXT NOT NULL, source_id TEXT NOT NULL, payload TEXT NOT NULL, '
        'status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, '
        'available_at TEXT NOT NULL, last_error TEXT, created_at TEXT NOT NULL, '
        'updated_at TEXT NOT NULL)'
    )
    store.execute(
        'CREATE INDEX IF NOT EXISTS zep_ingestion_ready '
        'ON zep_ingestion(status,available_at,created_at)'
    )


@contextlib.contextmanager
def _client():
    key = os.getenv('ZEP_API_KEY')
    if not key:
        yield None
        return
    import httpx
    from zep_cloud import Zep
    with httpx.Client(timeout=8, follow_redirects=False) as http:
        yield Zep(api_key=key, timeout=8, max_retries=0, httpx_client=http,
                  logging={'silent': True})


def _safe_error(exc):
    # Never persist provider messages, request URLs, payloads, or credential-bearing text.
    status = getattr(exc, 'status_code', None)
    if isinstance(status, int):
        return f'provider_{status}' if 400 <= status < 600 else 'provider_error'
    name = type(exc).__name__
    if name in {'TimeoutException', 'ConnectTimeout', 'ReadTimeout'}:
        return 'timeout'
    if name in {'ConnectError', 'NetworkError', 'RemoteProtocolError'}:
        return 'network_error'
    return 'provider_error'


def _setting_once(store, name, value):
    with store.atomic():
        row = store.execute('SELECT value FROM settings WHERE name=?', (name,)).fetchone()
        if row:
            return row[0]
        store.execute('INSERT INTO settings(name,value) VALUES (?,?) ON CONFLICT(name) DO NOTHING',
                      (name, value))
        row = store.execute('SELECT value FROM settings WHERE name=?', (name,)).fetchone()
        return row[0]


def _owner(store, client):
    owner_key = _setting_once(store, 'zep_owner_key', uuid.uuid4().hex)
    user_uuid = store.setting('zep_user_uuid')
    graph_uuid = store.setting('zep_graph_uuid')
    if user_uuid and graph_uuid:
        return user_uuid, graph_uuid
    # Resolve the persisted external identity if a create acknowledgement was lost.
    try:
        user = client.user.lookup(user_id='j-owner-' + owner_key)
    except Exception as exc:
        if getattr(exc, 'status_code', None) != 404:
            raise
        user = client.user.create(
            user_id='j-owner-' + owner_key,
            idempotency_key='j-owner-' + owner_key,
        )
    user_uuid = getattr(user, 'uuid_', None) or getattr(user, 'uuid', None)
    graph_uuid = getattr(user, 'graph_uuid', None) or user_uuid
    if not user_uuid:
        raise RuntimeError('Zep user response had no identifier')
    with store.atomic():
        store.setting('zep_user_uuid', user_uuid)
        store.setting('zep_graph_uuid', graph_uuid)
    return user_uuid, graph_uuid


def _thread(store, client, transport, conversation_key, user_uuid):
    with store.atomic():
        row = store.execute(
            'SELECT thread_key,thread_uuid FROM zep_threads '
            'WHERE transport=? AND conversation_key=?',
            (transport, conversation_key),
        ).fetchone()
        if not row:
            thread_key = uuid.uuid4().hex
            store.execute(
                'INSERT INTO zep_threads(transport,conversation_key,thread_key,created_at) '
                'VALUES (?,?,?,?) ON CONFLICT(transport,conversation_key) DO NOTHING',
                (transport, conversation_key, thread_key, _now()),
            )
            row = store.execute(
                'SELECT thread_key,thread_uuid FROM zep_threads '
                'WHERE transport=? AND conversation_key=?',
                (transport, conversation_key),
            ).fetchone()
    thread_key, thread_uuid = row
    if thread_uuid:
        return thread_uuid
    result = client.thread.create(
        user_uuid=user_uuid,
        idempotency_key='j-thread-' + thread_key,
    )
    thread_uuid = getattr(result, 'uuid_', None) or getattr(result, 'uuid', None)
    if not thread_uuid:
        raise RuntimeError('Zep thread response had no identifier')
    store.execute(
        'UPDATE zep_threads SET thread_uuid=? '
        'WHERE transport=? AND conversation_key=? AND thread_uuid IS NULL',
        (thread_uuid, transport, conversation_key),
    )
    saved = store.execute(
        'SELECT thread_uuid FROM zep_threads WHERE transport=? AND conversation_key=?',
        (transport, conversation_key),
    ).fetchone()
    return saved[0]


def _context_graph(store):
    # A pending/failed deletion is a privacy barrier, not permission to reuse stale context.
    blocked = store.execute(
        "SELECT id FROM zep_ingestion WHERE operation='reset' "
        "AND status IN ('pending','inflight','dead') LIMIT 1"
    ).fetchone()
    return None if blocked else store.setting('zep_graph_uuid')


def _fetch_context(graph_uuid, query):
    with _client() as client:
        if client is None:
            return ''
        response = client.graph.get_context(
            graph_uuid, query=query[:4000], include_results=False,
            max_characters=CONTEXT_LIMIT,
        )
        context = getattr(response, 'context', None) or ''
        return context[:CONTEXT_LIMIT] if isinstance(context, str) else ''


def retrieve_context(store, query):
    """Fetch bounded shared owner-graph reference. Never provision or import old archives."""
    try:
        graph_uuid = _context_graph(store)
        if not graph_uuid:
            return ''
        result = _fetch_context(graph_uuid, query)
        return result if _context_graph(store) == graph_uuid else ''
    except Exception as exc:
        store.setting('zep_last_error', _safe_error(exc))
        return ''


async def retrieve_context_async(store, query):
    # Only network work crosses threads: SQLite and the shared Store stay on their owner thread.
    try:
        graph_uuid = _context_graph(store)
        if not graph_uuid:
            return ''
        result = await asyncio.to_thread(_fetch_context, graph_uuid, query)
        return result if _context_graph(store) == graph_uuid else ''
    except Exception as exc:
        store.setting('zep_last_error', _safe_error(exc))
        return ''


def enqueue_turn(store, transport, conversation_key, source_id, user_text, assistant_text,
                 user_timestamp=None, assistant_timestamp=None):
    """Persist exactly one original user/assistant pair; callers include this in their transaction."""
    if not isinstance(user_text, str) or not isinstance(assistant_text, str):
        return None
    if not user_text.strip() or not assistant_text.strip():
        return None
    from j_core import redact_secret
    if redact_secret(user_text) or redact_secret(assistant_text):
        return None
    source_id = str(source_id)[:200]
    identity = hashlib.sha256((transport + '\0' + source_id).encode()).hexdigest()
    payload = {
        'messages': [
            {'role': 'user', 'content': user_text,
             'source_id': source_id, 'reference_time': user_timestamp or _now()},
            {'role': 'assistant', 'content': assistant_text,
             'source_id': source_id, 'reference_time': assistant_timestamp or _now()},
        ]
    }
    now = _now()
    store.execute(
        'INSERT INTO zep_ingestion(id,operation,transport,conversation_key,source_id,payload,'
        'status,attempts,available_at,created_at,updated_at) '
        'VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING',
        (identity, 'ingest', transport[:40], conversation_key[:300], source_id,
         json.dumps(payload, ensure_ascii=False), 'pending', 0, now, now, now),
    )
    return identity


def enqueue_reset(store, source_id):
    """Queue a provider-side owner-graph purge inside the caller's deletion transaction."""
    source_id = str(source_id)[:200]
    identity = hashlib.sha256(('reset\0' + source_id).encode()).hexdigest()
    if store.execute('SELECT id FROM zep_ingestion WHERE id=?', (identity,)).fetchone():
        return identity
    now = _now()
    # Keep content-free receipts for deduplication; remove queued copies of forgotten content.
    store.execute(
        "UPDATE zep_ingestion SET payload='{}',status=CASE "
        "WHEN status IN ('pending','inflight','dead') THEN 'cancelled' ELSE status END,updated_at=? "
        "WHERE operation='ingest'",
        (now,),
    )
    store.execute(
        'INSERT INTO zep_ingestion(id,operation,transport,conversation_key,source_id,payload,'
        'status,attempts,available_at,created_at,updated_at) '
        'VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING',
        (identity, 'reset', 'owner', 'owner', source_id, '{}',
         'pending', 0, now, now, now),
    )
    return identity


def recover(store):
    """Make interrupted claims retryable after worker restart."""
    store.execute(
        "UPDATE zep_ingestion SET status=CASE WHEN attempts>=? THEN 'dead' ELSE 'pending' END,"
        "available_at=?,updated_at=?,last_error='interrupted' "
        "WHERE status='inflight'",
        (MAX_ATTEMPTS, _now(), _now()),
    )


def _claim(store, limit):
    now = _now()
    with store.atomic():
        barrier = store.execute(
            "SELECT id FROM zep_ingestion WHERE operation='reset' "
            "AND status IN ('pending','inflight','dead') LIMIT 1"
        ).fetchone()
        rows = store.execute(
            "SELECT id,operation,transport,conversation_key,source_id,payload,attempts "
            "FROM zep_ingestion WHERE status='pending' AND available_at<=? "
            + ("AND operation='reset' " if barrier else "") +
            "ORDER BY CASE operation WHEN 'reset' THEN 0 ELSE 1 END,created_at,id LIMIT ?",
            (now, limit),
        ).fetchall()
        claimed = []
        for row in rows:
            identity = row[0]
            cursor = store.execute(
                "UPDATE zep_ingestion SET status='inflight',attempts=attempts+1,updated_at=? "
                "WHERE id=? AND status='pending'",
                (now, identity),
            )
            if cursor.rowcount:
                claimed.append((*row[:6], row[6] + 1))
        return claimed


def _complete(store, identity):
    store.execute(
        "UPDATE zep_ingestion SET status='completed',payload='{}',last_error=NULL,updated_at=? "
        "WHERE id=? AND status='inflight'",
        (_now(), identity),
    )


def _fail(store, identity, attempts, exc):
    now = _now()
    code = _safe_error(exc)
    if attempts >= MAX_ATTEMPTS:
        store.execute(
            "UPDATE zep_ingestion SET status='dead',last_error=?,updated_at=? "
            "WHERE id=? AND status='inflight'",
            (code, now, identity),
        )
        return
    delay = min(60 * (2 ** max(0, attempts - 1)), 3600)
    available = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=delay)).isoformat()
    store.execute(
        "UPDATE zep_ingestion SET status='pending',available_at=?,last_error=?,updated_at=? "
        "WHERE id=? AND status='inflight'",
        (available, code, now, identity),
    )


def _reset_owner(store, client, identity):
    user_uuid = store.setting('zep_user_uuid')
    owner_key = store.setting('zep_owner_key')
    if not user_uuid and owner_key:
        # A remote create may have succeeded before its UUID reached our transaction.
        # Do not rotate away the only durable locator until absence/deletion is confirmed.
        try:
            user = client.user.lookup(user_id='j-owner-' + owner_key)
        except Exception as exc:
            if getattr(exc, 'status_code', None) != 404:
                raise
        else:
            user_uuid = getattr(user, 'uuid_', None) or getattr(user, 'uuid', None)
            if not user_uuid:
                raise RuntimeError('Cannot confirm external owner identity for deletion')
    if user_uuid:
        try:
            client.user.delete(user_uuid, idempotency_key='j-reset-' + identity)
        except Exception as exc:
            if getattr(exc, 'status_code', None) != 404:
                raise
    with store.atomic():
        store.execute("DELETE FROM settings WHERE name IN ('zep_user_uuid','zep_graph_uuid')")
        store.setting('zep_owner_key', uuid.uuid4().hex)
        store.execute('DELETE FROM zep_threads')
        _complete(store, identity)


def process_pending(store, *, limit=MAX_BATCH):
    """Drain a bounded batch. Repeated calls process retryable work as it becomes due."""
    with _client() as client:
        if client is None:
            return 0
        count = 0
        for _ in range(max(1, min(int(limit), MAX_BATCH))):
            claimed = _claim(store, 1)
            if not claimed:
                break
            identity, operation, transport, conversation_key, source_id, raw_payload, attempts = claimed[0]
            count += 1
            try:
                if operation == 'reset':
                    _reset_owner(store, client, identity)
                elif operation == 'ingest':
                    user_uuid, _ = _owner(store, client)
                    thread_uuid = _thread(store, client, transport, conversation_key, user_uuid)
                    from zep_cloud import AddMessage
                    payload = json.loads(raw_payload)
                    messages = [
                        AddMessage(
                            role=item['role'],
                            content=item['content'],
                            name='owner' if item['role'] == 'user' else 'J',
                            reference_time=item['reference_time'],
                            metadata={
                                'source_transport': transport,
                                'source_id': source_id,
                                'source_role': item['role'],
                            },
                        )
                        for item in payload['messages']
                    ]
                    client.thread.add_messages(
                        thread_uuid,
                        messages=messages,
                        ignore_roles=['assistant'],
                        idempotency_key='j-ingest-' + identity,
                    )
                else:
                    raise ValueError('Unknown Zep queue operation')
                _complete(store, identity)
            except Exception as exc:
                store.setting('zep_last_error', _safe_error(exc))
                _fail(store, identity, attempts, exc)
        return count


def status(store):
    rows = store.execute(
        'SELECT status,COUNT(*) FROM zep_ingestion GROUP BY status'
    ).fetchall()
    return {row[0]: row[1] for row in rows}
