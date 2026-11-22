import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from hub_scoped_pulse import (
    verify_scoped_pulse, readiness, report, ScopedHubError, SITE, MAX_REPLY_BYTES,
)
from hub_link_probe import report as telegram_report

KEY = "a" * 64
REQUEST_ID = "ZEUS-HUB-LINK-20261122-K7M4"
ENV = {
    "HUB_ZEUS_SCOPED_READ_TOKEN": KEY,
    "HUB_ZEUS_SCOPED_READ_ENABLED": "true",
    "HUB_SITE_URL": SITE,
}


class FakeResponse:
    status = 200
    def __init__(self, data=None, raw=None, status=200):
        self.status = status
        self.raw = raw if raw is not None else json.dumps(data if data is not None else {
            "ok": True,
            "source": "existing_hub_r2_pulse",
            "scope": "pulse_metadata_only_v1",
            "pulseDate": "2026-11-22",
            "checkedAt": "2026-11-22T21:00:00Z",
            "requestId": REQUEST_ID,
            "storageReadCount": 1,
            "writes": 0,
        }).encode("utf8")
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, count):
        return self.raw[:count]


def verify(opener, env=ENV):
    return verify_scoped_pulse(env=env, opener=opener,
                               request_id=REQUEST_ID,
                               now=datetime(2026, 11, 22, tzinfo=timezone.utc))


class ScopedZeusTests(unittest.TestCase):
    def test_one_read_only_request_and_metadata_receipt(self):
        calls = []
        def opener(req, timeout):
            calls.append((req, timeout))
            return FakeResponse()
        result = verify(opener)
        self.assertEqual(result["status"], "PASS_READ_ONLY")
        self.assertEqual(result["pulseDate"], "2026-11-22")
        self.assertEqual(result["storageReadCount"], 1)
        self.assertEqual(result["writes"], 0)
        self.assertFalse(result["responseBodyExposed"])
        self.assertEqual(len(calls), 1)
        req, timeout = calls[0]
        self.assertEqual(req.get_method(), "GET")
        self.assertEqual(timeout, 8)
        self.assertEqual(req.full_url, SITE + "/api/zeus-link/probe?requestId=" + REQUEST_ID)
        self.assertEqual(req.get_header("Authorization"), "Bearer " + KEY)
        self.assertNotIn(KEY, json.dumps(result))
        self.assertNotIn("HUB_RECORD_READ_TOKEN", json.dumps(result))

    def test_readiness_is_not_false_success(self):
        self.assertEqual(readiness(env=ENV)["status"], "READY_NOT_VERIFIED")
        self.assertEqual(readiness(env={})["status"], "BLOCKED_NOT_CONFIGURED")

    def test_disabled_fails_before_network(self):
        with self.assertRaises(ScopedHubError):
            verify(lambda *args, **kwargs: self.fail("network"), env={
                **ENV, "HUB_ZEUS_SCOPED_READ_ENABLED": "false"})

    def test_key_invalid_fails_before_network(self):
        for value in ["", "abc", "b" * 63, "B" * 64, "c" * 65]:
            with self.subTest(value=value[:8]), self.assertRaises(ScopedHubError):
                verify(lambda *args, **kwargs: self.fail("network"), env={
                    **ENV, "HUB_ZEUS_SCOPED_READ_TOKEN": value})

    def test_host_pin_fails_before_network(self):
        with self.assertRaises(ScopedHubError):
            verify(lambda *args, **kwargs: self.fail("network"), env={
                **ENV, "HUB_SITE_URL": "https://untrusted.example"})

    def test_wrong_or_missing_fields_block(self):
        for change in [
            {"ok": False}, {"scope": "broad_reader"}, {"source": "snapshot"},
            {"requestId": "OTHER"}, {"pulseDate": "not-a-date"},
            {"checkedAt": None}, {"storageReadCount": 2},
            {"storageReadCount": "1"}, {"writes": 1}, {"writes": False},
        ]:
            data = {
                "ok": True, "source": "existing_hub_r2_pulse",
                "scope": "pulse_metadata_only_v1",
                "pulseDate": "2026-11-22",
                "checkedAt": "2026-11-22T21:00:00Z",
                "requestId": REQUEST_ID,
                "storageReadCount": 1,
                "writes": 0,
            }
            data.update(change)
            with self.subTest(change=change), self.assertRaises(ScopedHubError):
                verify(lambda req, timeout: FakeResponse(data=data))

    def test_non_json_and_oversized_fail(self):
        for response in [
            FakeResponse(raw=b"not json"),
            FakeResponse(raw=b"\xff"),
            FakeResponse(raw=b"x" * (MAX_REPLY_BYTES + 1)),
            FakeResponse(status=204),
        ]:
            with self.subTest(length=len(response.raw)), self.assertRaises(ScopedHubError):
                verify(lambda req, timeout: response)

    def test_http_errors_no_body_or_token_logging(self):
        for code in (401, 404, 503):
            def denied(req, timeout):
                raise HTTPError(req.full_url, code, KEY, {}, None)
            with self.assertRaises(ScopedHubError) as cm:
                verify(denied)
            self.assertNotIn(KEY, str(cm.exception))

    def test_transport_error_no_secret(self):
        def broken(req, timeout):
            raise URLError(KEY)
        with self.assertRaises(ScopedHubError) as cm:
            verify(broken)
        self.assertEqual(str(cm.exception), "Scoped Hub connection is unavailable.")

    def test_optional_siwc_hidden(self):
        seen = []
        def opener(req, timeout):
            seen.append(req)
            return FakeResponse()
        data = verify(opener, env={**ENV, "HUB_SIWC_BYPASS_TOKEN": "S" * 48})
        self.assertEqual(seen[0].get_header("Oai-sites-authorization"), "Bearer " + "S" * 48)
        self.assertNotIn("S" * 48, json.dumps(data))

    def test_no_redirect(self):
        from hub_scoped_pulse import DenyRedirects
        self.assertIsNone(DenyRedirects().redirect_request(None, None, 302, "redirect", {}, "https://evil.example"))

    def test_explicit_owner_only_telegram_command_blocked_without_credentials(self):
        with patch.dict("os.environ", {}, clear=True):
            data = json.loads(telegram_report("verify-scoped"))
        self.assertEqual(data["status"], "BLOCKED")
        self.assertTrue(data["requestId"].startswith("ZEUS-HUB-LINK-"))
        self.assertEqual(data["writes"], 0)
        self.assertFalse(data["responseBodyExposed"])

    def test_request_id_validation(self):
        with self.assertRaises(ScopedHubError):
            verify_scoped_pulse(env=ENV, opener=lambda req, timeout: FakeResponse(),
                                request_id="../bad")
        with self.assertRaises(ScopedHubError):
            verify_scoped_pulse(env=ENV, opener=lambda req, timeout: FakeResponse(),
                                request_id=REQUEST_ID + "?leak=true")

    def test_status_does_not_expose_token(self):
        self.assertNotIn(KEY, json.dumps(readiness(env=ENV)))
        self.assertNotIn(KEY, report(env={"HUB_ZEUS_SCOPED_READ_ENABLED": "false"}))


if __name__ == "__main__":
    unittest.main()
