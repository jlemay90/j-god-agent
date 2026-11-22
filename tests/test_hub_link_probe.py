import json
import unittest
from urllib.error import HTTPError

from hub_link_probe import HubLinkError, SITE, probe, report

MARKER = "ZEUS-HUB-LINK-20261122-K7M4"
ENV = {
    "HUB_SITE_URL": SITE,
    "HUB_ZEUS_LINK_READ_ENABLED": "true",
    "HUB_SIWC_BYPASS_TOKEN": "s" * 48,
    "HUB_ZEUS_LINK_SECRET": "k" * 48,
}


class FakeResponse:
    status = 200
    def __init__(self, value):
        self.body = json.dumps(value).encode()
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, n): return self.body[:n]


def payload(**changes):
    value = {"ok": True, "source": "authenticated_live_hub_storage",
             "scope": "read_only_probe_v1", "checkedAt": "2026-11-22T19:00:00Z",
             "pulseDate": "2026-11-22", "itemCount": 104, "markerFound": False}
    value.update(changes)
    return value


class HubLinkProbeTests(unittest.TestCase):
    def test_read_only_success_and_restricted_headers(self):
        calls = []
        def open_fake(req, timeout):
            calls.append((req, timeout))
            return FakeResponse(payload())
        result = probe(MARKER, env=ENV, opener=open_fake)
        self.assertEqual(result["status"], "PASS_READ_ONLY")
        self.assertEqual(result["writeAccess"], "NOT_TESTED")
        self.assertFalse(result["markerFound"])
        req, timeout = calls[0]
        self.assertEqual(req.get_method(), "GET")
        self.assertEqual(timeout, 8)
        self.assertEqual(req.full_url.split("?")[0], SITE + "/api/zeus-link/probe")
        self.assertEqual(req.get_header("Authorization"), "Bearer " + ENV["HUB_ZEUS_LINK_SECRET"])
        self.assertEqual(req.get_header("Oai-sites-authorization"), "Bearer " + ENV["HUB_SIWC_BYPASS_TOKEN"])
        self.assertNotIn("s" * 48, result.__repr__())

    def test_explicit_disabled_and_missing_credentials_block_before_transport(self):
        for diff in [
            {"HUB_ZEUS_LINK_READ_ENABLED": "false"},
            {"HUB_SIWC_BYPASS_TOKEN": ""},
            {"HUB_ZEUS_LINK_SECRET": ""},
            {"HUB_SITE_URL": "https://evil.example"},
        ]:
            with self.subTest(diff=diff):
                env = {**ENV, **diff}
                def should_not_call(*args, **kwargs):
                    self.fail("network must not be called")
                with self.assertRaises(HubLinkError):
                    probe(MARKER, env=env, opener=should_not_call)

    def test_marker_validation_before_network(self):
        for marker in ["", "hello", "../admin", "ZEUS-HUB-LINK-20261122-short",
                       "ZEUS-HUB-LINK-20261122-K7M4?token=bad"]:
            with self.subTest(marker=marker), self.assertRaises(HubLinkError):
                probe(marker, env=ENV, opener=lambda *a, **kw: self.fail("network"))

    def test_untrusted_reply_is_rejected(self):
        for overrides in [
            {"source": "dated_git_snapshot"}, {"scope": "write"},
            {"markerFound": "false"}, {"itemCount": -1},
            {"checkedAt": None}, {"pulseDate": "yesterday"}, {"ok": False},
        ]:
            with self.subTest(overrides=overrides):
                with self.assertRaises(HubLinkError):
                    probe(MARKER, env=ENV,
                          opener=lambda req, timeout: FakeResponse(payload(**overrides)))

    def test_http_errors_do_not_reveal_tokens(self):
        def denied(req, timeout):
            raise HTTPError(req.full_url, 403, "Forbidden", {}, None)
        with self.assertRaises(HubLinkError) as cm:
            probe(MARKER, env=ENV, opener=denied)
        self.assertNotIn(ENV["HUB_SIWC_BYPASS_TOKEN"], str(cm.exception))
        self.assertNotIn(ENV["HUB_ZEUS_LINK_SECRET"], str(cm.exception))

    def test_response_size_limit(self):
        class Oversize:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, n): return b"X" * n
        with self.assertRaises(HubLinkError):
            probe(MARKER, env=ENV, opener=lambda req, timeout: Oversize())

    def test_status_is_not_claimed_as_connected(self):
        msg = json.loads(report("status"))
        self.assertIn(msg["status"], ("DRAFT_OR_DISABLED",))
        self.assertEqual(msg["writeAccess"], "NOT_AVAILABLE")


if __name__ == "__main__":
    unittest.main()
