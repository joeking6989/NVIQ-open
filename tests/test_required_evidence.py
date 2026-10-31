import json
from pathlib import Path

import pytest

from nviq.audit.runner import run_audit
from nviq.cases import load_cases
from nviq.execution.canonical_lanes import run_canonical_lane_case
from nviq.execution.evaluators import REQUIRED_EVIDENCE_FIELDS, derive_observation
from nviq.execution.runner import derive_observations

ROOT = Path(__file__).resolve().parents[1]


def _p0():
    cases = load_cases(ROOT / "cases/v0.2/executable-p0.json")
    evidence = json.loads((ROOT / "examples/evidence/p0-executable.json").read_text(encoding="utf-8"))
    return {case["case_id"]: case for case in cases}, evidence


def _skeleton(record):
    return {
        "evidence_version": "0.1",
        "case_id": record["case_id"],
        "track": record["track"],
        "provenance": {"evidence_refs": ["probe"]},
    }


def test_every_p0_family_has_a_required_fact_contract():
    cases, _ = _p0()
    assert {case["family"] for case in cases.values()} <= set(REQUIRED_EVIDENCE_FIELDS)


@pytest.mark.parametrize("index", range(8))
def test_empty_required_sections_fail_closed(index):
    """Regression for audit probe P1: empty sections used to score 1.0 in three families."""
    cases, evidence = _p0()
    record = evidence[index]
    case = cases[record["case_id"]]
    empty = _skeleton(record)
    for section in REQUIRED_EVIDENCE_FIELDS[case["family"]]:
        empty[section] = {}
    result = derive_observation(case, empty)
    assert result["execution"]["status"] == "failed"
    assert result["metrics"] == {}
    assert result["catastrophic_failures"] == []
    assert "missing required evidence" in result["execution"]["failure_reason"]


@pytest.mark.parametrize("index", range(8))
def test_dropping_any_single_required_field_fails_closed(index):
    cases, evidence = _p0()
    record = evidence[index]
    case = cases[record["case_id"]]
    for section, fields in REQUIRED_EVIDENCE_FIELDS[case["family"]].items():
        for field in fields:
            mutated = json.loads(json.dumps(record))
            del mutated[section][field]
            result = derive_observation(case, mutated)
            assert result["execution"]["status"] == "failed", (section, field)
            assert f"{section}.{field}" in result["execution"]["failure_reason"]


def test_complete_fixture_evidence_still_scores():
    cases, evidence = _p0()
    rows = derive_observations(list(cases.values()), evidence)
    assert all(row["execution"]["status"] == "success" for row in rows)


def test_empty_section_audit_cannot_pass_any_case():
    cases, evidence = _p0()
    probe = []
    for record in evidence:
        row = _skeleton(record)
        for section in REQUIRED_EVIDENCE_FIELDS[cases[record["case_id"]]["family"]]:
            row[section] = {}
        probe.append(row)
    manifest = json.loads((ROOT / "examples/audit/executable-p0-manifest.json").read_text(encoding="utf-8"))
    audit = run_audit(manifest, list(cases.values()), derive_observations(list(cases.values()), probe), [])
    track = audit["benchmark"]["tracks"]["lsr_cvf"]
    assert audit["summary"]["overall_status"] != "pass"
    assert track["hard_gate_failures"] == 8
    assert all(not case["hard_gate_pass"] for case in track["cases"])


_LANES = {
    "conversational_floor_integrity": "floor_events",
    "long_silence_continuity": "silence_events",
    "asynchronous_cognitive_continuity_integrity": "async_tasks",
    "speaker_state_preservation": "speaker_state_events",
}


@pytest.mark.parametrize("family,section", sorted(_LANES.items()))
@pytest.mark.parametrize("events", [[], [{"note": "unrelated"}]])
def test_canonical_lanes_fail_closed_without_scorable_events(family, section, events):
    case = {"case_id": "NVIQ-LANE-001", "family": family, "scoring": {"metrics": [], "catastrophic_failure_conditions": []}}
    evidence = {"evidence_version": "0.1", "case_id": "NVIQ-LANE-001", "track": "audio_native", section: events, "provenance": {"evidence_refs": ["probe"]}}
    result = run_canonical_lane_case(case, evidence)
    assert result["execution"]["status"] == "failed"
    assert result["metrics"] == {}
    assert "insufficient evidence" in result["execution"]["failure_reason"]
