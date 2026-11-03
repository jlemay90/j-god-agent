"""Real HTTP checks; no accounts, models or owner database are used."""
import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from j_web_bridge import Handler


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, path, method='GET', body=None):
        connection = HTTPConnection(*self.server.server_address, timeout=2)
        try:
            connection.request(method, path, body=body)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_public_health_is_content_free_and_does_not_open_storage(self):
        with patch('telegram_agent_bot.Store', side_effect=AssertionError('No database allowed')):
            for path in ('/', '/healthz'):
                self.assertEqual(self.request(path), (200, {'ok': True, 'service': 'zeus'}))
        self.assertEqual(self.request('/hub/chat')[0], 405)
        with patch.object(Handler, 'secret', 'test-only-signing-key-not-for-deployment'):
            self.assertEqual(self.request('/hub/chat', 'POST', '{}')[0], 401)

    def test_health_remains_available_during_a_blocked_chat_request(self):
        started, release = threading.Event(), threading.Event()

        def blocked(handler):
            started.set()
            release.wait(3)
            handler.respond({'ok': False}, 503)

        with patch.object(Handler, 'do_POST', blocked):
            worker = threading.Thread(target=lambda: self.request('/hub/chat', 'POST', '{}'))
            worker.start()
            try:
                self.assertTrue(started.wait(1))
                self.assertEqual(self.request('/healthz')[0], 200)
            finally:
                release.set()
                worker.join(2)


if __name__ == '__main__':
    unittest.main()
