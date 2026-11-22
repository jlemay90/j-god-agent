"""Private host operator CLI for the five Pattern Investigator components.

Never install in GitHub Actions with owner tokens; public CI is synthetic only.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from .ledger import Ledger
from .service import run_once,watchdog_check,dispatch_alerts

def main(argv=None):
    p=argparse.ArgumentParser(prog="j-pattern-investigator")
    p.add_argument("action",choices=["run-once","watch","dispatch","status"])
    p.add_argument("--db",default=os.getenv("PATTERN_LEDGER_PATH",""))
    a=p.parse_args(argv)
    if not a.db:
        print(json.dumps({"status":"BLOCKED","reason":"PRIVATE_LEDGER_PATH_MISSING"}))
        return 2
    try:
        ledger=Ledger(a.db)
        if a.action=="run-once":
            if os.getenv("PATTERN_RUN_ENABLED")!="true":
                print(json.dumps({"status":"BLOCKED","reason":"RUN_NOT_ENABLED"}))
                return 2
            result=run_once(ledger)
            print(json.dumps(result,sort_keys=True))
            return 0 if result["status"]=="COMPLETED" else 2
        if a.action=="watch":
            result=watchdog_check(ledger)
            print(json.dumps(result,sort_keys=True))
            return 0 if result["check_status"]=="ON_TIME" else 3
        if a.action=="dispatch":
            result=dispatch_alerts(ledger)
            print(json.dumps(result,sort_keys=True))
            return 0 if result["unverified_or_blocked"]==0 else 4
        latest=ledger.latest()
        result={"status":"READ_ONLY_LOCAL_STATUS","latest_run":{k:latest.get(k) for k in
            ("slot","run_id","status","started_at_utc","finished_at_utc")} if latest else None,
            "pending_alert_count":len(ledger.pending_alerts()),
            "live_site_connector_verified":False}
        print(json.dumps(result,sort_keys=True))
        return 0
    except Exception:
        print(json.dumps({"status":"BLOCKED","reason":"PRIVATE_LEDGER_UNAVAILABLE"}))
        return 5

if __name__=="__main__":
    sys.exit(main())
