"""Run the Space's public entrypoints against NVIQ's own checked-in fixtures."""
from pathlib import Path

import pytest

from nviq.cases import load_cases
from nviq.observations import load_observations
from nviq.runner import run_benchmark
from nviq.space_service import audit_files, score_files


ROOT = Path(__file__).resolve().parents[1]


def test_space_score_calls_existing_scorer(tmp_path):
    cases = ROOT / "cases/v0.2/starter.json"
    observations = ROOT / "examples/observations/starter-observations.json"
    result = score_files(cases, observations, tmp_path)
    expected = run_benchmark(
        load_cases(cases),
        load_observations(observations, {case["case_id"] for case in load_cases(cases)}),
    )
    assert result["report"] == expected
    assert result["paths"]["json"].exists()
    assert result["summary"]["observation_count"] > 0


def test_space_audit_uses_real_evidence_pipeline(tmp_path):
    result = audit_files(
        ROOT / "cases/v0.2/executable-p0.json",
        ROOT / "examples/evidence/p0-executable.json",
        ROOT / "examples/audit/executable-p0-manifest.json",
        tmp_path,
    )
    assert result["report"]["audit_version"] == "0.1"
    assert result["summary"]["evidence_records"] > 0
    assert result["summary"]["derived_observations"] > 0
    assert result["paths"]["json"].exists()
    assert result["paths"]["html"].exists()
    assert result["paths"]["snapshot"].exists()


def test_space_rejects_incompatible_evidence_tracks(tmp_path):
    import json

    manifest = json.loads(
        (ROOT / "examples/audit/executable-p0-manifest.json").read_text(encoding="utf-8")
    )
    manifest["tracks"] = ["transcript_only"]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="tracks not enabled"):
        audit_files(
            ROOT / "cases/v0.2/executable-p0.json",
            ROOT / "examples/evidence/p0-executable.json",
            manifest_path,
            tmp_path,
        )


def test_space_rejects_empty_observations(tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="observations list is empty"):
        score_files(ROOT / "cases/v0.2/starter.json", empty, tmp_path)
