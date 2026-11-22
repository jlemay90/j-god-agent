"""Orchestration of Eyes -> evidence gate -> Brain -> durable receipt.

The worker is intentionally read-only with respect to Hub records. It writes
only its own PRIVATE ledger. No third-party experiments or automatic spending.
"""
from __future__ import annotations
import os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from .engine import investigate
from .brain import assess
from .eyes import fetch_hub_evidence
from .ledger import Ledger
from .voice import send_owner_alert, health_message

TZ=ZoneInfo("America/Chicago")
def _now():
    return datetime.now(timezone.utc)

def run_once(ledger:Ledger, *, fetcher=None, now:datetime|None=None)->dict:
    now=(now or _now()).astimezone(timezone.utc)
    claim=ledger.claim(now)
    if not claim["claimed"]:
        return {"run_id":claim["run_id"],"slot":claim["slot"],"status":"ALREADY_RECORDED",
                "existing_status":claim["status"],"did_not_rerun":True}
    try:
        fetcher=fetcher or (lambda:fetch_hub_evidence(
            siwc_token=os.getenv("HUB_SIWC_BYPASS_TOKEN",""),
            route_secret=os.getenv("HUB_PATTERN_LINK_SECRET",""),now=now))
        source=fetcher()
        if not isinstance(source,dict):
            raise ValueError("source unavailable")
        receipt=source.get("transport_receipt")
        if (not isinstance(receipt,dict) or
            receipt.get("method")!="owner_scoped_live_hub_read_only" or
            receipt.get("source")!="owner_authenticated_curated_hub_pattern_evidence" or
            not isinstance(source.get("observations"),list)):
            raise ValueError("untrusted transport receipt")
        data=investigate({"request_id":claim["run_id"],
                          "observations":source["observations"]},now=now)
        report=assess(data)
        candidates=[f for f in report["findings"] if f["assessment"] in
                    {"SUPPORTED_RECURRENCE","POSSIBLE_RECURRENCE"}]
        summary={
            "evidence_review_status":data["run_status"],
            "source_checked_at":receipt.get("checked_at_utc"),
            "source_revision":receipt.get("source_revision"),
            "observation_count":data["observations_checked"],
            "finding_count":report["findings_total"],
            "candidate_count":len(candidates),
            "analysis_mode":report["analysis_mode"],
            "hypotheses":[{"theme":f["theme"],"assessment":f["assessment"],
                           "evidence":f["supporting_record_ids"],
                           "contradictions":f["contradicting_record_ids"]}
                          for f in report["findings"]],
            "experiments_executed":0,
            "notification_sent":False,
            "handset_delivery_verified":False,
        }
        ledger.finish(claim["slot"],claim["run_id"],"COMPLETED",now,summary)
        if candidates:
            ledger.alert_once("finding:"+claim["slot"],"IMPORTANT_FINDING",now)
        return {"slot":claim["slot"],"run_id":claim["run_id"],"status":"COMPLETED",
                "source":"owner_scoped_live_hub_read_only","candidate_count":len(candidates),
                "notification_status":"QUEUED_NOT_SENT" if candidates else "NO_ALERT_NEEDED"}
    except Exception:
        # No sensitive source content / credentials are included in run receipts.
        ledger.finish(claim["slot"],claim["run_id"],"BLOCKED",now,
                      {"reason":"SOURCE_OR_ANALYSIS_NOT_VERIFIED","notification_sent":False})
        ledger.alert_once("failed:"+claim["slot"],"FAILED_RUN",now)
        return {"slot":claim["slot"],"run_id":claim["run_id"],"status":"BLOCKED",
                "reason":"SOURCE_OR_ANALYSIS_NOT_VERIFIED",
                "notification_status":"QUEUED_NOT_SENT"}

