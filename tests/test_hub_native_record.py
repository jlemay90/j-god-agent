import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import hub_native_record_probe as native
from hub_link_probe import report as telegram_report

ITEM = "11111111-2222-4333-8444-555555555555"
TOKEN = "a" * 64
ENV = {
    "HUB_NATIVE_RECORD_CHECK_ENABLED": "true",
    "HUB_NATIVE_TEST_ITEM_ID": ITEM,
    "HUB_RECORD_READ_TOKEN": TOKEN,
    "HUB_SITE_URL": native.SITE,
}


class FakeResponse:
    status = 200
    def __init__(self, data=None, raw=None):
        self.data = raw if raw is not None else json.dumps(
            data if data is not None else {"ok": True, "record": {
                "type": "item", "id": ITEM,
                "content": {"text": "PRIVATE SAMPLE NOT FOR TELEGRAM", "type": "Note"},
                "revision": 1, "storageVersion": "test-only-etag",
            }}
        ).encode()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, limit):
        return self.data[:limit]


class NativeRecordTests(unittest.TestCase):
    def test_secure_owner_pinned_read_emits_metadata_only(self):
        calls = []
        def opener(req, timeout):
            calls.append((req, timeout))
            return FakeResponse()
        receipt = native.verify_one_item(
            env=ENV, opener=opener,
            clock=lambda: datetime(2026, 11, 22, tzinfo=timezone.utc))
        self.assertEqual(receipt["status"], "PASS_READ_ONLY")
        self.assertEqual(receipt["recordType"], "item")
        self.assertTrue(receipt["identityMatched"])
        self.assertFalse(receipt["responseBodyExposed"])
        self.assertEqual(receipt["writeAccess"], "NOT_AVAILABLE")
        self.assertEqual(receipt["observedAt"], "2026-11-22T00:00:00+00:00")
        req, timeout = calls[0]
        self.assertEqual(req.get_method(), "GET")
        self.assertEqual(req.full_url, native.SITE + "/api/v1/records/item/" + ITEM)
        self.assertEqual(req.get_header("Authorization"), "Bearer " + TOKEN)
        self.assertEqual(timeout, 8)
        visible = json.dumps(receipt)
        self.assertNotIn(TOKEN, visible)
        self.assertNotIn(ITEM, visible)
        self.assertNotIn("PRIVATE SAMPLE", visible)
        self.assertNotIn("test-only-etag", visible)

    def test_disabled_never_contacts_site(self):
        bad = {**ENV, "HUB_NATIVE_RECORD_CHECK_ENABLED": "false"}
        with self.assertRaises(native.NativeHubProbeError):
            native.verify_one_item(env=bad, opener=lambda *a, **k: self.fail("network"))

    def test_missing_or_bad_pinned_id_never_contacts_site(self):
        for item in ["", "some-note", "../mcp", ITEM + "?id=x", "a" * 36]:
            with self.subTest(item=item), self.assertRaises(native.NativeHubProbeError):
                native.verify_one_item(
                    env={**ENV, "HUB_NATIVE_TEST_ITEM_ID": item},
                    opener=lambda *a, **k: self.fail("network"))

    def test_missing_or_bad_token_never_contacts_site(self):
        for token in ["", "test-secret", "a" * 63, "A" * 64, "b" * 65]:
            with self.subTest(length=len(token)), self.assertRaises(native.NativeHubProbeError):
                native.verify_one_item(
                    env={**ENV, "HUB_RECORD_READ_TOKEN": token},
                    opener=lambda *a, **k: self.fail("network"))

    def test_wrong_host_never_contacts_site(self):
        with self.assertRaises(native.NativeHubProbeError):
            native.verify_one_item(
                env={**ENV, "HUB_SITE_URL": "https://example.invalid"},
                opener=lambda *a, **k: self.fail("network"))

    def test_unrecognized_response_fails_closed(self):
        for data in [
            {"ok": False, "record": {"id": ITEM}},
            {"ok": True}, {"ok": True, "record": {}},
            {"ok": True, "record": {"type": "goal", "id": ITEM, "content": {}}},
            {"ok": True, "record": {"type": "item", "id": "other", "content": {}}},
            {"ok": True, "record": {"type": "item", "id": ITEM, "content": "not object"}},
        ]:
            with self.subTest(data=data), self.assertRaises(native.NativeHubProbeError):
                native.verify_one_item(env=ENV, opener=lambda *a, **kw: FakeResponse(data=data))

    def test_denied_http_status_is_blocked_and_redacted(self):
        for code in [401, 404, 503]:
            def denied(req, timeout):
                raise HTTPError(req.full_url, code, "denied", {}, None)
            with self.subTest(code=code), self.assertRaises(native.NativeHubProbeError) as cm:
                native.verify_one_item(env=ENV, opener=denied)
            self.assertNotIn(TOKEN, str(cm.exception))
            self.assertNotIn(ITEM, str(cm.exception))

    def test_transport_error_is_safe(self):
        def unavailable(req, timeout):
            raise URLError("fake secret in a transport exception")
        with self.assertRaises(native.NativeHubProbeError) as cm:
            native.verify_one_item(env=ENV, opener=unavailable)
        self.assertEqual(str(cm.exception), "Hub connection unavailable.")

    def test_oversize_and_non_json_are_blocked(self):
        for bad in [FakeResponse(raw=b"a" * (native.MAX_RESPONSE_BYTES + 1)),
                    FakeResponse(raw=b"<!DOCTYPE html>"), FakeResponse(raw=b"\xff")]:
            with self.subTest(length=len(bad.data)), self.assertRaises(native.NativeHubProbeError):
                native.verify_one_item(env=ENV, opener=lambda *a, **k: bad)

    def test_optional_siwc_header_stays_private(self):
        siwc = "c" * 48
        seen = []
        def opener(req, timeout):
            seen.append(req)
            return FakeResponse()
        receipt = native.verify_one_item(env={**ENV, "HUB_SIWC_BYPASS_TOKEN": siwc}, opener=opener)
        self.assertEqual(seen[0].get_header("Oai-sites-authorization"), "Bearer " + siwc)
        self.assertNotIn(siwc, json.dumps(receipt))

    def test_no_redirects(self):
        handler = native.NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, "redirect", {}, "https://elsewhere.example"))

    def test_telegram_route_defaults_to_blocked(self):
        with patch.dict("os.environ", {"HUB_NATIVE_RECORD_CHECK_ENABLED": "false"}, clear=True):
            result = json.loads(telegram_report("verify-native"))
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["responseBodyExposed"])
        self.assertEqual(result["writeAccess"], "NOT_AVAILABLE")

    def test_status_metadata_never_exposes_credential_or_id(self):
        result = native.status(env=ENV)
        self.assertEqual(result["status"], "DRAFT_OR_DISABLED")
        self.assertTrue(result["test_record_configured"])
        self.assertTrue(result["credential_configured"])
        self.assertNotIn(TOKEN, json.dumps(result))
        self.assertNotIn(ITEM, json.dumps(result))


if __name__ == "__main__":
    unittest.main()
