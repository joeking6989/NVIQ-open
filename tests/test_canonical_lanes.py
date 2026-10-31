from pathlib import Path

from nviq.cases import load_cases, load_schema, validate_cases
from nviq.execution.async_integrity import evaluate_request_boundary
from nviq.execution.evidence import load_evidence, validate_evidence
from nviq.execution.runner import derive_observations


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_csc_lanes_validate_and_execute_through_nviq():
    case_path = ROOT / "cases/v0.2/csc-canonical-p0.json"
    evidence_path = ROOT / "examples/evidence/csc-canonical-p0.json"

    cases = load_cases(case_path)
    validate_cases(cases, load_schema(ROOT / "src/nviq/schemas/test-case.v0.2.schema.json"))
    evidence = load_evidence(evidence_path)
    validate_evidence(
        evidence,
        load_schema(ROOT / "src/nviq/schemas/evidence-bundle.v0.1.schema.json"),
        {case["case_id"] for case in cases},
    )

    results = {row["case_id"]: row for row in derive_observations(cases, evidence)}
    assert set(results) == {
        "NVIQ-CSC-FLOOR-001",
        "NVIQ-CSC-SILENCE-001",
        "NVIQ-CSC-ASYNC-001",
        "NVIQ-CSC-SPEAKER-001",
    }
    assert all(row["execution"]["status"] == "success" for row in results.values())
    assert all(not row["catastrophic_failures"] for row in results.values())
    assert results["NVIQ-CSC-FLOOR-001"]["metrics"]["conversational_floor_integrity"] == 1.0
    assert results["NVIQ-CSC-SILENCE-001"]["metrics"]["long_silence_continuity"] == 1.0
    assert results["NVIQ-CSC-ASYNC-001"]["metrics"]["request_boundary_evidence_freeze"] == 1.0
    assert results["NVIQ-CSC-ASYNC-001"]["metrics"]["result_delivery_provenance"] == 1.0
    assert results["NVIQ-CSC-SPEAKER-001"]["metrics"]["speaker_state_preservation"] == 1.0


def test_result_delivery_provenance_accepts_exactly_one_accept_or_reject_transition():
    base = {
        "kind": "async_task",
        "authorized_time_ms": 1000,
        "evidence_times_at_authorization": [200, 800],
        "later_evidence_retroactively_added": False,
        "prepared_time_ms": 1600,
        "returned_time_ms": 1700,
        "committed_time_ms": 1800,
        "spoken_time_ms": 1900,
    }

    accepted = {**base, "accepted_time_ms": 1750, "rejected_time_ms": None}
    rejected = {**base, "accepted_time_ms": None, "rejected_time_ms": 1750}
    contradictory = {**base, "accepted_time_ms": 1740, "rejected_time_ms": 1750}

    assert evaluate_request_boundary([accepted])["result_delivery_provenance"] == 1.0
    assert evaluate_request_boundary([rejected])["result_delivery_provenance"] == 1.0
    assert evaluate_request_boundary([contradictory])["result_delivery_provenance"] == 0.0
