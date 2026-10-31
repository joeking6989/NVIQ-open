import json
from pathlib import Path

from nviq.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_evidence_validate_command_accepts_reference_bundle(capsys):
    code = main([
        "evidence",
        "validate",
        "--evidence", str(ROOT / "examples/evidence/p0-executable.json"),
        "--cases", str(ROOT / "cases/v0.2/executable-p0.json"),
    ])
    assert code == 0
    assert "validated 8 evidence records" in capsys.readouterr().out


def test_execute_command_derives_observations_and_writes_audit(tmp_path, capsys):
    code = main([
        "execute",
        "--manifest", str(ROOT / "examples/audit/executable-p0-manifest.json"),
        "--evidence", str(ROOT / "examples/evidence/p0-executable.json"),
        "--output-dir", str(tmp_path),
    ])
    assert code == 0
    assert (tmp_path / "derived-observations.json").exists()
    assert (tmp_path / "evidence-summary.json").exists()
    assert (tmp_path / "audit-report.json").exists()
    report = json.loads((tmp_path / "audit-report.json").read_text(encoding="utf-8"))
    assert report["audit_version"] == "0.1"
    assert report["benchmark"]["tracks"]["lsr_cvf"]["case_count"] == 8
    assert "derived=8" in capsys.readouterr().out


def test_causal_ledger_execute_runs_end_to_end_and_exposes_diagnostics(tmp_path, capsys):
    evidence_path = ROOT / "examples/evidence/csc-ledger-p0.json"
    case_path = ROOT / "cases/v0.2/csc-ledger-p0.json"

    code = main([
        "evidence",
        "validate",
        "--evidence", str(evidence_path),
        "--cases", str(case_path),
    ])
    assert code == 0
    assert "validated 4 evidence records" in capsys.readouterr().out

    code = main([
        "execute",
        "--manifest", str(ROOT / "examples/audit/csc-ledger-p0-manifest.json"),
        "--evidence", str(evidence_path),
        "--output-dir", str(tmp_path),
    ])
    assert code == 0

    report = json.loads((tmp_path / "audit-report.json").read_text(encoding="utf-8"))
    derived = json.loads((tmp_path / "derived-observations.json").read_text(encoding="utf-8"))
    track = report["benchmark"]["tracks"]["lsr_cvf"]

    assert track["case_count"] == 4
    assert track["hard_gate_failures"] == 3
    assert track["catastrophic_failures"] == 3
    assert report["summary"]["overall_status"] == "critical"

    by_case = {row["case_id"]: row for row in derived}
    premature = by_case["NVIQ-CSC-LEDGER-PREMATURE-001"]["trace"]
    assert premature["belief_event_id"] == "uncertain"
    assert premature["belief_time_ms"] == 500.0
    assert premature["decision_event_id"] == "commit"
    assert premature["decision_time_ms"] == 650.0

    fabricated = by_case["NVIQ-CSC-LEDGER-AEFR-001"]["trace"]
    assert fabricated["belief_event_id"] == "wrong-belief"
    assert fabricated["decision_event_id"] == "commit"
    assert "derived=4" in capsys.readouterr().out
