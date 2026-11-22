import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pattern_investigator.eyes import fetch_hub_evidence, EyesBlocked, SITE_URL
from pattern_investigator.brain import assess
from pattern_investigator.engine import investigate
from pattern_investigator.ledger import Ledger,LedgerError
from pattern_investigator.service import run_once,watchdog_check,dispatch_alerts
from pattern_investigator.voice import send_owner_alert,health_message

NOW = datetime(2026, 11, 22, 22, 0, tzinfo=timezone.utc)
TOKEN = "x" * 48
BOT = "123456:" + ("A"*32)

def observed(i,**overrides):
    v={"id":f"obs-{i}","event_id":f"event-{i}","source_ref":f"hub:item:{i}",
       "source_kind":"owner_reported","occurred_at":(NOW-timedelta(days=i)).isoformat(),
       "theme":"test_recurrence","basis":"observed_event","polarity":"supports",
       "summary":"Neutral synthetic evidence","goal":"growth","authorized":True,"sensitive":False}
    v.update(overrides)
    return v

def source(rows=None):
    rows=[observed(1),observed(2)] if rows is None else rows
    return {"observations":rows,"transport_receipt":{
        "source":"owner_authenticated_curated_hub_pattern_evidence",
        "method":"owner_scoped_live_hub_read_only","checked_at_utc":NOW.isoformat(),
        "source_revision":"fixture-rev-1","external_truth_verified":False,
        "count":len(rows)}}

class EyesTests(unittest.TestCase):
    def test_default_denies_missing_credentials(self):
        with self.assertRaises(EyesBlocked):
            fetch_hub_evidence(siwc_token="",route_secret="",now=NOW)
    def test_curated_scoped_success_and_auth_headers(self):
        body={"ok":True,"source":"owner_authenticated_curated_hub_pattern_evidence",
              "scope":"pattern_read_only_v1","checkedAt":NOW.isoformat(),
              "sourceRevision":"rev12","observations":[observed(1)]}
        def fake(req,timeout,cap):
            self.assertEqual(req.full_url,SITE_URL)
            self.assertEqual(req.get_method(),"GET")
            self.assertEqual(req.headers["Authorization"],"Bearer "+TOKEN)
            self.assertEqual(req.headers["Oai-sites-authorization"],"Bearer "+TOKEN)
            self.assertEqual(timeout,8)
            return (200,json.dumps(body).encode(),SITE_URL)
        result=fetch_hub_evidence(siwc_token=TOKEN,route_secret=TOKEN,opener=fake,now=NOW)
        self.assertEqual(result["transport_receipt"]["count"],1)
        self.assertFalse(result["transport_receipt"]["external_truth_verified"])
    def test_redirect_rejected(self):
        with self.assertRaises(EyesBlocked):
            fetch_hub_evidence(siwc_token=TOKEN,route_secret=TOKEN,
                 opener=lambda *a:(200,b"{}",SITE_URL+"/else"),now=NOW)
    def test_forged_or_stale_source_rejected(self):
        body={"ok":True,"source":"wrong","scope":"pattern_read_only_v1","checkedAt":NOW.isoformat(),"observations":[]}
        with self.assertRaises(EyesBlocked):
            fetch_hub_evidence(siwc_token=TOKEN,route_secret=TOKEN,
               opener=lambda *a:(200,json.dumps(body).encode(),SITE_URL),now=NOW)
        body["source"]="owner_authenticated_curated_hub_pattern_evidence"
        body["checkedAt"]=(NOW-timedelta(hours=3)).isoformat()
        with self.assertRaises(EyesBlocked):
            fetch_hub_evidence(siwc_token=TOKEN,route_secret=TOKEN,
               opener=lambda *a:(200,json.dumps(body).encode(),SITE_URL),now=NOW)
    def test_oversized_rejected(self):
        with self.assertRaises(EyesBlocked):
            fetch_hub_evidence(siwc_token=TOKEN,route_secret=TOKEN,
               opener=lambda *a:(200,b"0"*64001,SITE_URL),now=NOW)

