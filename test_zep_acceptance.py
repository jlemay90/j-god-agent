"""Additional acceptance regressions; all providers and model replies are mocked."""
import asyncio
import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import httpx
import j_zep
import j_web_bridge
import test_j_zep as fixtures


class AcceptanceTests(unittest.TestCase):
    setUp = fixtures.ZepTests.setUp
    tearDown = fixtures.ZepTests.tearDown
    reopen = fixtures.ZepTests.reopen
    finalize = fixtures.ZepTests.finalize
    due = fixtures.ZepTests.due
    payload = fixtures.ZepTests.payload

    def test_rate_limit_and_timeout_recover_without_losing_local_reply(self):
        for identity, error in enumerate((
            httpx.ReadTimeout('sensitive body'),
            type('RateLimit', (Exception,), {'status_code': 429})('sensitive body'),
        ), 1):
            self.finalize(identity)
            with patch.object(self.fake.thread, 'add_messages', side_effect=error):
                j_zep.process_pending(self.store)
            row = self.store.execute(
                'SELECT status,attempts,last_error FROM zep_ingestion WHERE source_id=?',
                ('telegram:' + str(identity),)).fetchone()
            self.assertEqual(row[:2], ('pending', 1))
            self.assertIn(row[2], ('timeout', 'provider_429'))
            self.assertTrue(self.store.seen(identity))
            self.reopen()
            j_zep.recover(self.store)
            self.due()
            j_zep.process_pending(self.store)
        self.assertEqual(j_zep.status(self.store), {'completed': 2})

    def test_corrected_preference_reaches_hub_after_restart(self):
        change = dict(kind='preference', key='answer format', value='Use paragraphs',
                      explicit=True, status='active')
        self.store.finalize(1, 'Use paragraphs', 'saved', [change], '', {})
        old = self.store.memory_rows()[0]['id']
        change.update(value='Use concise bullet points', target_id=old)
        self.store.finalize(2, 'Correction: use concise bullet points', 'saved',
                            [change], '', {})
        self.reopen()
        captured = []

        async def generate(ctx, contents, **kwargs):
            captured.append(json.loads(contents))
            return NS(text=json.dumps({'reply': 'Synthetic answer',
                                       'proposal': {'kind': 'none'}}))

        client = NS(aio=NS(aclose=AsyncMock()), close=lambda: None)
        with patch('google.genai.Client', return_value=client), \
             patch('j_runtime.model_generate', side_effect=generate), \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'synthetic-test-key'}):
            j_web_bridge.generate_reply(self.store, self.payload('build'))
        active = captured[0]['durable_reference']
        self.assertTrue(any(m['value'] == 'Use concise bullet points' for m in active))
        self.assertFalse(any(m['value'] == 'Use paragraphs' for m in active))
        self.assertEqual(len(self.store.memory_rows(True)), 2)

    def test_missing_owner_mapping_cannot_recall_another_owners_graph(self):
        self.assertEqual(j_zep.retrieve_context(self.store, 'private marker'), '')
        self.assertEqual(self.fake.graph_queries, [])
        self.finalize()
        j_zep.process_pending(self.store)
        self.assertEqual(self.fake.threads[0]['user_uuid'], self.store.setting('zep_user_uuid'))


if __name__ == '__main__':
    unittest.main()
