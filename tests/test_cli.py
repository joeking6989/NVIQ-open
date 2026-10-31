import json
from pathlib import Path

from nviq.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_validate_command_returns_zero_for_starter_cases(capsys):
    code = main([
        "validate",
        "--schema", str(ROOT / "src/nviq/schemas/test-case.v0.2.schema.json"),
        "--cases", str(ROOT / "cases/v0.2/starter.json"),
    ])
    assert code == 0
    assert "validated 3 cases" in capsys.readouterr().out


def test_score_command_writes_report(tmp_path, capsys):
    observations = tmp_path / "obs.json"
    observations.write_text(json.dumps([
        {"case_id": "NVIQ-CONF-001", "track": "lsr_cvf", "metrics": {"confidence_inflation_error": 0.01, "clarification_policy_accuracy": 1.0, "alternative_preservation": 1.0}, "catastrophic_failures": []}
    ]), encoding="utf-8")
    output = tmp_path / "report.json"
    code = main([
        "score",
        "--schema", str(ROOT / "src/nviq/schemas/test-case.v0.2.schema.json"),
        "--cases", str(ROOT / "cases/v0.2/starter.json"),
        "--observations", str(observations),
        "--output", str(output),
    ])
    assert code == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["tracks"]["lsr_cvf"]["case_count"] == 1
    assert len(report["missing_observations"]) == 2
    assert "scored 1 observations" in capsys.readouterr().out
