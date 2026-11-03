"""Synthetic Zep integration checks. Never use live providers or existing owner data."""
import asyncio
import contextlib
import datetime as dt
import json
import os
import tempfile
import unittest
import uuid
from types import SimpleNamespace as NS
from unittest.mock import patch

from telegram_agent_bot import Store, Turn
import j_zep as zep
import j_web_bridge as web


class ProviderError(Exception):
    status_code = 503


class MissingUser(Exception):
    status_code = 404


class FakeZep:
    def __init__(self):
        self.users, self.threads, self.deliveries, self.calls, self.deletes = [], [], {}, [], []
        self.fail = False
        self.context = 'Historical reference'
        self.user = NS(create=self.create_user, delete=self.delete_user, lookup=self.lookup_user)
        self.thread = NS(create=self.create_thread, add_messages=self.add_messages)
        self.graph = NS(get_context=self.get_context)
        self.graph_queries = []

    def create_user(self, **kwargs):
        if not kwargs.get('first_name'):
            raise ValueError('Cloud v4 requires an owner display name')
        assert uuid.UUID(kwargs['idempotency_key']).version == 4
        self.users.append(kwargs)
        return NS(uuid_='user-' + str(len(self.users)), graph_uuid='graph-' + str(len(self.users)))

    def lookup_user(self, **kwargs):
        for i, user in enumerate(self.users, 1):
            if user['user_id'] == kwargs['user_id']:
                return NS(uuid_='user-' + str(i), graph_uuid='graph-' + str(i))
        raise MissingUser()

    def delete_user(self, user_uuid, **kwargs):
        if self.fail:
            raise ProviderError('credential-bearing-provider-body-must-not-persist')
        self.deletes.append(user_uuid)

    def create_thread(self, **kwargs):
        assert uuid.UUID(kwargs['idempotency_key']).version == 4
        self.threads.append(kwargs)
        return NS(uuid_='thread-' + str(len(self.threads)))

    def add_messages(self, thread_uuid, **kwargs):
        assert uuid.UUID(kwargs['idempotency_key']).version == 4
        self.calls.append((thread_uuid, kwargs))
        if self.fail:
            raise ProviderError('credential-bearing-provider-body-must-not-persist')
        self.deliveries.setdefault(kwargs['idempotency_key'], (thread_uuid, kwargs))

    def get_context(self, graph_uuid, **kwargs):
        self.graph_queries.append((graph_uuid, kwargs))
        if self.fail:
            raise ProviderError('credential-bearing-provider-body-must-not-persist')
        return NS(context=self.context)


class ZepTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            'DATABASE_URL': '', 'J_ENV': 'test', 'J_DATA_DIR': self.temp.name,
            'GEMINI_MODEL': 'synthetic', 'ZEP_API_KEY': '',
        })
        self.env.start()
        self.store = Store()
        self.fake = FakeZep()

        @contextlib.contextmanager
        def client():
            yield self.fake
        self.client_patch = patch('j_zep._client', client)
        self.client_patch.start()

    def tearDown(self):
        self.client_patch.stop()
        self.store.db.close()
        self.env.stop()
        self.temp.cleanup()

    def reopen(self):
        self.store.db.close()
        self.store = Store()

    def finalize(self, identity=1, text='synthetic orchard decision', reply='Final reply', **kwargs):
        return self.store.finalize(identity, text, reply, [], '', {}, **kwargs)

    def payload(self, panel='today'):
        return {'requestId': str(uuid.uuid4()), 'panel': panel,
                'message': 'What should I do next?',
                'context': {'schema': 1, 'section': panel, 'today': '2026-11-03'},
                'history': [{'role': 'user', 'text': 'Do not import this old archive'}]}

    def due(self):
        self.store.execute("UPDATE zep_ingestion SET available_at='2000-01-01' WHERE status='pending'")

    def test_final_reply_roles_source_dates_and_replay_are_exact(self):
        stamp = '2026-11-03T10:00:00+00:00'
        reply = self.store.finalize(1, 'Be concise', 'Actual answer', [], 'Use concise prose', {},
                                    user_timestamp=stamp)
        self.assertIn('Saved rule revision', reply)
        self.assertIsNone(self.store.finalize(1, 'Be concise', 'Different answer', [], '', {}))
        self.assertEqual(zep.process_pending(self.store), 1)
        _, call = next(iter(self.fake.deliveries.values()))
        user, assistant = call['messages']
        self.assertEqual((user.role, assistant.role), ('user', 'assistant'))
        self.assertEqual(user.content, 'Be concise')
        self.assertEqual(assistant.content, reply)
        self.assertEqual(user.reference_time, stamp)
        self.assertEqual(user.metadata['source_id'], 'telegram:1')
        self.assertEqual(user.metadata['source_transport'], 'telegram')
        self.assertEqual(call['ignore_roles'], ['assistant'])
        self.assertEqual(self.store.execute('SELECT payload FROM zep_ingestion').fetchone()[0], '{}')
        self.assertEqual(zep.process_pending(self.store), 0)

    def test_both_transports_share_owner_but_keep_thread_mappings_after_restart(self):
        self.finalize()
        p = self.payload()
        result = web.process(self.store, p, lambda *_: ({'reply': 'Hub final reply'}, 1))
        self.assertEqual(web.process(self.store, p, lambda *_: self.fail('No replay model call')), result)
        self.assertEqual(zep.process_pending(self.store), 2)
        self.assertEqual(len(self.fake.users), 1)
        self.assertEqual(len(self.fake.threads), 2)
        self.assertTrue(all(t['user_uuid'] == 'user-1' for t in self.fake.threads))
        self.assertEqual(len(self.fake.deliveries), 2)
        for _, call in self.fake.deliveries.values():
            self.assertNotIn('Do not import this old archive', str(call['messages']))
        original = self.store.execute('SELECT transport,thread_uuid FROM zep_threads ORDER BY transport').fetchall()
        self.reopen()
        self.finalize(2)
        p['requestId'] = str(uuid.uuid4())
        web.process(self.store, p, lambda *_: ({'reply': 'Another final reply'}, 1))
        zep.process_pending(self.store)
        self.assertEqual(len(self.fake.users), 1)
        self.assertEqual(len(self.fake.threads), 2)
        self.assertEqual(original, self.store.execute('SELECT transport,thread_uuid FROM zep_threads ORDER BY transport').fetchall())

    def test_source_roles_remain_correct_when_voice_is_transcribed(self):
        from j_runtime import handle_turn
        sent = []

        async def download(path):
            path.write_bytes(b'synthetic-audio')

        async def get_file():
            return NS(download_to_drive=download)

        async def generate(ctx, contents, **kwargs):
            if kwargs.get('schema') is None:
                return NS(text='My orchard decision was to wait.')
            return NS(text=json.dumps(dict(reply='Understood.', explicit_rule_request=False,
                                           rule='', needs_clarification=False)))

        async def send(message, text):
            sent.append(text)

        async def reply(text):
            sent.append(text)

        message = NS(text=None, voice=NS(file_size=10, duration=1, get_file=get_file),
                     date=dt.datetime(2026, 11, 3, tzinfo=dt.timezone.utc), reply_text=reply)
        update = NS(update_id=10, effective_message=message, effective_chat=NS(id=1))
        ctx = NS(bot_data={'store': self.store, 'started': 0})
        asyncio.run(handle_turn(update, ctx, owner=lambda *_: True, send_text=send,
                                generate=generate, mirror=lambda *_: True, speak=None, Turn=Turn))
        raw = json.loads(self.store.execute('SELECT payload FROM zep_ingestion').fetchone()[0])
        self.assertEqual(raw['messages'][0]['content'], 'My orchard decision was to wait.')
        self.assertEqual(raw['messages'][1]['content'], 'Understood.')
        self.assertEqual(len(raw['messages']), 2)
        self.assertEqual(sent, ['Transcript: My orchard decision was to wait.', 'Understood.'])

    def test_failed_ingestion_is_bounded_sanitized_and_not_a_failed_local_turn(self):
        self.finalize()
        self.fake.fail = True
        for attempt in range(zep.MAX_ATTEMPTS):
            self.due()
            self.assertEqual(zep.process_pending(self.store), 1)
        row = self.store.execute('SELECT status,attempts,last_error FROM zep_ingestion').fetchone()
        self.assertEqual(row, ('dead', zep.MAX_ATTEMPTS, 'provider_503'))
        self.assertEqual(zep.process_pending(self.store), 0)
        self.assertEqual(self.store.history()[0]['assistant'], 'Final reply')
        self.assertNotIn('credential-bearing', str(row))

    def test_crash_after_provider_ack_reuses_same_idempotency_key(self):
        self.finalize()
        with patch('j_zep._complete', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                zep.process_pending(self.store)
        self.reopen()
        zep.recover(self.store)
        self.assertEqual(zep.process_pending(self.store), 1)
        self.assertEqual(len(self.fake.calls), 2)
        self.assertEqual(len(self.fake.deliveries), 1)
        self.assertEqual(self.fake.calls[0][1]['idempotency_key'],
                         self.fake.calls[1][1]['idempotency_key'])

    def test_retrieval_is_shared_bounded_async_and_failure_safe(self):
        self.finalize()
        zep.process_pending(self.store)
        self.fake.context = 'untrusted text ' * 1000
        result = asyncio.run(zep.retrieve_context_async(self.store, 'question'))
        self.assertEqual(len(result), zep.CONTEXT_LIMIT)
        graph, params = self.fake.graph_queries[-1]
        self.assertEqual(graph, 'graph-1')
        self.assertEqual(params['max_characters'], zep.CONTEXT_LIMIT)
        self.fake.fail = True
        self.assertEqual(zep.retrieve_context(self.store, 'question'), '')
        self.assertEqual(self.store.setting('zep_last_error'), 'provider_503')

    def test_confirmed_deletion_blocks_context_and_clears_queued_copies(self):
        change = dict(kind='preference', key='length', value='short', explicit=True)
        self.store.finalize(1, 'Keep it short', 'Okay', [change], '', {})
        zep.process_pending(self.store)
        old_owner = self.store.setting('zep_owner_key')
        self.finalize(2)
        identity = self.store.memory_rows()[0]['id']
        self.assertTrue(self.store.forget_memory(identity))
        self.assertEqual(zep.retrieve_context(self.store, 'length'), '')
        self.assertEqual(self.fake.graph_queries, [])
        self.assertTrue(all(r[0] == '{}' for r in self.store.execute('SELECT payload FROM zep_ingestion').fetchall()))
        self.assertEqual(self.store.execute('SELECT COUNT(*) FROM conversation_archive').fetchone()[0], 2)
        zep.process_pending(self.store)
        self.assertEqual(self.fake.deletes, ['user-1'])
        self.assertNotEqual(self.store.setting('zep_owner_key'), old_owner)
        self.assertIsNone(self.store.setting('zep_graph_uuid'))
        self.finalize(3)
        zep.process_pending(self.store)
        self.assertEqual(len(self.fake.users), 2)

    def test_failed_cleanup_blocks_new_ingestion_and_context(self):
        self.finalize()
        zep.process_pending(self.store)
        with self.store.atomic():
            self.store.reset_zep('synthetic-forget')
        self.finalize(2)
        self.fake.fail = True
        for _ in range(zep.MAX_ATTEMPTS):
            self.due()
            zep.process_pending(self.store)
        self.assertEqual(zep.status(self.store)['dead'], 1)
        self.assertEqual(zep.status(self.store)['pending'], 1)
        self.assertEqual(zep.retrieve_context(self.store, 'anything'), '')
        self.assertEqual(len(self.fake.deliveries), 1)

    def test_hub_completion_and_queue_write_are_atomic(self):
        p = self.payload()
        with patch.object(self.store, 'queue_zep_turn', side_effect=RuntimeError('synthetic queue failure')):
            with self.assertRaises(RuntimeError):
                web.process(self.store, p, lambda *_: ({'reply': 'final'}, 1))
        row = self.store.execute('SELECT status,result FROM hub_web_requests').fetchone()
        self.assertEqual(row, ('failed', None))
        self.assertEqual(zep.status(self.store), {})

    def test_unconfigured_provider_retains_queue_and_local_fallback(self):
        self.finalize()

        @contextlib.contextmanager
        def absent():
            yield None

        with patch('j_zep._client', absent):
            self.assertEqual(zep.process_pending(self.store), 0)
            self.assertEqual(zep.retrieve_context(self.store, 'question'), '')
        self.assertEqual(zep.status(self.store), {'pending': 1})
        self.assertTrue(self.store.seen(1))

    def test_owner_create_ack_loss_resolves_persisted_external_identity(self):
        self.finalize()
        setting = self.store.setting

        def interrupted(name, value=None):
            if name == 'zep_user_uuid' and value:
                raise KeyboardInterrupt()
            return setting(name, value)

        with patch.object(self.store, 'setting', interrupted):
            with self.assertRaises(KeyboardInterrupt):
                zep.process_pending(self.store)
        self.reopen()
        zep.recover(self.store)
        zep.process_pending(self.store)
        self.assertEqual(len(self.fake.users), 1)
        self.assertEqual(self.store.setting('zep_user_uuid'), 'user-1')

    def interrupt_owner_creation(self):
        self.finalize()
        setting = self.store.setting

        def interrupted(name, value=None):
            if name == 'zep_user_uuid' and value:
                raise KeyboardInterrupt()
            return setting(name, value)

        with patch.object(self.store, 'setting', interrupted):
            with self.assertRaises(KeyboardInterrupt):
                zep.process_pending(self.store)
        self.reopen()
        self.assertIsNone(self.store.setting('zep_user_uuid'))
        self.assertTrue(self.store.setting('zep_owner_key'))

    def test_confirmed_forget_deletes_owner_after_create_ack_loss(self):
        from telegram_agent_bot import command
        self.interrupt_owner_creation()
        old_key = self.store.setting('zep_owner_key')
        replies = []

        async def reply(text):
            replies.append(text)

        update = NS(update_id=2, effective_message=NS(text='/forget confirm', reply_text=reply),
                    effective_user=NS(id=1), effective_chat=NS(id=1, type='private'))
        ctx = NS(bot_data={'store': self.store, 'owner_id': 1}, args=['confirm'])
        asyncio.run(command(update, ctx))
        self.assertEqual(self.store.setting('zep_owner_key'), old_key)
        self.assertEqual(zep.retrieve_context(self.store, 'old information'), '')
        zep.process_pending(self.store)
        self.assertEqual(self.fake.deletes, ['user-1'])
        self.assertNotEqual(self.store.setting('zep_owner_key'), old_key)
        self.assertEqual(zep.status(self.store), {'cancelled': 1, 'completed': 1})

    def test_uncertain_lookup_after_create_ack_loss_keeps_cleanup_pending(self):
        self.interrupt_owner_creation()
        old_key = self.store.setting('zep_owner_key')
        with self.store.atomic():
            self.store.reset_zep('synthetic-forget-after-interruption')
        with patch.object(self.fake.user, 'lookup', side_effect=ProviderError('sensitive body')):
            zep.process_pending(self.store)
        self.assertEqual(self.store.setting('zep_owner_key'), old_key)
        self.assertEqual(zep.status(self.store), {'cancelled': 1, 'pending': 1})
        self.assertEqual(self.fake.deletes, [])
        self.assertEqual(zep.retrieve_context(self.store, 'old information'), '')
        self.due()
        zep.process_pending(self.store)
        self.assertEqual(self.fake.deletes, ['user-1'])
        self.assertNotEqual(self.store.setting('zep_owner_key'), old_key)

    def test_installed_v4_sdk_serializes_roles_times_and_idempotency_headers(self):
        import httpx
        from zep_cloud import Zep
        requests = []

        def handle(request):
            body = json.loads(request.content) if request.content else {}
            requests.append((request.method, request.url.path, body, request.headers))
            if 'lookup' in request.url.path:
                return httpx.Response(404, json={'message': 'not found'})
            if request.url.path.endswith('/users'):
                return httpx.Response(201, json={'uuid': 'sdk-user', 'graph_uuid': 'sdk-graph'})
            if request.url.path.endswith('/threads'):
                return httpx.Response(201, json={'uuid': 'sdk-thread'})
            if request.url.path.endswith('/messages'):
                return httpx.Response(202, json={})
            if request.url.path.endswith('/context'):
                return httpx.Response(200, json={'context': 'SDK historical reference'})
            self.fail('Unexpected SDK endpoint: ' + request.url.path)

        with httpx.Client(transport=httpx.MockTransport(handle)) as http:
            client = Zep(api_key='synthetic-test-key', httpx_client=http, max_retries=0)

            @contextlib.contextmanager
            def sdk_client():
                yield client

            self.finalize(user_timestamp='2026-11-03T10:00:00+00:00')
            with patch('j_zep._client', sdk_client):
                zep.process_pending(self.store)
                self.assertEqual(zep.status(self.store), {'completed': 1})
                self.assertEqual(zep.retrieve_context(self.store, 'question'), 'SDK historical reference')
        message = next(r for r in requests if r[1].endswith('/messages'))
        self.assertEqual([m['role'] for m in message[2]['messages']], ['user', 'assistant'])
        self.assertEqual(message[2]['messages'][0]['reference_time'], '2026-11-03T10:00:00+00:00')
        self.assertEqual(str(uuid.UUID(message[3]['Idempotency-Key'])),
                         message[3]['Idempotency-Key'])


if __name__ == '__main__':
    unittest.main()
