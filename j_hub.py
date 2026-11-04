"""Read-only, dated Hub project handoff over the existing approved Git connection."""
import datetime as dt
import json
from j_repository import git, verified_origin, RepoError

SOURCE = "https://j-command-hub.jlemay90.chatgpt.site"
PATH = "hub_project_context.json"

def validate(raw):
    if len(raw) > 16000:
        raise ValueError("Hub project handoff exceeds its size limit.")
    value = json.loads(raw)
    if value.get("schema_version") != 1 or value.get("source") != SOURCE or value.get("live_sync") is not False:
        raise ValueError("Hub project handoff has an unexpected source or schema.")
    captured = dt.datetime.fromisoformat(value["captured_at_utc"].replace("Z", "+00:00"))
    if captured.tzinfo is None or captured > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
        raise ValueError("Hub project handoff timestamp is invalid.")
    if type(value.get("hub_revision")) is not int:
        raise ValueError("Hub project handoff revision is invalid.")
    out = {key: value[key] for key in ("schema_version", "source", "captured_at_utc", "hub_revision", "live_sync")}
    for key in ("decisions", "next_steps", "limits"):
        rows = value.get(key, [])
        if not isinstance(rows, list) or len(rows) > 20 or any(not isinstance(x, str) or len(x)>1500 for x in rows):
            raise ValueError("Hub project handoff fields are invalid.")
        out[key] = rows
    out["scope"] = "Software project handoff only; no personal Hub tasks or documents."
    out["age_hours"] = round(max(0, (dt.datetime.now(dt.timezone.utc)-captured).total_seconds()/3600), 1)
    out["stale"] = out["age_hours"] > 24
    out["reference_only"] = True
    return out

def cached():
    try:
        verified_origin()
        out = validate(git("show", "refs/remotes/origin/main:" + PATH))
        out["source_commit"] = git("rev-parse", "refs/remotes/origin/main")
        out["status"] = "dated_snapshot"
        return out
    except (RepoError, ValueError, KeyError, TypeError):
        return {"status":"unavailable", "live_sync":False, "note":"No validated Hub project handoff available. No live Hub or Drive access is implied."}


def model_context():
    """Historical handoffs cannot attest to current authenticated Hub state."""
    value = cached()
    metadata = {
        "status": "unverified",
        "live_sync": False,
        "project_memory_revision": None,
        "reference_only": True,
        "note": "Current J Hub projectMemory revision is not live authenticated here.",
    }
    if value.get("status") != "dated_snapshot":
        return metadata
    metadata.update(
        status="stale_snapshot_excluded" if value["stale"] else "historical_snapshot",
        captured_at_utc=value["captured_at_utc"],
        handoff_revision=value["hub_revision"],
    )
    # Do not feed obsolete roadmaps/decisions to the model as current project state.
    if not value["stale"]:
        metadata["historical_reference"] = {
            key: value[key] for key in ("decisions", "next_steps", "limits")
        }
    return metadata


def report(refresh=True):
    if refresh:
        try:
            verified_origin()
            git("fetch", "--no-tags", "origin", "main")
        except RepoError:
            return "Hub project refresh failed. No live Hub access or successful synchronization is claimed."
    value = cached()
    if value["status"] == "unavailable":
        return value["note"]
    return ("Hub project handoff — DATED SNAPSHOT, not live Hub access\n"
            + "Captured UTC: " + value["captured_at_utc"]
            + "\nHistorical handoff revision: " + str(value["hub_revision"])
            + "\nCurrent J Hub projectMemory revision: unverified (no live authenticated source)."
            + "\nGit commit: " + value["source_commit"][:12]
            + "\nSource: " + SOURCE
            + "\n" + ("STALE: over 24 hours old. Confirm current status." if value["stale"] else "Snapshot is under 24 hours old; it is not live project state.")
            + "\n\nBuild roadmap:\n" + "\n".join(value["next_steps"])
            + "\n\nRead-only project snapshot. No Hub writes or Drive/Gmail/Calendar access.")
