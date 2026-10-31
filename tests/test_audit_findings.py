from pathlib import Path

from nviq.audit.findings import derive_findings
from nviq.audit.remediations import attach_remediations, load_remediations


ROOT = Path(__file__).resolve().parents[1]


def _report(case):
    return {"nviq_version":"0.2","tracks":{"lsr_cvf":{"case_count":1,"mean_score":case["score"],"hard_gate_failures":int(not case["hard_gate_pass"]),"catastrophic_failures":int(case["catastrophic_failure"]),"families":{},"cases":[case]}},"missing_observations":[]}


def test_catastrophic_failure_becomes_critical_with_evidence():
    case={"case_id":"NVIQ-X-001","family":"abstention_fidelity","track":"lsr_cvf","score":0.2,"hard_gate_pass":False,"catastrophic_failure":True,"catastrophic_failures":["fabricated_speech"],"missing_metrics":[],"metrics":[{"name":"abstention","observed":0.0,"threshold":1.0,"hard_gate":True,"passed":False,"normalized_score":0.0,"weight":1.0,"higher_is_better":True}]}
    observations=[{"case_id":"NVIQ-X-001","track":"lsr_cvf","metrics":{"abstention":0.0},"catastrophic_failures":["fabricated_speech"],"trace":{"decoder":"invented words"},"evidence_refs":["audio-17"]}]
    critical=[f for f in derive_findings(_report(case),observations) if f["finding_type"]=="catastrophic_failure"][0]
    assert critical["severity"]=="Critical"
    assert critical["failure_id"]=="fabricated_speech"
    assert critical["evidence"]["source_evidence_ids"]==["audio-17"]
    assert critical["evidence"]["trace"]=={"decoder":"invented words"}


def test_failed_hard_gate_is_at_least_high():
    case={"case_id":"NVIQ-C-001","family":"confidence_channel_fidelity","track":"lsr_cvf","score":0.5,"hard_gate_pass":False,"catastrophic_failure":False,"catastrophic_failures":[],"missing_metrics":[],"metrics":[{"name":"confidence_inflation_error","observed":0.4,"threshold":0.05,"hard_gate":True,"passed":False,"normalized_score":0.125,"weight":1.0,"higher_is_better":False}]}
    gate=[f for f in derive_findings(_report(case),[{"case_id":"NVIQ-C-001","track":"lsr_cvf","metrics":{},"catastrophic_failures":[]}]) if f["finding_type"]=="hard_gate_failure"][0]
    assert gate["severity"]=="High"
    assert gate["metric_name"]=="confidence_inflation_error"


def test_remediation_attachment_is_deterministic():
    findings=[{"finding_id":"F-1","family":"confidence_channel_fidelity","finding_type":"hard_gate_failure","metric_name":"confidence_inflation_error","failure_id":None}]
    registry=[{"remediation_id":"R-2","title":"Second","applies_to":["confidence_channel_fidelity"],"rationale":"r","recommended_change":"c","verification_method":"v","default_priority":"P1"},{"remediation_id":"R-1","title":"First","applies_to":["confidence_inflation_error"],"rationale":"r","recommended_change":"c","verification_method":"v","default_priority":"P0"}]
    attached=attach_remediations(findings,registry)
    assert [r["remediation_id"] for r in attached[0]["remediations"]]==["R-1","R-2"]


def test_evidence_bundle_preserves_adapter_and_execution_metadata():
    case={"case_id":"NVIQ-A-001","family":"confidence_channel_fidelity","track":"lsr_cvf","score":0.0,"hard_gate_pass":False,"catastrophic_failure":False,"catastrophic_failures":[],"missing_metrics":[],"metrics":[{"name":"accuracy","observed":0.0,"threshold":1.0,"hard_gate":True,"passed":False,"normalized_score":0.0,"weight":1.0,"higher_is_better":True}]}
    observation={"case_id":"NVIQ-A-001","track":"lsr_cvf","metrics":{"accuracy":0.0},"catastrophic_failures":[],"adapter":{"kind":"precomputed","provider":"Noct-Tech","model":"fixture","configuration":{}},"execution":{"status":"success","failure_reason":None}}
    finding=derive_findings(_report(case),[observation])[0]
    assert finding["evidence"]["adapter"]["provider"]=="Noct-Tech"
    assert finding["evidence"]["execution"]["status"]=="success"


def test_floor_integrity_failure_gets_explicit_floor_arbitration_remediation():
    registry=load_remediations(ROOT/"src/nviq/data/remediations.v0.1.json")
    findings=[{
        "finding_id":"F-floor",
        "family":"conversational_floor_integrity",
        "finding_type":"catastrophic_failure",
        "metric_name":None,
        "failure_id":"conversational_floor_integrity_failure",
    }]
    attached=attach_remediations(findings,registry)
    ids=[item["remediation_id"] for item in attached[0]["remediations"]]
    assert "NVIQ-R-FLOOR-001" in ids
