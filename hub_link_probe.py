"""Zeus -> private J Command Hub limited read-only probe.

Disabled until the actual Hub Site has a separately authorized read-only
endpoint and the Replit Secret store contains BOTH the Sites SIWC bypass token
and a distinct scoped Hub-link token. Never copy user records to Zeus.
"""
from __future__ import annotations

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

SITE = "https://j-command-hub.jlemay90.chatgpt.site"
MARKER_RE = re.compile(r"^ZEUS-HUB-LINK-[0-9]{8}-[A-Z0-9]{4,16}$")
MAX_REPLY_BYTES = 2048


class HubLinkError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _read(response):
    body = response.read(MAX_REPLY_BYTES + 1)
    if len(body) > MAX_REPLY_BYTES:
        raise HubLinkError("Hub replied with an oversized response")
    try:
        return json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise HubLinkError("Hub returned a non-JSON response") from None


def probe(marker, *, env=None, opener=None):
    """Returns a small source-linked receipt. Never modifies Hub state."""
    if not isinstance(marker, str) or not MARKER_RE.fullmatch(marker):
        raise HubLinkError("Invalid owner-approved marker; no connection attempted")
    env = os.environ if env is None else env
    if env.get("HUB_SITE_URL", SITE) != SITE:
        raise HubLinkError("Hub host mismatch; fail closed")
    if env.get("HUB_ZEUS_LINK_READ_ENABLED") != "true":
        raise HubLinkError("Zeus Hub read link is disabled")
    siwc = env.get("HUB_SIWC_BYPASS_TOKEN", "")
    scoped = env.get("HUB_ZEUS_LINK_SECRET", "")
    if len(siwc) < 32 or len(scoped) < 32:
        raise HubLinkError("Hub link credentials are missing; do not paste secrets")
    req = Request(
        SITE + "/api/zeus-link/probe?" + urlencode({"marker": marker}),
        headers={"OAI-Sites-Authorization": "Bearer " + siwc,
                 "Authorization": "Bearer " + scoped,
                 "Accept": "application/json", "Cache-Control": "no-store"},
        method="GET")
    try:
        if opener is None:
            with build_opener(NoRedirect()).open(req, timeout=8) as response:
                status = getattr(response, "status", None)
                payload = _read(response)
        else:
            with opener(req, timeout=8) as response:
                status = getattr(response, "status", None)
                payload = _read(response)
    except HTTPError as exc:
        # A 401/403 may be from Sites or the separate scoped Hub API.
        raise HubLinkError("Hub refused authorization or endpoint (HTTP %d)" % exc.code) from None
    except (URLError, TimeoutError, OSError) as exc:
        raise HubLinkError("Hub transport unavailable (%s)" % type(exc).__name__) from None

    if status != 200 or not isinstance(payload, dict) or payload.get("ok") is not True:
        raise HubLinkError("Hub probe not successful; no live read confirmed")
    if payload.get("source") != "authenticated_live_hub_storage" or payload.get("scope") != "read_only_probe_v1":
        raise HubLinkError("Hub source is unrecognized; historical snapshots are not live proof")
    if type(payload.get("itemCount")) is not int or not 0 <= payload["itemCount"] <= 1_000_000:
        raise HubLinkError("Hub item count is invalid")
    if type(payload.get("markerFound")) is not bool:
        raise HubLinkError("Hub marker confirmation is missing")
    stamp = payload.get("checkedAt")
    if not isinstance(stamp, str) or not re.match(r"^\d{4}-\d{2}-\d{2}T", stamp):
        raise HubLinkError("Live Hub read timestamp is missing")
    day = payload.get("pulseDate")
    if day is not None and (not isinstance(day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day)):
        raise HubLinkError("Hub pulse date invalid")
    return {
        "status": "PASS_READ_ONLY",
        "request": marker,
        "source": payload["source"],
        "checkedAt": stamp,
        "pulseDate": day,
        "itemCount": payload["itemCount"],
        "markerFound": payload["markerFound"],
        "writeAccess": "NOT_TESTED",
        "next": "Independent readback from ChatGPT Hub; write remains disabled.",
    }


def report(argument=""):
    """Telegram command: /hublink status or /hublink probe ZEUS-HUB-LINK-..."""
    parts = argument.strip().split()
    if not parts or parts == ["status"]:
        return json.dumps({
            "status": "DRAFT_OR_DISABLED",
            "enabled": os.getenv("HUB_ZEUS_LINK_READ_ENABLED") == "true",
            "credentials_present": bool(os.getenv("HUB_SIWC_BYPASS_TOKEN")) and bool(os.getenv("HUB_ZEUS_LINK_SECRET")),
            "writeAccess": "NOT_AVAILABLE",
            "note": "A working Telegram reply is not proof of Hub access. Use /hublink probe MARKER after authenticated deployment.",
        }, sort_keys=True)
    if parts == ["verify-scoped"]:
        from hub_scoped_pulse import report as scoped_report
        return scoped_report()
    if len(parts) == 2 and parts[0] == "probe":
        try:
            return json.dumps(probe(parts[1]), sort_keys=True)
        except HubLinkError as exc:
            return json.dumps({"status": "BLOCKED", "reason": str(exc),
                               "writeAccess": "NOT_AVAILABLE"}, sort_keys=True)
    return "Use /hublink status, /hublink probe MARKER, or /hublink verify-scoped."
