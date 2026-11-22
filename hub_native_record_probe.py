"""Owner-only, one-record native J Command Hub read verification for Zeus.

This adapter is DISABLED BY DEFAULT and makes a single GET request only to the
existing deployed Sites v28 API. The Hub returns full record content; this
adapter NEVER forwards it to Telegram, AI models, logs, or saved state.

The Hub's bearer is NOT narrowly scoped at its origin. Deploying this client
or copying the token into Zeus requires a separate owner-approved risk review.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

SITE = "https://j-command-hub.jlemay90.chatgpt.site"
RECORD_PATH = "/api/v1/records/item/"
UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
BEARER = re.compile(r"^[0-9a-f]{64}$")
MAX_RESPONSE_BYTES = 65536


class NativeHubProbeError(RuntimeError):
    """Safe, non-secret operator error."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def status(*, env=None):
    env = os.environ if env is None else env
    return {
        "status": "DRAFT_OR_DISABLED",
        "enabled": env.get("HUB_NATIVE_RECORD_CHECK_ENABLED") == "true",
        "test_record_configured": bool(UUID.fullmatch(env.get("HUB_NATIVE_TEST_ITEM_ID", ""))),
        "credential_configured": bool(BEARER.fullmatch(env.get("HUB_RECORD_READ_TOKEN", ""))),
        "tokenScope": "EXISTING_BROAD_RECORD_READ",
        "writeAccess": "NOT_AVAILABLE",
        "note": "This is not a live connection receipt. No record content is exposed. Use verify-native only after separate deployment and credential approval.",
    }


def verify_one_item(*, env=None, opener=None, clock=None):
    """Read ONE operator-pinned item, discard content, return metadata-only receipt.

    Inputs contain no user-supplied type or ID, blocking arbitrary record queries
    from Telegram, model messages, and prompt injection.
    """
    env = os.environ if env is None else env
    if env.get("HUB_NATIVE_RECORD_CHECK_ENABLED") != "true":
        raise NativeHubProbeError("Native Hub record check is disabled.")
    item_id = env.get("HUB_NATIVE_TEST_ITEM_ID", "")
    token = env.get("HUB_RECORD_READ_TOKEN", "")
    if not isinstance(item_id, str) or not UUID.fullmatch(item_id):
        raise NativeHubProbeError("A valid operator-pinned test item ID is missing.")
    if not isinstance(token, str) or not BEARER.fullmatch(token):
        raise NativeHubProbeError("A valid secret credential is not configured in Zeus.")
    if env.get("HUB_SITE_URL", SITE) != SITE:
        raise NativeHubProbeError("Pinned Hub host mismatch.")
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "Cache-Control": "no-store",
    }
    siwc = env.get("HUB_SIWC_BYPASS_TOKEN", "")
    if siwc:
        if len(siwc) < 32:
            raise NativeHubProbeError("Configured SIWC service credential is invalid.")
        headers["OAI-Sites-Authorization"] = "Bearer " + siwc
    request = Request(SITE + RECORD_PATH + item_id, headers=headers, method="GET")
    try:
        if opener is None:
            with build_opener(NoRedirect()).open(request, timeout=8) as response:
                code, raw = getattr(response, "status", None), response.read(MAX_RESPONSE_BYTES + 1)
        else:
            with opener(request, timeout=8) as response:
                code, raw = getattr(response, "status", None), response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise NativeHubProbeError("Hub rejected the record check (HTTP %d)." % exc.code) from None
    except (URLError, TimeoutError, OSError):
        raise NativeHubProbeError("Hub connection unavailable.") from None
    if code != 200:
        raise NativeHubProbeError("Hub did not return an HTTP 200 read receipt.")
    if len(raw) > MAX_RESPONSE_BYTES:
        raise NativeHubProbeError("Hub record response exceeds test limits.")
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise NativeHubProbeError("Hub returned an invalid JSON response.") from None
    record = body.get("record") if isinstance(body, dict) and body.get("ok") is True else None
    if not isinstance(record, dict):
        raise NativeHubProbeError("Hub did not return a verified record wrapper.")
    if record.get("type") != "item" or not isinstance(record.get("id"), str) or record["id"].lower() != item_id.lower():
        raise NativeHubProbeError("Hub record identity did not match the approved test item.")
    if not isinstance(record.get("content"), dict):
        raise NativeHubProbeError("Hub record content structure was not recognized.")
    # Do not return, log or save the body or record objects.
    id_hash = hashlib.sha256(("item:" + item_id.lower()).encode("ascii")).hexdigest()[:12]
    observed_at = (clock or (lambda: datetime.now(timezone.utc)))().isoformat()
    return {
        "status": "PASS_READ_ONLY",
        "request": "owner-pinned-native-record-check",
        "origin": SITE,
        "source": "existing_hub_record_api",
        "recordType": "item",
        "recordIdentityHash": id_hash,
        "identityMatched": True,
        "observedAt": observed_at,
        "responseBodyExposed": False,
        "tokenScope": "EXISTING_BROAD_RECORD_READ",
        "writeAccess": "NOT_AVAILABLE",
        "next": "Independently verify approved item existence using the authenticated Hub connector.",
    }


def report(*, env=None):
    """A structured Telegram message without user-provided target records."""
    try:
        return json.dumps(verify_one_item(env=env), sort_keys=True)
    except NativeHubProbeError as exc:
        return json.dumps({
            "status": "BLOCKED", "reason": str(exc),
            "writeAccess": "NOT_AVAILABLE",
            "responseBodyExposed": False,
        }, sort_keys=True)
