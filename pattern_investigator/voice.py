"""Pattern Investigator owner-only notification transport; OFF by default.

Sends only redacted run health and reviewed finding COUNT, never raw source text.
Telegram API acceptance is NOT proof of handset or human delivery.
"""
from __future__ import annotations
import json
import re
import urllib.request
import urllib.error

class DeliveryBlocked(Exception):
    pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DeliveryBlocked("redirect forbidden")

def send_owner_alert(*, bot_token:str, chat_id:str, message:str,
                     explicitly_enabled:bool=False, sender=None)->dict:
    if explicitly_enabled is not True:
        return {"status":"BLOCKED_NOT_ENABLED","provider":"telegram"}
    if (not isinstance(bot_token,str) or len(bot_token)<28 or len(bot_token)>180 or
        not re.fullmatch(r"[0-9]{5,15}:[A-Za-z0-9_-]{20,}",bot_token) or
        not isinstance(chat_id,str) or not re.fullmatch(r"-?[0-9]{5,18}",chat_id)):
        return {"status":"BLOCKED_NOT_CONFIGURED","provider":"telegram"}
    if (not isinstance(message,str) or len(message)>550 or
        any(x in message for x in ("http://","https://","token=","Bearer "))):
        return {"status":"BLOCKED_UNSAFE_MESSAGE","provider":"telegram"}
    body=json.dumps({"chat_id":chat_id,"text":message,"disable_web_page_preview":True}).encode("utf-8")
    req=urllib.request.Request("https://api.telegram.org/bot"+bot_token+"/sendMessage",
                               data=body,method="POST",
                               headers={"Content-Type":"application/json","Accept":"application/json"})
    try:
        if sender is None:
            with urllib.request.build_opener(NoRedirect()).open(req,timeout=8) as response:
                status,payload=response.status,response.read(2048)
        else:
            status,payload=sender(req,8,2048)
        d=json.loads(payload)
        mid=d.get("result",{}).get("message_id") if isinstance(d,dict) else None
        if status!=200 or d.get("ok") is not True or not isinstance(mid,int):
            raise DeliveryBlocked("provider rejected")
        return {"status":"PROVIDER_ACCEPTED","provider":"telegram","message_id":str(mid),
                "handset_delivery_verified":False}
    except (DeliveryBlocked,TimeoutError,OSError,ValueError,urllib.error.URLError):
        return {"status":"FAILED_UNVERIFIED","provider":"telegram","handset_delivery_verified":False}

def health_message(*,kind:str,date:str,findings:int=0)->str:
    if kind not in {"MISSED_RUN","FAILED_RUN","IMPORTANT_FINDING","DELIVERY_FAILURE"}:
        raise ValueError("invalid kind")
    if not isinstance(date,str) or not re.fullmatch(r"\d{4}-\d\d-\d\d",date):
        raise ValueError("invalid date")
    if not isinstance(findings,int) or findings<0 or findings>30:
        raise ValueError("invalid count")
    if kind=="IMPORTANT_FINDING":
        return f"J Pattern Investigator: {findings} evidence-reviewed candidate(s) on {date}. Check private Hub review. No experiment was run."
    if kind=="MISSED_RUN":
        return f"J Pattern Investigator ALERT: expected run missing or overdue for {date}. Investigate private service; no results are assumed."
    if kind=="FAILED_RUN":
        return f"J Pattern Investigator ALERT: run blocked or failed on {date}; no pattern claims are trusted."
    return f"J Pattern Investigator ALERT: notification delivery failure detected for {date}. Check private service log."
