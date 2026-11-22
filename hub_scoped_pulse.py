"""Owner-only, disabled-by-default scoped Pulse receipt from existing J Command Hub.

Requires NEW dedicated Hub route secret, not broad HUB_RECORD_READ_TOKEN.
No text, names, full records, write/list capabilities, or model-supplied targets.
Never call automatically; this is an explicit, owner-only Telegram command.
"""
from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

SITE = "https://j-command-hub.jlemay90.chatgpt.site"
ENDPOINT = "/api/zeus-link/probe"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
REQUEST_ID = re.compile(r"^ZEUS-HUB-LINK-[0-9]{8}-[A-Z0-9]{4,16}$")
ISO = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T")
DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
MAX_REPLY_BYTES = 2048


class ScopedHubError(RuntimeError):
    pass


class DenyRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def readiness(*, env=None):
    e = os.environ if env is None else env
    return {
        "request": "scoped-pulse-read",
        "status": "READY_NOT_VERIFIED" if (
            e.get("HUB_ZEUS_SCOPED_READ_ENABLED") == "true"
            and bool(HEX64.fullmatch(e.get("HUB_ZEUS_SCOPED_READ_TOKEN", "")))
        ) else "BLOCKED_NOT_CONFIGURED",
        "enabled": e.get("HUB_ZEUS_SCOPED_READ_ENABLED") == "true",
        "scopedCredentialPresent": bool(HEX64.fullmatch(e.get("HUB_ZEUS_SCOPED_READ_TOKEN", ""))),
        "scope": "pulse_metadata_only_v1",
        "writeAccess": "NOT_AVAILABLE",
        "note": "Configuration is not proof of live Site authentication.",
    }


def verify_scoped_pulse(*, env=None, opener=None, now=None, request_id=None):
    e = os.environ if env is None else env
    if e.get("HUB_ZEUS_SCOPED_READ_ENABLED") != "true":
        raise ScopedHubError("Scoped Hub Pulse read is disabled.")
    token = e.get("HUB_ZEUS_SCOPED_READ_TOKEN", "")
    if not isinstance(token, str) or not HEX64.fullmatch(token):
        raise ScopedHubError("New scoped Hub route credential is not configured.")
    if e.get("HUB_SITE_URL", SITE) != SITE:
        raise ScopedHubError("Hub host mismatch; refusing request.")
    moment = now or datetime.now(timezone.utc)
    request_id = request_id or "ZEUS-HUB-LINK-%s-%s" % (
        moment.strftime("%Y%m%d"), secrets.token_hex(5).upper())
    if not REQUEST_ID.fullmatch(request_id):
        raise ScopedHubError("Request ID is invalid.")
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "Cache-Control": "no-store",
    }
    siwc = e.get("HUB_SIWC_BYPASS_TOKEN", "")
    if siwc:
        if not isinstance(siwc, str) or len(siwc) < 32 or len(siwc) > 500:
            raise ScopedHubError("Optional Sites service credential is invalid.")
        headers["OAI-Sites-Authorization"] = "Bearer " + siwc

    req = Request(SITE + ENDPOINT + "?" + urlencode({"requestId": request_id}),
                  method="GET", headers=headers)
    try:
        if opener is None:
            with build_opener(DenyRedirects()).open(req, timeout=8) as response:
                status, body = getattr(response, "status", None), response.read(MAX_REPLY_BYTES + 1)
        else:
            with opener(req, timeout=8) as response:
                status, body = getattr(response, "status", None), response.read(MAX_REPLY_BYTES + 1)
    except HTTPError as exc:
        raise ScopedHubError("Hub rejected the scoped probe (HTTP %d)." % exc.code) from None
    except (URLError, TimeoutError, OSError):
        raise ScopedHubError("Scoped Hub connection is unavailable.") from None

    if status != 200 or len(body) > MAX_REPLY_BYTES:
        raise ScopedHubError("Hub did not return a valid bounded success receipt.")
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ScopedHubError("Hub response was not valid JSON.") from None
    if not isinstance(data, dict) or data.get("ok") is not True or data.get("scope") != "pulse_metadata_only_v1":
        raise ScopedHubError("Hub response was not an authenticated scoped receipt.")
    if data.get("source") != "existing_hub_r2_pulse" or data.get("requestId") != request_id:
        raise ScopedHubError("Hub source or request ID did not match.")
    date, stamp = data.get("pulseDate"), data.get("checkedAt")
    if not isinstance(date, str) or not DATE.fullmatch(date):
        raise ScopedHubError("Hub Pulse date was invalid.")
    if not isinstance(stamp, str) or not ISO.match(stamp):
        raise ScopedHubError("Hub observation timestamp was invalid.")
    if type(data.get("storageReadCount")) is not int or data["storageReadCount"] != 1:
        raise ScopedHubError("Unexpected scoped storage read count.")
    if type(data.get("writes")) is not int or data["writes"] != 0:
        raise ScopedHubError("Unexpected write count.")
    return {
        "requestId": request_id,
        "status": "PASS_READ_ONLY",
        "verifiedEffect": "one_pulse_metadata_read",
        "scope": "pulse_metadata_only_v1",
        "source": "existing_hub_r2_pulse",
        "pulseDate": date,
        "checkedAt": stamp,
        "storageReadCount": 1,
        "writes": 0,
        "responseBodyExposed": False,
        "next": "Compare pulseDate to independently authenticated ChatGPT Hub read.",
    }


def report(*, env=None):
    request_id = "ZEUS-HUB-LINK-%s-%s" % (
        datetime.now(timezone.utc).strftime("%Y%m%d"), secrets.token_hex(5).upper())
    try:
        return json.dumps(verify_scoped_pulse(env=env, request_id=request_id), sort_keys=True)
    except ScopedHubError as exc:
        return json.dumps({
            "requestId": request_id, "status": "BLOCKED",
            "reason": str(exc), "writes": 0,
            "responseBodyExposed": False,
            "next": "Verify secret configuration, deployed route and owner authorization.",
        }, sort_keys=True)
