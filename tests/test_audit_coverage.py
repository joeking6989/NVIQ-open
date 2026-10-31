import json
from pathlib import Path

from nviq.audit.runner import run_audit, write_audit_artifacts
from nviq.audit.html import render_html
from nviq.cases import load_cases
from nviq.execution.runner import derive_observations

ROOT = Path(__file__).resolve().parents[1]


def _case(case_id):
    return {
        "case_id": case_id,
        "family": "confidence_channel_fidelity",
        "scoring": {
            "metrics": [{"name": "accuracy", "weight": 1, "higher_is_better": True, "hard_gate": True, "threshold": 1.0}],
            "catastrophic_failure_conditions": [],
        },
    }


def _observation(case_id):
    return {"case_id": case_id, "track": "lsr_cvf", "metrics": {"accuracy": 1.0}, "catastrophic_failures": []}


def _manifest():
    return {
        "audit_id": "audit-coverage",
        "customer_name": "Voice Co",
        "target_name": "Agent",
        "target_version": "1.0",
        "created_at": "2026-10-18T00:00:00+11:00",
        "benchmark_version": "0.2",
        "case_set": "inline",
        "tracks": ["lsr_cvf"],
        "evidence_sources": [{"evidence_id": "trace-1", "kind": "trace", "ref": "trace://1"}],
        "retention_policy": {"raw_audio": "not_retained", "derived_artifacts_days": 90},
    }


def test_full_coverage_still_passes_and_reports_coverage():
    cases = [_case("NVIQ-A-001"), _case("NVIQ-B-001")]
    audit = run_audit(_manifest(), cases, [_observation("NVIQ-A-001"), _observation("NVIQ-B-001")], [])
    assert audit["summary"]["overall_status"] == "pass"
    assert audit["coverage"]["complete"] is True
    assert audit["coverage"]["tracks"]["lsr_cvf"]["observed_case_count"] == 2
    assert audit["coverage"]["tracks"]["lsr_cvf"]["missing_case_ids"] == []


def test_unobserved_case_creates_high_finding_and_blocks_pass():
    cases = [_case("NVIQ-A-001"), _case("NVIQ-B-001")]
    audit = run_audit(_manifest(), cases, [_observation("NVIQ-A-001")], [])
    assert audit["summary"]["overall_status"] == "action_required"
    assert audit["coverage"]["complete"] is False
    assert audit["coverage"]["tracks"]["lsr_cvf"]["missing_case_ids"] == ["NVIQ-B-001"]
    missing = [item for item in audit["findings"] if item["finding_type"] == "missing_observation"]
    assert len(missing) == 1
    assert missing[0]["severity"] == "High"
    assert missing[0]["case_id"] == "NVIQ-B-001"
    assert missing[0]["finding_id"] == "F-lsr_cvf-NVIQ-B-001-missing-observation"
    assert audit["summary"]["high_findings"] == 1


def test_no_observations_at_all_is_not_a_pass():
    audit = run_audit(_manifest(), [_case("NVIQ-A-001")], [], [])
    assert audit["summary"]["overall_status"] != "pass"
    assert audit["coverage"]["tracks"]["lsr_cvf"]["observed_case_count"] == 0


def test_snapshot_and_html_carry_coverage(tmp_path):
    cases = [_case("NVIQ-A-001"), _case("NVIQ-B-001")]
    audit = run_audit(_manifest(), cases, [_observation("NVIQ-A-001")], [])
    paths = write_audit_artifacts(audit, tmp_path)
    snapshot = json.loads(paths["snapshot"].read_text(encoding="utf-8"))
    assert snapshot["coverage"] == {"lsr_cvf": {"expected": 2, "observed": 1, "missing_case_ids": ["NVIQ-B-001"]}}
    assert "1 of 2" in render_html(audit)


def test_partial_executable_p0_run_is_not_a_pass():
    """Regression for audit probe P2: 5 of 8 evidence records previously reported pass."""
    cases = load_cases(ROOT / "cases/v0.2/executable-p0.json")
    evidence = json.loads((ROOT / "examples/evidence/p0-executable.json").read_text(encoding="utf-8"))[:5]
    manifest = json.loads((ROOT / "examples/audit/executable-p0-manifest.json").read_text(encoding="utf-8"))
    audit = run_audit(manifest, cases, derive_observations(cases, evidence), [])
    assert audit["summary"]["overall_status"] == "action_required"
    assert sorted(item["case_id"] for item in audit["findings"] if item["finding_type"] == "missing_observation") == [
        "NVIQ-CTX-001",
        "NVIQ-PRIOR-001",
        "NVIQ-TURN-001",
    ]
