import json
from copy import deepcopy
from pathlib import Path

from nviq.execution.runner import derive_observations
from nviq.runner import run_benchmark

ROOT = Path(__file__).resolve().parents[1]
P0 = {
    "uncertainty_fidelity",
    "abstention_fidelity",
    "state_speech_consistency",
    "shared_state_integrity",
    "prior_contamination_resistance",
    "turn_state_floor_state_cognition",
    "confidence_channel_fidelity",
}


def _fixtures():
    cases = json.loads((ROOT / "cases/v0.2/executable-p0.json").read_text(encoding="utf-8"))
    evidence = json.loads((ROOT / "examples/evidence/p0-executable.json").read_text(encoding="utf-8"))
    return cases, evidence


def test_executable_suite_covers_every_p0_family_and_context_transform():
    cases, _ = _fixtures()
    families = {case["family"] for case in cases}
    assert P0 <= families
    assert "context_transformation_integrity" in families


def test_raw_evidence_derives_one_observation_per_case_without_catastrophic_failures():
    cases, evidence = _fixtures()
    rows = derive_observations(cases, evidence)
    assert len(rows) == len(cases) == 8
    assert all(not row["catastrophic_failures"] for row in rows)
    assert {row["case_id"] for row in rows} == {case["case_id"] for case in cases}


def test_failure_injection_is_caught_across_all_executable_families():
    cases, clean = _fixtures()
    corrupted = deepcopy(clean)
    by_id = {row["case_id"]: row for row in corrupted}

    by_id["NVIQ-CONF-001"]["confidence"]["expressed"] = 1.0

    by_id["NVIQ-UNC-001"]["confidence"]["authoritative"] = 0.95
    by_id["NVIQ-UNC-001"]["confidence"]["expressed"] = 0.95
    by_id["NVIQ-UNC-001"]["confidence"]["action_mode"] = "act"

    by_id["NVIQ-ABSTAIN-001"]["message"]["lexical_output"] = "invented speech"
    by_id["NVIQ-ABSTAIN-001"]["message"]["abstained"] = False

    by_id["NVIQ-STATE-001"]["action"]["spoken_claim"] = "success"

    by_id["NVIQ-SHARED-001"]["shared_state"]["used_context_ids"].append("msg-unheard")

    by_id["NVIQ-PRIOR-001"]["prior"]["contextual_resolved"] = {"neutral": 0.05, "angry": 0.95}
    by_id["NVIQ-PRIOR-001"]["prior"]["promoted_as_current_observation"] = True

    by_id["NVIQ-TURN-001"]["turn"]["predicted_floor_state"] = "holds_floor"

    by_id["NVIQ-CTX-001"]["context_retrieval"]["decisive_evidence_recovered"] = False
    by_id["NVIQ-CTX-001"]["context_retrieval"]["provenance_preserved"] = False

    observations = derive_observations(cases, corrupted)
    benchmark = run_benchmark(cases, observations)
    track = benchmark["tracks"]["lsr_cvf"]

    assert track["case_count"] == 8
    assert track["hard_gate_failures"] == 8
    assert track["catastrophic_failures"] == 8
    assert all(row["catastrophic_failures"] for row in observations)
