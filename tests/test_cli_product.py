"""Developer-facing CLI behaviour: bundled resources, exit codes, --version, errors."""

import json
from pathlib import Path

import pytest

from nviq import __version__
from nviq.cli import EXIT_ERROR, EXIT_GATE_FAILED, EXIT_OK, main, run
from nviq.resources import (
    AUDIT_MANIFEST_SCHEMA,
    CAUSAL_LEDGER_SCHEMA,
    EVIDENCE_BUNDLE_SCHEMA,
    REMEDIATION_REGISTRY,
    TEST_CASE_SCHEMA,
)

ROOT = Path(__file__).resolve().parents[1]


def test_bundled_resources_exist_inside_the_package():
    for path in (AUDIT_MANIFEST_SCHEMA, CAUSAL_LEDGER_SCHEMA, EVIDENCE_BUNDLE_SCHEMA, REMEDIATION_REGISTRY, TEST_CASE_SCHEMA):
        assert path.is_file(), path
        assert "src/nviq/" in path.as_posix() or "site-packages/nviq/" in path.as_posix()


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"nviq {__version__}"


def test_commands_run_from_any_directory_with_bundled_defaults(tmp_path, monkeypatch):
    """Regression for audit probe P7: defaults were relative to the repository root."""
    monkeypatch.chdir(tmp_path)
    assert main(["validate", "--cases", str(ROOT / "cases/v0.2/starter.json")]) == EXIT_OK
    code = main([
        "execute",
        "--manifest", str(ROOT / "examples/audit/executable-p0-manifest.json"),
        "--evidence", str(ROOT / "examples/evidence/p0-executable.json"),
        "--output-dir", str(tmp_path / "out"),
    ])
    assert code == EXIT_OK
    report = json.loads((tmp_path / "out/audit-report.json").read_text(encoding="utf-8"))
    assert report["summary"]["overall_status"] == "pass"


def _execute_csc(tmp_path, *extra):
    return main([
        "execute",
        "--manifest", str(ROOT / "examples/audit/csc-ledger-p0-manifest.json"),
        "--evidence", str(ROOT / "examples/evidence/csc-ledger-p0.json"),
        "--output-dir", str(tmp_path / "csc"),
        *extra,
    ])


def test_critical_audit_exits_zero_without_gate(tmp_path):
    assert _execute_csc(tmp_path) == EXIT_OK


def test_fail_on_critical_gates_a_critical_audit(tmp_path, capsys):
    """Regression for audit probe P6: a critical audit exited 0 and could not gate CI."""
    assert _execute_csc(tmp_path, "--fail-on", "critical") == EXIT_GATE_FAILED
    assert "gate failed" in capsys.readouterr().err


def test_fail_on_does_not_trip_on_a_clean_audit(tmp_path):
    code = main([
        "execute",
        "--manifest", str(ROOT / "examples/audit/executable-p0-manifest.json"),
        "--evidence", str(ROOT / "examples/evidence/p0-executable.json"),
        "--output-dir", str(tmp_path / "clean"),
        "--fail-on", "medium",
    ])
    assert code == EXIT_OK


def test_audit_run_supports_fail_on(tmp_path):
    code = main([
        "audit", "run",
        "--manifest", str(ROOT / "examples/audit/starter-manifest.json"),
        "--observations", str(ROOT / "examples/observations/starter-observations.json"),
        "--output-dir", str(tmp_path / "starter"),
        "--fail-on", "low",
    ])
    report = json.loads((tmp_path / "starter/audit-report.json").read_text(encoding="utf-8"))
    assert code == (EXIT_GATE_FAILED if report["findings"] else EXIT_OK)


def test_errors_are_one_line_not_tracebacks(tmp_path, capsys):
    """Regression for audit probe P8."""
    bad = tmp_path / "bad.json"
    bad.write_text('{"a": 1}', encoding="utf-8")
    code = run(["evidence", "validate", "--evidence", str(bad)])
    err = capsys.readouterr().err
    assert code == EXIT_ERROR
    assert err.startswith("nviq: error: evidence file must contain a JSON array")
    assert "Traceback" not in err
    assert len(err.strip().splitlines()) == 1


def test_missing_file_is_a_clean_error(tmp_path, capsys):
    code = run(["validate", "--cases", str(tmp_path / "nope.json")])
    assert code == EXIT_ERROR
    assert "nviq: error:" in capsys.readouterr().err
