"""Pattern Investigator Brain: evidence-linked, non-diagnostic review.

No external AI call occurs in this module. Optional hosted model adapters MUST be
separately approved, scoped and tested; this deterministic brain is the safe fallback.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

RANK = {
    "SUPPORTED_RECURRENCE": 0,
    "POSSIBLE_RECURRENCE": 1,
    "CONTESTED": 2,
    "STALE_REVERIFY": 3,
    "INSUFFICIENT_EVIDENCE": 4,
    "REQUIRES_SEPARATE_CONSENT": 5,
}

def assess(review: dict, *, limit: int = 3) -> dict:
    if not isinstance(review,dict) or review.get("run_status") != "EVIDENCE_REVIEW_COMPLETED":
        raise ValueError("verified local evidence review required")
    if not isinstance(limit,int) or isinstance(limit,bool) or not 1<=limit<=5:
        raise ValueError("invalid limit")
    findings=review.get("findings")
    if not isinstance(findings,list) or len(findings)>30:
        raise ValueError("unbounded findings")
    ranked=[]
    for finding in findings:
        if not isinstance(finding,dict) or finding.get("assessment") not in RANK:
            raise ValueError("unrecognized assessment")
        ids=finding.get("evidence")
        negatives=finding.get("disconfirming_evidence")
        alts=finding.get("alternative_explanations")
        if (not isinstance(ids,list) or not isinstance(negatives,list) or
            not isinstance(alts,list) or len(alts)<2 or
            any(not isinstance(s,str) for s in ids+negatives+alts)):
            raise ValueError("missing evidence, counterevidence or alternatives")
        status=finding["assessment"]
        safe=status in {"SUPPORTED_RECURRENCE","POSSIBLE_RECURRENCE"}
        ranked.append({
            "theme":finding["theme"], "assessment":status,
            "supporting_record_ids":ids, "contradicting_record_ids":negatives,
            "alternative_explanations":alts[:3],
            "significance":"possible repeated circumstances; NOT a diagnosis or proof of causation",
            "confidence":("MODERATE_FOR_REPETITION_ONLY" if status=="SUPPORTED_RECURRENCE" else
                          "LOW_FOR_REPETITION_ONLY" if status=="POSSIBLE_RECURRENCE" else "UNESTABLISHED"),
            "proposed_experiment":({
                "proposal":"With owner approval, choose one small, reversible change for this theme.",
                "baseline":"Record existing frequency/outcome before changing anything.",
                "measurement":"Compare the same observable measure after the agreed test period.",
                "stopping_rule":"Stop on cost, family disruption, increased stress or owner request.",
                "status":"PROPOSED_NOT_AUTHORIZED_NOT_RUN",
            } if safe else None),
            "next_step":("Request owner approval for a measured, reversible experiment."
                         if safe else "Seek fresh and contrary evidence; do not intervene."),
            "owner_approval_needed":safe,
        })
    ranked.sort(key=lambda x:(RANK[x["assessment"]],x["theme"]))
    return {
        "schema_version":"0.2",
        "source_run_id":review.get("run_id"),
        "analysis_mode":"RULE_BASED_NO_EXTERNAL_AI",
        "analysis_status":"COMPLETED",
        "created_at_utc":review.get("created_at_utc"),
        "findings_total":len(ranked),
        "findings_returned":min(limit,len(ranked)),
        "findings":ranked[:limit],
        "experiments_executed":0,
        "outcomes_verified":0,
        "cannot_infer":"causation, stable personality, third-party motives, medical diagnosis, or actual completion",
    }
