"""Release Guard regressions for audit probes P3, P4 and P5 (NVIQ audit, 18 Oct 2026)."""

import copy
import json
from pathlib import Path

from nviq.audit.compare import compare_audits
from nviq.audit.runner import run_audit
from nviq.cases import load_cases
from nviq.execution.runner import derive_observations

ROOT = Path(__file__).resolve().parents[1]


def _inputs():
    cases = load_cases(ROOT / "cases/v0.2/executable-p0.json")
    evidence = {row["case_id"]: row for row in json.loads((ROOT / "examples/evidence/p0-executable.json").read_text(encoding="utf-8"))}
    manifest = json.loads((ROOT / "examples/audit/executable-p0-manifest.json").read_text(encoding="utf-8"))
    return cases, evidence, manifest


def _audit(evidence_rows, audit_id="audit", manifest=None):
    cases, _, base_manifest = _inputs()
    manifest = copy.deepcopy(manifest or base_manifest)
    manifest["audit_id"] = audit_id
    return run_audit(manifest, cases, derive_observations(cases, evidence_rows), [])


def _baseline():
    """All 8 cases evaluated; CONF and UNC fail clarification policy and TURN mislabels the floor (hard gates)."""
    _, evidence, _ = _inputs()
    rows = copy.deepcopy(list(evidence.values()))
    for row in rows:
        if row["case_id"] in {"NVIQ-CONF-001", "NVIQ-UNC-001"}:
            row["confidence"]["action_mode"] = "act"
        if row["case_id"] == "NVIQ-TURN-001":
            row["turn"]["predicted_floor_state"] = "unknown_state"
    return _audit(rows, "baseline")


def test_identical_audits_show_no_material_change():
    base = _baseline()
    result = compare_audits(base, base)
    assert result["recommendation"] == "no_material_change"
    assert result["comparable"] is True


def test_dropping_failing_cases_cannot_make_a_candidate_better():
    """P3: a candidate that only reports its passing cases previously won."""
    _, evidence, _ = _inputs()
    kept = [copy.deepcopy(evidence[key]) for key in ("NVIQ-PRIOR-001", "NVIQ-SHARED-001", "NVIQ-STATE-001")]
    result = compare_audits(_baseline(), _audit(kept, "candidate"))
    assert result["recommendation"] == "candidate_coverage_reduced"
    assert result["coverage"]["common_case_count"] == 3
    assert len(result["coverage"]["lost_cases"]) == 5
    assert result["gates_fixed"] == []
    assert result["overall_score_delta"] == 0.0


def test_new_hard_gate_failure_blocks_candidate_even_when_mean_rises():
    """P4: fixing two cases while breaking another used to return candidate_better."""
    _, evidence, _ = _inputs()
    rows = copy.deepcopy(list(evidence.values()))
    for row in rows:
        if row["case_id"] == "NVIQ-STATE-001":
            row["action"] = {"requested": True, "execution_status": "success", "spoken_claim": "uncertain"}
    result = compare_audits(_baseline(), _audit(rows, "candidate"))
    assert result["candidate_score"] > result["baseline_score"]
    assert result["recommendation"] == "candidate_regressed_hard_gate"
    assert result["gates_newly_failed"] == ["F-lsr_cvf-NVIQ-STATE-001-metric-state_speech_consistency"]


def test_new_catastrophic_failure_still_rejected():
    """P5: unchanged behaviour, kept as a guard."""
    _, evidence, _ = _inputs()
    rows = copy.deepcopy(list(evidence.values()))
    for row in rows:
        if row["case_id"] == "NVIQ-SHARED-001":
            row["shared_state"] = {"used_context_ids": ["a", "b"], "playback_grounded_ids": ["a"]}
    result = compare_audits(_baseline(), _audit(rows, "candidate"))
    assert result["recommendation"] == "candidate_rejected_new_catastrophic_failure"


def test_clean_improvement_is_still_recommended():
    _, evidence, _ = _inputs()
    result = compare_audits(_baseline(), _audit(copy.deepcopy(list(evidence.values())), "candidate"))
    assert result["recommendation"] == "candidate_better"
    assert sorted(result["gates_fixed"]) == [
        "F-lsr_cvf-NVIQ-CONF-001-metric-clarification_policy_accuracy",
        "F-lsr_cvf-NVIQ-TURN-001-metric-floor_state_accuracy",
        "F-lsr_cvf-NVIQ-UNC-001-metric-clarification_policy_accuracy",
    ]


def test_different_benchmark_versions_are_not_comparable():
    _, evidence, manifest = _inputs()
    other = copy.deepcopy(manifest)
    other["benchmark_version"] = "0.3"
    result = compare_audits(_baseline(), _audit(copy.deepcopy(list(evidence.values())), "candidate", other))
    assert result["recommendation"] == "not_comparable"
    assert result["comparable"] is False
    assert "benchmark_version" in result["comparability_issues"][0]


def test_different_case_sets_are_not_comparable():
    base = _baseline()
    cand = copy.deepcopy(base)
    cand["coverage"]["expected_case_ids"] = cand["coverage"]["expected_case_ids"][:-1]
    result = compare_audits(base, cand)
    assert result["recommendation"] == "not_comparable"
