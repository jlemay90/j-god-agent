"""Full original-controller + mocked Gemini five-cycle checkpoint integration."""
import re
import tempfile
import unittest
from pathlib import Path

from run_controller.controller import Controller
from run_controller.gemini_readonly import GeminiReadOnlyWorker, RateCard, WorkerError
from test_gemini_readonly import manifest, response


class GeminiSQLiteIntegrationTests(unittest.TestCase):
    def test_five_mock_cycles_with_sqlite_restart_and_manual_reconciliation(self):
        """Integration with the parent Controller; synthetic inference, NOT a live Gemini test."""
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "private.sqlite"
            client = Controller(db)
            mid = client.create("public pilot mock", max_cycles=5, max_seconds=300,
                                max_cost_usd=0.05, initial_state={"findings": []})
            fail_once = {"enabled": True}
            calls = []

            def mock_provider(url, body, key, timeout):
                task_id = re.search(r"Source ID: ([a-z0-9_]+)",
                                    body["contents"][0]["parts"][0]["text"]).group(1)
                if url.endswith("countTokens"):
                    if task_id == "public_3" and fail_once["enabled"]:
                        fail_once["enabled"] = False
                        raise WorkerError("simulated outage before inference")
                    return {"totalTokens": 100}
                calls.append(task_id)
                return response(task_id)

            worker = GeminiReadOnlyWorker(manifest(), model="gemini-test",
                                          rate_card=RateCard(1.0, 2.0),
                                          remaining_usd=lambda _mid: 0.05 - client.status(mid)["spent_usd"],
                                          authorized=True, api_key="test-key-not-secret", post=mock_provider)
            with self.assertRaisesRegex(WorkerError, "simulated outage"):
                client.run(mid, worker)
            self.assertEqual(client.status(mid)["completed"], 2)
            self.assertEqual(client.status(mid)["status"], "needs_review")
            self.assertEqual(calls, ["public_1", "public_2"])
            client.close()
            client = Controller(db)
            # Outage occurred before simulated generateContent; external no-effect verified in test.
            client.resolve_interrupted(mid, outcome="no_effect", receipt="mock provider had no generateContent call")
            worker = GeminiReadOnlyWorker(manifest(), model="gemini-test",
                                          rate_card=RateCard(1.0, 2.0),
                                          remaining_usd=lambda _mid: 0.05 - client.status(mid)["spent_usd"],
                                          authorized=True, api_key="test-key-not-secret", post=mock_provider)
            result = client.run(mid, worker)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["completed"], 5)
            self.assertEqual(len(result["state"]["findings"]), 5)
            self.assertEqual(calls, [f"public_{n}" for n in range(1, 6)])
            self.assertEqual(sum(e["event"] == "cycle_completed" for e in client.events(mid)), 5)
            client.close()

