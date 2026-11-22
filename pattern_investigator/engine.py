"""Pattern Investigator v0.1: deterministic, read-only evidence gate.

This module evaluates *authorized, externally sourced* observations. It never
retrieves data, diagnoses people, changes a user record, or runs an experiment.
Ingestion and delivery adapters must independently establish access, provenance,
and runtime health before claiming a deployed autonomous investigator.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any
import re
import uuid

MAX_OBSERVATIONS = 300
MAX_TEXT = 360
MAX_THEMES = 30
ALLOWED_PROVENANCE = {"original_verified", "owner_reported", "secondary", "unverified"}
ALLOWED_BASIS = {"observed_event", "owner_report", "intention", "hypothesis"}
ALLOWED_POLARITY = {"supports", "contradicts"}
GOALS = {"income", "financial_stability", "fatherhood", "health", "relationships", "freedom", "growth", "creativity", "peace", "other"}
KEY = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,99}$")


class InvalidInput(ValueError):
    """Unsafe/invalid input; never print raw personal content in exceptions."""


def _iso(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise InvalidInput(f"{label} must be an ISO-8601 timestamp")
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidInput(f"{label} must be an ISO-8601 timestamp") from exc
    if date.tzinfo is None:
        raise InvalidInput(f"{label} requires timezone")
    return date.astimezone(timezone.utc)


def _short(value: Any, label: str, *, key: bool = False) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > (100 if key else MAX_TEXT):
        raise InvalidInput(f"{label} missing or too long")
    v = value.strip()
    if key and not KEY.fullmatch(v):
        raise InvalidInput(f"{label} format invalid")
    return v


def _validate_observation(row: Any, now: datetime) -> dict:
    if not isinstance(row, dict):
        raise InvalidInput("observation must be an object")
    required = ("id", "event_id", "source_ref", "source_kind", "occurred_at", "theme", "basis", "polarity", "summary", "goal", "authorized", "sensitive")
    if any(key not in row for key in required):
        raise InvalidInput("observation missing required fields")
    if row["authorized"] is not True:
        raise InvalidInput("observation source not authorized")
    if not isinstance(row["sensitive"], bool):
        raise InvalidInput("sensitive flag must be explicit")
    for key, allowed in (("source_kind", ALLOWED_PROVENANCE), ("basis", ALLOWED_BASIS), ("polarity", ALLOWED_POLARITY), ("goal", GOALS)):
        if row[key] not in allowed:
            raise InvalidInput(f"{key} value not supported")
    occurred_at = _iso(row["occurred_at"], "occurred_at")
    if occurred_at > now + timedelta(minutes=5):
        raise InvalidInput("future evidence date")
    # Neither source_kind nor source_ref establishes that a connector read occurred.
    return {
        "id": _short(row["id"], "id", key=True),
        "event_id": _short(row["event_id"], "event_id", key=True),
        "source_ref": _short(row["source_ref"], "source_ref"),
        "source_kind": row["source_kind"],
        "occurred_at": occurred_at,
        "theme": _short(row["theme"], "theme", key=True).lower(),
        "basis": row["basis"],
        "polarity": row["polarity"],
        "summary": _short(row["summary"], "summary"),
        "goal": row["goal"],
        "sensitive": row["sensitive"],
    }


def investigate(payload: dict, *, now: datetime | None = None) -> dict:
    """Return conservative hypotheses and one audit receipt; never act on them.

    Signals are explicit themes assigned by an authorized *ingestion* layer.
    Matching a signal is recurrence detection, not causal inference. All output
    should remain private; no source content is sent anywhere by this module.
    """
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not isinstance(payload, dict) or set(payload) - {"request_id", "observations"}:
        raise InvalidInput("input must contain only request_id and observations")
    request_id = _short(payload.get("request_id"), "request_id", key=True)
    rows = payload.get("observations")
    if not isinstance(rows, list) or len(rows) > MAX_OBSERVATIONS:
        raise InvalidInput("observations must be a bounded list")
    observations = [_validate_observation(row, now) for row in rows]
    ids = [row["id"] for row in observations]
    if len(ids) != len(set(ids)):
        raise InvalidInput("duplicate observation id")

    themes: dict[str, list[dict]] = defaultdict(list)
    for row in observations:
        themes[row["theme"]].append(row)
    if len(themes) > MAX_THEMES:
        raise InvalidInput("too many themes")

    findings = []
    for theme, group in sorted(themes.items()):
        # Event IDs identify real-world observations, not notebook copies.
        by_event: dict[str, list[dict]] = defaultdict(list)
        for r in group:
            by_event[r["event_id"]].append(r)
        conflict = any(len({r["polarity"] for r in event}) > 1 for event in by_event.values())
        # Prioritize original verified receipts; don't count duplicates as support.
        priority = {"original_verified": 3, "owner_reported": 2, "secondary": 1, "unverified": 0}
        independent = [max(event, key=lambda r: priority[r["source_kind"]]) for event in by_event.values()]
        positives = [r for r in independent if r["polarity"] == "supports" and r["basis"] in {"observed_event", "owner_report"}]
        negatives = [r for r in independent if r["polarity"] == "contradicts" and r["basis"] in {"observed_event", "owner_report"}]
        dates = {r["occurred_at"].date() for r in positives}
        sources = {r["source_ref"] for r in positives}
        verified = [r for r in positives if r["source_kind"] == "original_verified"]
        stale = bool(positives) and max(r["occurred_at"] for r in positives) < now - timedelta(days=90)
        sensitive = any(r["sensitive"] for r in group)
        if sensitive:
            status = "REQUIRES_SEPARATE_CONSENT"
        elif conflict:
            status = "CONTESTED"
        elif negatives:
            status = "CONTESTED"
        elif len(positives) < 2 or len(dates) < 2:
            status = "INSUFFICIENT_EVIDENCE"
        elif stale:
            status = "STALE_REVERIFY"
        elif len(positives) >= 3 and len(sources) >= 2 and len(verified) >= 2:
            status = "SUPPORTED_RECURRENCE"
        else:
            status = "POSSIBLE_RECURRENCE"
        supporting = sorted(positives, key=lambda r: r["occurred_at"], reverse=True)
        opposing = sorted(negatives, key=lambda r: r["occurred_at"], reverse=True)
        goals = sorted({r["goal"] for r in group})
        findings.append({
            "theme": theme,
            "assessment": status,
            "interpretation": "Observed recurrence only; no causation or personality diagnosis is established.",
            "goal_links": goals,
            "evidence": [r["id"] for r in supporting],
            "disconfirming_evidence": [r["id"] for r in opposing],
            "duplicate_event_records": len(group) - len(independent),
            "distinct_event_count": len(independent),
            "independent_support_count": len(positives),
            "original_verified_count": len(verified),
            "alternative_explanations": [
                "Timing, circumstance, or incentives rather than a stable personal pattern.",
                "The available records may be incomplete or selectively captured."
            ],
            "proposed_next_step": (
                "Ask the owner whether to define a reversible, measurable experiment with a baseline and stopping rule."
                if status in {"SUPPORTED_RECURRENCE", "POSSIBLE_RECURRENCE"} else
                "Collect independent, up-to-date evidence or resolve conflicting records before suggesting a test."
            ),
            "experiment_status": "NOT_AUTHORIZED_NOT_RUN",
        })
    return {
        "schema_version": "0.1",
        "request_id": request_id,
        "run_id": str(uuid.uuid4()),
        "created_at_utc": now.isoformat(),
        "run_status": "EVIDENCE_REVIEW_COMPLETED",
        "scope": "local_read_only_evidence_review_not_live_monitoring",
        "observations_checked": len(observations),
        "themes_checked": len(themes),
        "findings": findings,
        "delivery_status": "NOT_DELIVERED_BY_ENGINE",
        "source_access_status": "SUPPLIED_BY_CALLER_NOT_INDEPENDENTLY_VERIFIED",
    }


def watchdog(receipt: dict | None, *, now: datetime | None = None, max_age_hours: int = 36) -> dict:
    """External scheduler can poll this; cannot detect its own nonexecution."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not isinstance(max_age_hours, int) or not 1 <= max_age_hours <= 720:
        raise InvalidInput("max_age_hours out of range")
    if not isinstance(receipt, dict) or receipt.get("run_status") != "EVIDENCE_REVIEW_COMPLETED":
        result = "MISSING_OR_FAILED"
        age = None
    else:
        checked_at = _iso(receipt.get("created_at_utc"), "receipt.created_at_utc")
        if checked_at > now + timedelta(minutes=5):
            result, age = "CLOCK_CONFLICT", None
        else:
            age = round((now - checked_at).total_seconds()/3600, 2)
            result = "ON_TIME" if age <= max_age_hours else "OVERDUE"
    return {"check_status": result, "age_hours": age,
            "max_age_hours": max_age_hours,
            "notification_status": "NOT_SENT_BY_ENGINE",
            "meaning": "Receipt freshness only; an external independent scheduler and delivery receipt are required."}