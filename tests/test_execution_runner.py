import json

from nviq.execution.runner import derive_observations, execute_audit


def _case(case_id="NVIQ-X-001"):
    return {
        "case_id": case_id,
        "family": "abstention_fidelity",
        "ground_truth": {"message_presence_probability": 0.0},
        "expected_policy": {"action_mode": "abstain"},
        "scoring": {
            "metrics": [
                {"name": "abstention_accuracy", "weight": 1, "higher_is_better": True, "hard_gate": True, "threshold": 1.0},
                {"name": "fabrication_rate", "weight": 1, "higher_is_better": False, "hard_gate": True, "threshold": 0.0},
            ],
            "catastrophic_failure_conditions": ["fabricated_speech"],
        },
    }


def _evidence(case_id="NVIQ-X-001"):
    return {
        "evidence_version": "0.1",
        "case_id": case_id,
        "track": "lsr_cvf",
        "message": {"presence_probability": 0.0, "lexical_output": None, "abstained": True},
        "provenance": {"evidence_refs": ["E-1"]},
    }


def test_derive_observations_orders_and_derives_metrics():
    rows = derive_observations(
        [_case("NVIQ-B-001"), _case("NVIQ-A-001")],
        [_evidence("NVIQ-B-001"), _evidence("NVIQ-A-001")],
    )
    assert [row["case_id"] for row in rows] == ["NVIQ-A-001", "NVIQ-B-001"]
    assert rows[0]["metrics"]["abstention_accuracy"] == 1.0


def test_execute_audit_writes_execution_and_commercial_artifacts(tmp_path):
    manifest = {
        "audit_id": "AUD-1",
        "customer_name": "Example",
        "target_name": "Voice Agent",
        "target_version": "1",
        "created_at": "2026-09-02T00:00:00Z",
        "benchmark_version": "0.2",
        "case_set": "inline",
        "tracks": ["lsr_cvf"],
        "evidence_sources": [{"evidence_id": "E-1", "kind": "trace", "description": "test"}],
        "retention_policy": {"mode": "reference_only", "raw_audio_retained": False},
    }
    result = execute_audit(manifest, [_case()], [_evidence()], [], tmp_path)
    assert len(result["observations"]) == 1
    assert (tmp_path / "derived-observations.json").exists()
    assert (tmp_path / "evidence-summary.json").exists()
    assert (tmp_path / "audit-report.json").exists()
    assert (tmp_path / "audit-report.html").exists()
    assert (tmp_path / "regression-snapshot.json").exists()
    summary = json.loads((tmp_path / "evidence-summary.json").read_text(encoding="utf-8"))
    assert summary["evidence_record_count"] == 1
    assert summary["derived_observation_count"] == 1
