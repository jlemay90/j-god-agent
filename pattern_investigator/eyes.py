"""Pattern Investigator Eyes v0.2: pinned HTTPS, owner-scoped, read-only transport.

Only an independently authorized private Sites route may supply personal data.
This client does not grant consent or prove that the Sites route is deployed.
The older Zeus /api/zeus-link/probe is metadata-only and is NOT an evidence source.
"""
from __future__ import annotations
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Callable, Any

SITE_URL = "https://j-command-hub.jlemay90.chatgpt.site/api/pattern-investigator/evidence"
MAX_RESPONSE = 64000
MAX_ROWS = 100
SECRET = re.compile(r"^[!-~]{32,256}$")

class EyesBlocked(Exception):
    """No private data or credential values in exceptions."""

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise EyesBlocked("redirect forbidden")

def _parse_date(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError) as exc:
        raise EyesBlocked("invalid source timestamp") from exc

def fetch_hub_evidence(*, siwc_token: str, route_secret: str,
                       opener: Callable[..., Any] | None = None,
                       now: datetime | None = None) -> dict:
    """Fetch curated observations, NEVER the full owner Hub state.

    A real operator must configure both independent private credentials.
    'Authenticated' means accepted by the private scoped route, not proof that
    any personal observation was true. Downstream evidence gate still applies.
    """
    if not all(isinstance(s, str) and SECRET.fullmatch(s) for s in (siwc_token, route_secret)):
        raise EyesBlocked("private Hub source not configured")
    req = urllib.request.Request(
        SITE_URL,
        headers={"Authorization": "Bearer " + route_secret,
                 "OAI-Sites-Authorization": "Bearer " + siwc_token,
                 "Accept": "application/json"},
        method="GET"
    )
    try:
        if opener is None:
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=8) as response:
                status = response.status
                data = response.read(MAX_RESPONSE + 1)
                target = response.geturl()
        else:
            status, data, target = opener(req, 8, MAX_RESPONSE + 1)
    except (EyesBlocked, TimeoutError, OSError, urllib.error.URLError) as exc:
        raise EyesBlocked("private Hub source unavailable") from exc
    if status != 200 or target != SITE_URL or not isinstance(data, bytes) or len(data) > MAX_RESPONSE:
        raise EyesBlocked("private Hub response rejected")
    try:
        result = json.loads(data)
    except (ValueError, UnicodeDecodeError) as exc:
        raise EyesBlocked("invalid private Hub response") from exc
    if not isinstance(result, dict) or result.get("ok") is not True or (
        result.get("source") != "owner_authenticated_curated_hub_pattern_evidence"
        or result.get("scope") != "pattern_read_only_v1"):
        raise EyesBlocked("untrusted evidence source")
    checked = _parse_date(result.get("checkedAt"))
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if checked > now + timedelta(minutes=5) or checked < now - timedelta(hours=2):
        raise EyesBlocked("stale or future private Hub read")
    rows = result.get("observations")
    if not isinstance(rows, list) or len(rows) > MAX_ROWS or any(not isinstance(row, dict) for row in rows):
        raise EyesBlocked("bad curated observation bundle")
    # NEVER trust a caller's 'verified' flags as outside-world proof. These are
    # transport facts; observed claims still require original source checks.
    return {"observations": rows, "transport_receipt": {
        "source": result["source"],
        "checked_at_utc": checked.isoformat(),
        "count": len(rows),
        "method": "owner_scoped_live_hub_read_only",
        "source_revision": result.get("sourceRevision") if isinstance(result.get("sourceRevision"), str) else None,
        "external_truth_verified": False,
    }}
