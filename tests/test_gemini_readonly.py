import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from run_controller.controller import CycleRequest
from run_controller.gemini_readonly import (GeminiReadOnlyWorker, RateCard,
                                            WorkerError, validate_manifest)
from run_controller.gemini_pilot import main


def manifest(n=5):
    return {"tasks": [dict(id=f"public_{i}", question=f"What does claim {i} prove?",
                           source_url="https://github.com/jlemay90/j-god-agent/pull/9",
                           source_checked_at="2026-11-22T17:00:00Z",
                           source_text=f"Synthetic PUBLIC excerpt {i}: locally tested, not live.",
                           public=True) for i in range(1, n+1)]}


def response(source_id="public_1", *, usage=True, body=True):
    result = {"modelVersion": "test-model", "responseId": "test-response-id",
              "candidates": [{"content": {"parts": [{"text": json.dumps({
                  "source_id": source_id, "finding": "Local test is not deployment proof.",
                  "limitation": "Live integration not verified."}) if body else ""}]}}]}
    if usage:
        result["usageMetadata"] = {"promptTokenCount": 100, "totalTokenCount": 128,
                                   "candidatesTokenCount": 28}
    return result


class GeminiReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.source = manifest()
        self.calls = []

    def fake_post(self, url, body, api_key, timeout):
        self.calls.append((url, body, api_key, timeout))
        if url.endswith("countTokens"):
            return {"totalTokens": 100}
        return response()

    def worker(self, **overrides):
        config = dict(model="gemini-test", rate_card=RateCard(1.0, 2.0),
                      remaining_usd=lambda mission_id: 0.01,
                      authorized=True, api_key="test-key-not-secret", post=self.fake_post)
        config.update(overrides)
        return GeminiReadOnlyWorker(self.source, **config)

    @staticmethod
    def req(cycle=1, state=None):
        return CycleRequest("mission-test", cycle, "nonce", state if state is not None else {"findings": []})

    def test_good_cycle_receipt_and_human_review(self):
        result = self.worker()(self.req())
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(result.state["findings"]), 1)
        self.assertTrue(result.state["findings"][0]["human_review_required"])
        self.assertEqual(result.state["findings"][0]["source_url"], self.source["tasks"][0]["source_url"])
        self.assertIn("USD_ESTIMATE", result.receipt)
        self.assertAlmostEqual(result.cost_usd, .000156)
        self.assertNotIn("test-key-not-secret", result.receipt)
        self.assertEqual(self.calls[0][2], "test-key-not-secret")
        self.assertNotIn("tools", self.calls[1][1])

    def test_second_cycle_uses_saved_checkpoint(self):
        first = self.worker()(self.req())
        def source2(url, body, key, timeout):
            return {"totalTokens": 90} if url.endswith("countTokens") else response("public_2")
        result = self.worker(post=source2)(self.req(2, first.state))
        self.assertEqual(len(result.state["findings"]), 2)
        self.assertEqual(result.state["findings"][1]["id"], "public_2")

    def test_requires_explicit_authorization(self):
        with self.assertRaisesRegex(WorkerError, "explicit"):
            self.worker(authorized=False)(self.req())
        self.assertFalse(self.calls)

    def test_requires_key(self):
        with self.assertRaisesRegex(WorkerError, "GEMINI_API_KEY"):
            self.worker(api_key="")(self.req())
        self.assertFalse(self.calls)

    def test_budget_guard_prevents_generation(self):
        with self.assertRaisesRegex(WorkerError, "budget"):
            self.worker(remaining_usd=lambda _mid: 0.000001)(self.req())
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(self.calls[0][0].endswith("countTokens"))

    def test_missing_usage_fails_closed(self):
        def bad(url, body, key, timeout):
            return {"totalTokens": 100} if url.endswith("countTokens") else response(usage=False)
        with self.assertRaisesRegex(WorkerError, "unverified"):
            self.worker(post=bad)(self.req())

    def test_source_id_mismatch_blocks_checkpoint(self):
        def bad(url, body, key, timeout):
            return {"totalTokens": 100} if url.endswith("countTokens") else response("wrong")
        with self.assertRaises(WorkerError):
            self.worker(post=bad)(self.req())

    def test_empty_output_fails_closed(self):
        def bad(url, body, key, timeout):
            return {"totalTokens": 100} if url.endswith("countTokens") else response(body=False)
        with self.assertRaises(WorkerError):
            self.worker(post=bad)(self.req())

    def test_socket_timeout_fails_closed(self):
        def bad(url, body, key, timeout):
            raise WorkerError("timeout")
        with self.assertRaisesRegex(WorkerError, "timeout"):
            self.worker(post=bad)(self.req())

    def test_stale_count_blocks_call(self):
        with self.assertRaisesRegex(WorkerError, "checkpoint"):
            self.worker()(self.req(2, {"findings": []}))
        self.assertFalse(self.calls)

    def test_only_preapproved_public_sources(self):
        for field, value in [("public", False), ("source_url", "https://docs.google.com/document/d/secret"),
                             ("source_url", "https://github.com@evil.example/x")]:
            with self.subTest(field=field, value=value):
                data = copy.deepcopy(self.source)
                data["tasks"][0][field] = value
                with self.assertRaises(ValueError): validate_manifest(data)

    def test_duplicate_and_oversized_snippets(self):
        d = copy.deepcopy(self.source)
        d["tasks"][1]["id"] = d["tasks"][0]["id"]
        with self.assertRaises(ValueError): validate_manifest(d)
        d = manifest()
        d["tasks"][0]["source_text"] = "X" * 3501
        with self.assertRaises(ValueError): validate_manifest(d)

    def test_model_and_ratecard_require_explicit_safe_values(self):
        with self.assertRaises(ValueError): RateCard(0.0, 1.0)
        with self.assertRaises(ValueError): self.worker(model="bad/model")

    def test_preview_is_offline_and_creates_no_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "evidence.json"
            db = Path(tmp) / "never_created.sqlite"
            src.write_text(json.dumps(manifest()))
            argv = ["--manifest", str(src), "--db", str(db), "--model", "gemini-test",
                    "--input-price-per-million", "1", "--output-price-per-million", "2",
                    "--max-usd", "0.02", "--preview"]
            self.assertEqual(main(argv), 0)
            self.assertFalse(db.exists())

    def test_no_key_rejected_before_db_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "evidence.json"
            db = Path(tmp) / "blocked.sqlite"
            src.write_text(json.dumps(manifest()))
            argv = ["--manifest", str(src), "--db", str(db), "--model", "gemini-test",
                    "--input-price-per-million", "1", "--output-price-per-million", "2",
                    "--max-usd", "0.02", "--authorize-model-calls"]
            with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
                with self.assertRaises(SystemExit) as cm:
                    main(argv)
            self.assertEqual(cm.exception.code, 2)
            self.assertFalse(db.exists())


    def test_rejects_world_readable_checkpoint_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "evidence.json"
            src.write_text(json.dumps(manifest()))
            private = Path(tmp) / "insecure"
            private.mkdir()
            private.chmod(0o755)
            db = private / "checkpoint.sqlite"
            argv = ["--manifest", str(src), "--db", str(db), "--model", "gemini-test",
                    "--input-price-per-million", "1", "--output-price-per-million", "2",
                    "--max-usd", "0.02", "--authorize-model-calls"]
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-not-secret"}):
                with self.assertRaises(SystemExit) as cm:
                    main(argv)
            self.assertEqual(cm.exception.code, 2)
            self.assertFalse(db.exists())

    def test_rejects_world_readable_existing_checkpoint_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "evidence.json"
            src.write_text(json.dumps(manifest()))
            private = Path(tmp) / "secure"
            private.mkdir(mode=0o700)
            db = private / "checkpoint.sqlite"
            db.write_bytes(b"not a real sqlite file")
            db.chmod(0o644)
            argv = ["--manifest", str(src), "--db", str(db), "--model", "gemini-test",
                    "--input-price-per-million", "1", "--output-price-per-million", "2",
                    "--max-usd", "0.02", "--authorize-model-calls"]
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-not-secret"}):
                with self.assertRaises(SystemExit) as cm:
                    main(argv)
            self.assertEqual(cm.exception.code, 2)
            self.assertEqual(db.read_bytes(), b"not a real sqlite file")



if __name__ == "__main__":
    unittest.main()