def watchdog_check(ledger:Ledger,*,now:datetime|None=None,
                   max_age_hours:float=28)->dict:
    """Separate process. Daily expected run must exist by 08:35 Central.

    This does not verify the watchdog itself is externally monitored.
    """
    now=(now or _now()).astimezone(timezone.utc)
    if not isinstance(max_age_hours,(int,float)) or isinstance(max_age_hours,bool) or not 1<=max_age_hours<=72:
        raise ValueError("invalid max age")
    local=now.astimezone(TZ)
    expected_slot=local.strftime("%Y-%m-%d")
    past_grace=(local.hour>8 or (local.hour==8 and local.minute>=35))
    latest=ledger.latest()
    status="MISSING_RUN" if past_grace else "AWAITING_SCHEDULED_RUN"
    if latest is not None:
        try:
            stamp=latest["finished_at_utc"] or latest["started_at_utc"]
            ts=datetime.fromisoformat(stamp)
            if ts.tzinfo is None or ts>now+timedelta(minutes=5):
                status="CLOCK_CONFLICT"
            else:
                age=(now-ts).total_seconds()/3600
                if latest["status"]=="RUNNING":
                    status="RUN_IN_PROGRESS" if age<=1 else "STALLED_RUN"
                elif latest["status"]!="COMPLETED":
                    status="FAILED_RUN"
                elif age>max_age_hours:
                    status="OVERDUE"
                elif past_grace and latest["slot"]!=expected_slot:
                    status="MISSING_RUN"
                else:
                    status="ON_TIME"
        except (TypeError,ValueError,OverflowError):
            status="INVALID_RECEIPT"
    if status not in {"ON_TIME","RUN_IN_PROGRESS","AWAITING_SCHEDULED_RUN"}:
        key="watch:"+expected_slot+":"+status
        ledger.alert_once(key,"MISSED_RUN",now)
    return {"check_status":status,"expected_slot":expected_slot,
            "last_run_status":latest["status"] if latest else "MISSING",
            "last_run_id":latest["run_id"] if latest else None,
            "alert_status":"QUEUED_NOT_DELIVERED" if status not in {"ON_TIME","RUN_IN_PROGRESS","AWAITING_SCHEDULED_RUN"} else "NO_ALERT",
            "independently_scheduled":False,
            "external_monitor_verified":False}

def dispatch_alerts(ledger:Ledger,*,now:datetime|None=None,
                    sender=None,bot_token:str|None=None,chat_id:str|None=None,
                    explicitly_enabled:bool|None=None)->dict:
    now=(now or _now()).astimezone(timezone.utc)
    enabled=(os.getenv("PATTERN_ALERT_SEND_ENABLED")=="true") if explicitly_enabled is None else explicitly_enabled
    token=bot_token if bot_token is not None else os.getenv("TELEGRAM_BOT_TOKEN","")
    recipient=chat_id if chat_id is not None else os.getenv("TELEGRAM_OWNER_CHAT_ID","")
    accepted=blocked=0
    for row in ledger.pending_alerts():
        # At most one provider call per pending alert every 30 minutes.
        try:
            last=datetime.fromisoformat(row["last_attempt_utc"]) if row["last_attempt_utc"] else None
        except ValueError:
            last=None
        if last and now-last<timedelta(minutes=30):
            continue
        day=row["key"].split(":")[1] if row["key"].count(":")>0 else now.astimezone(TZ).strftime("%Y-%m-%d")
        if not (len(day)==10 and day[4]=="-" and day[7]=="-"):
            day=now.astimezone(TZ).strftime("%Y-%m-%d")
        msg=health_message(kind=row["category"],date=day,findings=1)
        result=send_owner_alert(bot_token=token,chat_id=recipient,message=msg,
                                explicitly_enabled=enabled,sender=sender)
        success=result["status"]=="PROVIDER_ACCEPTED"
        ledger.mark_alert(row["key"],"PROVIDER_ACCEPTED" if success else "BLOCKED",
                          now,result.get("message_id"))
        accepted+=int(success)
        blocked+=int(not success)
    return {"provider_accepted":accepted,"unverified_or_blocked":blocked,
            "handset_delivery_verified":False,"send_enabled":enabled}
