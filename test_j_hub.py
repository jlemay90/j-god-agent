import datetime as dt
import json
import unittest
from unittest.mock import patch
import j_hub

class HubHandoffTests(unittest.TestCase):
    def valid(self):
        return {"schema_version":1,"source":j_hub.SOURCE,"captured_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"hub_revision":7,"live_sync":False,"decisions":["Keep sources"],"next_steps":["Verify"],"limits":["No live access"],"private_tasks":["excluded"]}
    def test_drops_unapproved_fields(self):
        v=j_hub.validate(json.dumps(self.valid()))
        self.assertNotIn("private_tasks",v)
        self.assertTrue(v["reference_only"])
        self.assertFalse(v["live_sync"])
    def test_rejects_bad_source_and_live_claim(self):
        for field,value in [("source","https://attacker.example"),("live_sync",True),("hub_revision","7"),("decisions","unexpected")]:
            v=self.valid(); v[field]=value
            with self.assertRaises((ValueError,TypeError)): j_hub.validate(json.dumps(v))
    def test_stale_is_explicit(self):
        v=self.valid();v["captured_at_utc"]=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=2)).isoformat()
        self.assertTrue(j_hub.validate(json.dumps(v))["stale"])
    def test_failure_does_not_claim_connection(self):
        with patch("j_hub.verified_origin",side_effect=j_hub.RepoError("offline")):
            self.assertEqual(j_hub.cached()["status"],"unavailable")
            self.assertIn("failed",j_hub.report())
    def test_frozen_file_path_and_provenance(self):
        calls=[]
        def fake(*args):
            calls.append(args)
            return json.dumps(self.valid()) if args[0]=="show" else "a"*40
        with patch("j_hub.verified_origin"),patch("j_hub.git",side_effect=fake):
            v=j_hub.cached()
            self.assertEqual(v["source_commit"],"a"*40)
            self.assertIn(("show","refs/remotes/origin/main:hub_project_context.json"),calls)

if __name__=="__main__":unittest.main()
