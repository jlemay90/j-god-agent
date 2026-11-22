"""Private local CLI; JSON on stdin, JSON receipt on stdout. No API calls."""
import argparse
import json
import sys
from .engine import InvalidInput, investigate, watchdog


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline Pattern Investigator evidence gate")
    parser.add_argument("mode", choices=("investigate", "watchdog"))
    parser.add_argument("--max-age-hours", type=int, default=36)
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
        result = investigate(payload) if args.mode == "investigate" else watchdog(payload, max_age_hours=args.max_age_hours)
    except (InvalidInput, json.JSONDecodeError) as exc:
        # Validation errors are structured; avoid echoing sensitive input.
        print(json.dumps({"run_status": "BLOCKED", "error": str(exc), "delivery_status": "NOT_SENT"}))
        return 2
    print(json.dumps(result, indent=2))
    return 0 if args.mode == "investigate" or result["check_status"] == "ON_TIME" else 3

if __name__ == "__main__":
    sys.exit(main())