"""Provider-free regressions for optional recall deadlines and bounded work."""
import asyncio
import concurrent.futures
import threading
import time
import unittest
from unittest.mock import patch

import j_zep


class Store:
    def __init__(self):
        self.values = {'zep_graph_uuid': 'synthetic-graph'}
        self.owner_thread = threading.get_ident()

    def execute(self, *args):
        assert threading.get_ident() == self.owner_thread
        return self

    def fetchone(self):
        return None

    def setting(self, name, value=None):
        assert threading.get_ident() == self.owner_thread
        if value is not None:
            self.values[name] = value
        return self.values.get(name)


class RecallDeadlineTests(unittest.TestCase):
    def exercise_deadline(self, asynchronous):
        release = threading.Event()
        store = Store()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            def blocked(*args):
                release.wait(3)
                return 'late context must not be used'

            with patch.object(j_zep, '_recall_pool', pool), \
                 patch.object(j_zep, '_recall_slots', threading.BoundedSemaphore(2)), \
                 patch.object(j_zep, 'RECALL_TIMEOUT', 0.05), \
                 patch.object(j_zep, '_fetch_context', blocked):
                try:
                    started = time.monotonic()
                    if asynchronous:
                        result = asyncio.run(j_zep.retrieve_context_async(store, 'synthetic'))
                    else:
                        result = j_zep.retrieve_context(store, 'synthetic')
                    self.assertEqual(result, '')
                    self.assertLess(time.monotonic() - started, 0.5)
                    self.assertEqual(store.setting('zep_last_error'), 'timeout')
                finally:
                    release.set()
        self.assertEqual(store.setting('zep_last_error'), 'timeout')

    def test_hub_recall_has_total_deadline(self):
        self.exercise_deadline(False)

    def test_telegram_recall_has_total_deadline(self):
        self.exercise_deadline(True)

    def test_saturated_recall_skips_without_queueing_and_recovers(self):
        store = Store()
        slots = threading.BoundedSemaphore(1)
        slots.acquire()
        with patch.object(j_zep, '_recall_slots', slots), \
             patch.object(j_zep, '_fetch_context', return_value='bounded reference') as fetch:
            self.assertEqual(j_zep.retrieve_context(store, 'synthetic'), '')
            self.assertEqual(store.setting('zep_last_error'), 'recall_busy')
            fetch.assert_not_called()
            slots.release()
            self.assertEqual(j_zep.retrieve_context(store, 'synthetic'), 'bounded reference')

    def test_transport_receives_short_timeout_without_retries(self):
        from types import SimpleNamespace
        import contextlib
        calls = []

        @contextlib.contextmanager
        def client():
            def context(*args, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(context='reference')
            yield SimpleNamespace(graph=SimpleNamespace(get_context=context))

        with patch.object(j_zep, '_client', client):
            self.assertEqual(j_zep._fetch_context('synthetic', 'question'), 'reference')
        self.assertEqual(calls[0]['request_options'],
                         {'timeout_in_seconds': 1.0, 'max_retries': 0})

    def test_completion_releases_the_original_slot(self):
        from unittest.mock import Mock
        original = threading.BoundedSemaphore(1)
        replacement = threading.BoundedSemaphore(1)
        pending = concurrent.futures.Future()
        pool = Mock()
        pool.submit.return_value = pending
        with patch.object(j_zep, '_recall_slots', original), \
             patch.object(j_zep, '_recall_pool', pool):
            self.assertIs(j_zep._submit_recall('synthetic', 'question'), pending)
            with patch.object(j_zep, '_recall_slots', replacement):
                pending.set_result('reference')
        self.assertTrue(original.acquire(blocking=False))
        self.assertTrue(replacement.acquire(blocking=False))


if __name__ == '__main__':
    unittest.main()
