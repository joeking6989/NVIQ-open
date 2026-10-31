import json
from collections import Counter
from pathlib import Path

from nviq.audit.runner import run_audit, write_audit_artifacts
from nviq.execution.csc import run_csc_case
from nviq.execution.canonical_lanes import CANONICAL_LANE_FAMILIES, run_canonical_lane_case

from .evaluators import derive_observation


def derive_observations(cases: list[dict], evidence_records: list[dict]) -> list[dict]:
    cases_by_id = {case["case_id"]: case for case in cases}
    derived = []
    for evidence in evidence_records:
        case = cases_by_id[evidence["case_id"]]
        family = case.get("family")
        if family in CANONICAL_LANE_FAMILIES:
            derived.append(run_canonical_lane_case(case, evidence))
        elif family == "causal_speech_cognition" and "ledger" in evidence:
            result = run_csc_case({"case_id": case["case_id"], "ledger": evidence["ledger"], "expected": case.get("expected", {})})
            derived.append({
                "case_id": case["case_id"], "track": evidence["track"],
                "metrics": result["metrics"],
                "catastrophic_failures": result["catastrophic_failures"],
                "execution": {"status": "success", "failure_reason": None},
                "trace": {
                    "source": "nviq_csc_engine_v0.1",
                    "failure_locus": result["failure_locus"],
                    "earliest_failure_time_ms": result["earliest_failure_time_ms"],
                    "belief_event_id": result["belief_event_id"],
                    "belief_time_ms": result["belief_time_ms"],
                    "decision_event_id": result["decision_event_id"],
                    "decision_time_ms": result["decision_time_ms"],
                },
                "evidence_refs": evidence.get("provenance", {}).get("evidence_refs", []),
                "adapter": {"kind": "nviq_csc_engine", "provider": evidence.get("provenance", {}).get("provider"), "model": evidence.get("provenance", {}).get("model"), "configuration": evidence.get("provenance", {}).get("configuration", {})},
            })
        else:
            derived.append(derive_observation(case, evidence))
    return sorted(derived, key=lambda row: (row["case_id"], row["track"]))


def _execution_summary(cases: list[dict], evidence_records: list[dict], observations: list[dict]) -> dict:
    case_map = {case["case_id"]: case for case in cases}
    family_counts = Counter(case_map[row["case_id"]]["family"] for row in observations)
    track_counts = Counter(row["track"] for row in observations)
    return {"execution_version":"0.1","evidence_record_count":len(evidence_records),"derived_observation_count":len(observations),"tracks":dict(sorted(track_counts.items())),"families":dict(sorted(family_counts.items()))}


def execute_audit(manifest: dict, cases: list[dict], evidence_records: list[dict], remediation_registry: list[dict], output_dir: Path) -> dict:
    observations = derive_observations(cases, evidence_records)
    report = run_audit(manifest, cases, observations, remediation_registry)
    paths = write_audit_artifacts(report, output_dir)
    derived_path = output_dir / "derived-observations.json"
    summary_path = output_dir / "evidence-summary.json"
    derived_path.write_text(json.dumps(observations, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path.write_text(json.dumps(_execution_summary(cases, evidence_records, observations), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"report":report,"observations":observations,"paths":{**paths,"derived_observations":derived_path,"evidence_summary":summary_path}}