class BrainTests(unittest.TestCase):
    def test_hypothesis_is_not_outcome_or_conclusion(self):
        checked=investigate({"request_id":"test-1","observations":[observed(1),observed(2)]},now=NOW)
        report=assess(checked)
        f=report["findings"][0]
        self.assertEqual(f["assessment"],"POSSIBLE_RECURRENCE")
        self.assertEqual(f["proposed_experiment"]["status"],"PROPOSED_NOT_AUTHORIZED_NOT_RUN")
        self.assertEqual(report["experiments_executed"],0)
        self.assertEqual(report["analysis_mode"],"RULE_BASED_NO_EXTERNAL_AI")
    def test_untrusted_brain_receipt_rejected(self):
        with self.assertRaises(ValueError):
            assess({"run_status":"EVIDENCE_REVIEW_COMPLETED","findings":[{"assessment":"FULL_CONFIDENCE"}]})
    def test_contradiction_blocks_experiment(self):
        rows=[observed(1),observed(2,polarity="contradicts")]
        r=assess(investigate({"request_id":"test-2","observations":rows},now=NOW))
        self.assertIsNone(r["findings"][0]["proposed_experiment"])

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=str(Path(self.tmp.name)/"pilot.sqlite")
        self.ledger=Ledger(self.db)
    def tearDown(self):
        self.tmp.cleanup()
    def test_permissions_and_exactly_one_daily_claim(self):
        self.assertEqual(os.stat(self.db).st_mode & 0o077,0)
        a=self.ledger.claim(NOW); b=self.ledger.claim(NOW)
        self.assertTrue(a["claimed"]);self.assertFalse(b["claimed"])
        self.assertEqual(a["run_id"],b["run_id"])
    def test_run_receipt_persisted_without_raw_source(self):
        result=run_once(self.ledger,fetcher=source,now=NOW)
        self.assertEqual(result["status"],"COMPLETED")
        row=self.ledger.latest()
        self.assertEqual(row["status"],"COMPLETED")
        self.assertEqual(json.loads(row["summary"])["candidate_count"],1)
        self.assertNotIn("Neutral synthetic evidence",row["summary"])
        self.assertEqual(len(self.ledger.pending_alerts()),1)
        self.assertEqual(run_once(self.ledger,fetcher=source,now=NOW)["status"],"ALREADY_RECORDED")
    def test_failure_keeps_receipt_and_does_not_echo_secret(self):
        result=run_once(self.ledger,fetcher=lambda: (_ for _ in ()).throw(RuntimeError("private secret")),now=NOW)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertNotIn("private secret",json.dumps(result))
        self.assertEqual(self.ledger.latest()["status"],"BLOCKED")
        self.assertEqual(watchdog_check(self.ledger,now=NOW)["check_status"],"FAILED_RUN")
    def test_watchdog_detects_missing_stale_and_deduplicates(self):
        self.assertEqual(watchdog_check(self.ledger,now=NOW)["check_status"],"MISSING_RUN")
        self.assertEqual(watchdog_check(self.ledger,now=NOW)["check_status"],"MISSING_RUN")
        self.assertEqual(len(self.ledger.pending_alerts()),1)
        run_once(self.ledger,fetcher=source,now=NOW)
        self.assertEqual(watchdog_check(self.ledger,now=NOW)["check_status"],"ON_TIME")
        self.assertEqual(watchdog_check(self.ledger,now=NOW+timedelta(hours=40))["check_status"],"OVERDUE")
    def test_stale_run_revision_cannot_finish(self):
        a=self.ledger.claim(NOW)
        with self.assertRaises(LedgerError):
            self.ledger.finish(a["slot"],"other","COMPLETED",NOW,{"x":1})
        self.assertEqual(self.ledger.latest()["status"],"RUNNING")
    def test_private_path_required(self):
        with self.assertRaises(LedgerError):
            Ledger("local.sqlite")
    def test_voice_disabled_by_default(self):
        r=send_owner_alert(bot_token=BOT,chat_id="12345678",message="safe",explicitly_enabled=False)
        self.assertEqual(r["status"],"BLOCKED_NOT_ENABLED")
    def test_provider_ack_not_delivery(self):
        self.ledger.alert_once("watch:2026-11-22:FAILED_RUN","FAILED_RUN",NOW)
        count=[0]
        def fake(req,seconds,limit):
            count[0]+=1
            return (200,json.dumps({"ok":True,"result":{"message_id":123}}).encode())
        r=dispatch_alerts(self.ledger,now=NOW,sender=fake,bot_token=BOT,
                          chat_id="12345678",explicitly_enabled=True)
        self.assertEqual(r["provider_accepted"],1)
        self.assertFalse(r["handset_delivery_verified"])
        self.assertEqual(dispatch_alerts(self.ledger,now=NOW,sender=fake,bot_token=BOT,
                          chat_id="12345678",explicitly_enabled=True)["provider_accepted"],0)
        self.assertEqual(count[0],1)
    def test_alert_refuses_urls(self):
        self.assertEqual(send_owner_alert(bot_token=BOT,chat_id="12345678",
            message="https://example.com",explicitly_enabled=True)["status"],"BLOCKED_UNSAFE_MESSAGE")

if __name__=="__main__":
    unittest.main()
