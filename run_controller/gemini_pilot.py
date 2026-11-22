"""Manual, non-scheduled J RUN Gemini read-only pilot entry point."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from .controller import Controller, RunError
from .gemini_readonly import GeminiReadOnlyWorker, RateCard, validate_manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description="Owner-authorized read-only Gemini pilot (not an always-on agent)")
    parser.add_argument("--manifest", required=True, type=Path, help="pre-reviewed PUBLIC evidence manifest")
    parser.add_argument("--db", required=True, type=Path, help="PRIVATE persistent SQLite checkpoint path")
    parser.add_argument("--model", required=True, help="exact Gemini model allowed by this project's credential")
    parser.add_argument("--input-price-per-million", required=True, type=float)
    parser.add_argument("--output-price-per-million", required=True, type=float)
    parser.add_argument("--max-usd", required=True, type=float, help="estimated budget limit, NOT a billing guarantee")
    parser.add_argument("--max-seconds", default=300, type=float)
    parser.add_argument("--authorize-model-calls", action="store_true", help="explicitly allow paid inference requests")
    parser.add_argument("--preview", action="store_true", help="validate manifest and configuration; NO network or DB write")
    parser.add_argument("--mission-id", help="resume a READY mission only; never auto-reconcile a failed cycle")
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    tasks = validate_manifest(manifest)
    rate_card = RateCard(args.input_price_per_million, args.output_price_per_million)
    if not 0 < args.max_usd <= 5:
        parser.error("pilot requires an explicit estimated budget >$0 and <=$5")
    if not 1 <= args.max_seconds <= 3600:
        parser.error("pilot max duration must be 1-3600 seconds")
    if len(tasks) != 5:
        parser.error("acceptance pilot requires exactly five public evidence tasks")
    if args.preview:
        print(json.dumps({"validated_public_tasks": len(tasks), "no_network": True,
                          "no_db_write": True, "model": args.model, "estimated_budget_usd": args.max_usd}))
        return 0
    if not args.authorize_model_calls or not os.environ.get("GEMINI_API_KEY"):
        parser.error("blocked: --authorize-model-calls AND GEMINI_API_KEY are required; no model request made")
    args.db.parent.mkdir(parents=True, exist_ok=True)
    controller = Controller(args.db)
    try:
        fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        config = {"manifest_sha256": fingerprint, "model": args.model,
                  "rate_input": rate_card.input_usd_per_million,
                  "rate_output": rate_card.output_usd_per_million}
        if args.mission_id:
            mission_id = args.mission_id
            old = controller.status(mission_id)
            if old["status"] != "ready" or any(old["state"].get(k) != v for k, v in config.items()):
                raise RunError("cannot resume: checkpoint state, model, or rate card has changed")
            if old["max_cost_usd"] != args.max_usd or old["max_cycles"] != 5:
                raise RunError("cannot resume with a different limit")
        else:
            mission_id = controller.create("J RUN public-source Gemini pilot", max_cycles=5,
                                           max_seconds=args.max_seconds, max_cost_usd=args.max_usd,
                                           initial_state={**config, "findings": []})
        worker = GeminiReadOnlyWorker(manifest, model=args.model, rate_card=rate_card,
                                      remaining_usd=lambda mid: max(0, controller.status(mid)["max_cost_usd"] -
                                                                 controller.status(mid)["spent_usd"]),
                                      authorized=args.authorize_model_calls)
        result = controller.run(mission_id, worker)
        print(json.dumps({"mission_id": mission_id, "status": result["status"],
                          "cycles_completed": result["completed"],
                          "estimated_usd_not_billed": result["spent_usd"],
                          "human_review_required": True}, sort_keys=True))
        return 0 if result["status"] == "completed" else 2
    finally:
        controller.close()


if __name__ == "__main__":
    raise SystemExit(main())
