import json
import os
import subprocess
import sys
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pattern_investigator import InvalidInput, investigate, watchdog

NOW = datetime(2026, 11, 22, 20, 20, tzinfo=timezone.utc)


def record(i=1, **kwargs):
    day = NOW - timedelta(days=5-i)
    row = {"id": f"obs{i}", "event_id": f"event{i}", "source_ref": f"source{i}",
           "source_kind": "original_verified", "occurred_at": day.isoformat(),
           "theme": "follow_through", "basis": "observed_event", "polarity": "supports",
           "summary": "A neutral fictional example", "goal": "growth",
           "authorized": True, "sensitive": False}
    row.update(kwargs)
    return row


def check(rows):
    return investigate({"request_id": "case-001", "observations": rows}, now=NOW)


class PatternInvestigatorTest(unittest.TestCase):
    def test_three_independent_originals_supported(self):
        result = check([record(1), record(2), record(3)])
        f = result["findings"][0]
        self.assertEqual(f["assessment"], "SUPPORTED_RECURRENCE")
        self.assertEqual(f["original_verified_count"], 3)
        self.assertEqual(result["run_status"], "EVIDENCE_REVIEW_COMPLETED")
        self.assertEqual(f["experiment_status"], "NOT_AUTHORIZED_NOT_RUN")
        self.assertEqual(result["delivery_status"], "NOT_DELIVERED_BY_ENGINE")

    def test_two_events_possible_not_confident(self):
        self.assertEqual(check([record(1), record(2)])["findings"][0]["assessment"], "POSSIBLE_RECURRENCE")

    def test_single_event_insufficient(self):
        self.assertEqual(check([record(1)])["findings"][0]["assessment"], "INSUFFICIENT_EVIDENCE")

    def test_intention_not_observed(self):
        self.assertEqual(check([record(1, basis="intention"), record(2)])["findings"][0]["assessment"], "INSUFFICIENT_EVIDENCE")

    def test_two_same_event_not_independent(self):
        f = check([record(1), record(2, event_id="event1")])["findings"][0]
        self.assertEqual(f["assessment"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(f["duplicate_event_records"], 1)

    def test_same_day_not_independent(self):
        f = check([record(1), record(2, occurred_at=record(1)["occurred_at"])])["findings"][0]
        self.assertEqual(f["assessment"], "INSUFFICIENT_EVIDENCE")

    def test_third_party_repetition_does_not_count_original(self):
        f = check([record(1, source_kind="secondary"), record(2, source_kind="secondary"), record(3, source_kind="owner_reported")])["findings"][0]
        self.assertEqual(f["assessment"], "POSSIBLE_RECURRENCE")

    def test_single_source_not_supported(self):
        f = check([record(1, source_ref="same"), record(2, source_ref="same"), record(3, source_ref="same")])["findings"][0]
        self.assertEqual(f["assessment"], "POSSIBLE_RECURRENCE")

    def test_contradiction_is_not_hidden(self):
        f = check([record(1), record(2), record(3, polarity="contradicts")])["findings"][0]
        self.assertEqual(f["assessment"], "CONTESTED")
        self.assertEqual(f["disconfirming_evidence"], ["obs3"])

    def test_conflict_within_same_event_is_flagged(self):
        f = check([record(1), record(2, event_id="event1", polarity="contradicts")])["findings"][0]
        self.assertEqual(f["assessment"], "CONTESTED")

    def test_stale_requires_reverification(self):
        old = (NOW - timedelta(days=110)).isoformat()
        f = check([record(1, occurred_at=old), record(2, occurred_at=(NOW-timedelta(days=109)).isoformat())])["findings"][0]
        self.assertEqual(f["assessment"], "STALE_REVERIFY")

    def test_sensitive_data_not_auto_inferred(self):
        f = check([record(1, sensitive=True), record(2), record(3)])["findings"][0]
        self.assertEqual(f["assessment"], "REQUIRES_SEPARATE_CONSENT")

    def test_wrong_type_enumeration_is_blocked_not_crashed(self):
        with self.assertRaises(InvalidInput): check([record(1, source_kind=["original_verified"])])

    def test_missing_authorization_fails_closed(self):
        with self.assertRaises(InvalidInput): check([record(1, authorized=False)])

    def test_missing_source_fails_closed(self):
        with self.assertRaises(InvalidInput): check([record(1, source_ref="")])

    def test_future_event_rejected(self):
        with self.assertRaises(InvalidInput): check([record(1, occurred_at=(NOW+timedelta(days=3)).isoformat())])

    def test_timezone_required(self):
        with self.assertRaises(InvalidInput): check([record(1, occurred_at="2026-11-20T12:00:00")])

    def test_duplicate_id_rejected(self):
        with self.assertRaises(InvalidInput): check([record(1), record(1)])

    def test_excessive_records_rejected(self):
        with self.assertRaises(InvalidInput): check([record(1)]*301)

    def test_unknown_fields_rejected(self):
        with self.assertRaises(InvalidInput): investigate({"request_id":"A", "observations":[], "commands":"delete"}, now=NOW)

    def test_empty_input_explicit_no_findings(self):
        r = check([])
        self.assertEqual(r["findings"], [])
        self.assertEqual(r["observations_checked"], 0)

    def test_watchdog_on_time(self):
        receipt = check([record(1)])
        self.assertEqual(watchdog(receipt, now=NOW+timedelta(hours=2))["check_status"], "ON_TIME")

    def test_watchdog_missing_and_overdue(self):
        receipt = check([])
        self.assertEqual(watchdog(None, now=NOW)["check_status"], "MISSING_OR_FAILED")
        self.assertEqual(watchdog(receipt, now=NOW+timedelta(hours=37))["check_status"], "OVERDUE")

    def test_watchdog_clock_conflict(self):
        receipt = check([])
        self.assertEqual(watchdog(receipt, now=NOW-timedelta(days=2))["check_status"], "CLOCK_CONFLICT")

    def test_bad_bounds(self):
        with self.assertRaises(InvalidInput): watchdog(None, now=NOW, max_age_hours=0)

    def test_cli_block_receipt_no_raw_input_echo(self):
        p = subprocess.run([sys.executable, "-m", "pattern_investigator", "investigate"],
                           input=json.dumps({"request_id":"123", "observations":[record(1, authorized=False, summary="private sentinel")]}),
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertEqual(json.loads(p.stdout)["run_status"], "BLOCKED")
        self.assertNotIn("private sentinel", p.stdout)

    def test_no_network_or_filesystem_writes_in_engine(self):
        # Core should remain pure by design; excludes dependency imports.
        import inspect
        from pattern_investigator import engine
        src = inspect.getsource(engine)
        self.assertNotIn("requests.", src)
        self.assertNotIn("urllib.request", src)
        self.assertNotIn("open(", src)

if __name__ == "__main__":
    unittest.main()