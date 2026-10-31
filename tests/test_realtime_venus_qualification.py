import copy
import json
from pathlib import Path

from nviq.adapters.realtime_venus import adapt_realtime_venus_trace_manifest
from nviq.cases import load_cases
from nviq.cli import main
from nviq.realtime_venus_qualification import qualify_realtime_venus_runtime


ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = ROOT / "cases/v0.2/realtime-venus-adapter-p0.json"
TRACE_PATH = ROOT / "examples/realtime-venus/adapter-contract-trace-manifest.json"
RUNTIME_MANIFEST = ROOT / "examples/audit/realtime-venus-runtime-p0-manifest.json"
PINNED_COMMIT = "e53ae8d5bde92b30364b26f2e4c13c9db7a8ffea"


def _cases():
    return load_cases(CASE_PATH)


def _adapter_records():
    return adapt_realtime_venus_trace_manifest(_cases(), TRACE_PATH)


def _clean_runtime_records():
    records = copy.deepcopy(_adapter_records())
    for record in records:
        config = record["provenance"]["configuration"]
        config["capture_origin"] = "runtime"
        config["source_commit"] = PINNED_COMMIT
    aefr = next(
        record
        for record in records
        if record["case_id"] == "NVIQ-VENUS-AEFR-001"
    )
    aefr["ledger"]["events"][0]["fabricated"] = False
    return records


def _execute(tmp_path: Path, evidence: list[dict]):
    evidence_path = tmp_path / "evidence.json"
    output_dir = tmp_path / "execution"
    evidence_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    code = main([
        "execute",
        "--manifest", str(RUNTIME_MANIFEST),
        "--evidence", str(evidence_path),
        "--output-dir", str(output_dir),
    ])
    assert code == 0
    return evidence_path, output_dir


def test_runtime_qualification_gate_issues_receipt_only_for_clean_runtime_bundle(tmp_path, capsys):
    evidence_path, output_dir = _execute(tmp_path, _clean_runtime_records())
    capsys.readouterr()
    receipt_path = tmp_path / "receipt.json"

    code = main([
        "qualify",
        "realtime-venus",
        "--cases", str(CASE_PATH),
        "--evidence", str(evidence_path),
        "--execution-dir", str(output_dir),
        "--output", str(receipt_path),
    ])
    assert code == 0
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["qualified"] is True
    assert receipt["status"] == "qualified"
    assert receipt["reasons"] == []
    assert receipt["source_commit"] == PINNED_COMMIT
    assert receipt["capture_origin_required"] == "runtime"
    assert len(receipt["qualification_bundle_sha256"]) == 64
    assert "status=qualified" in capsys.readouterr().out


def test_adapter_fixture_is_rejected_as_runtime_proof(tmp_path):
    evidence_path, output_dir = _execute(tmp_path, _adapter_records())
    receipt_path = tmp_path / "rejected-receipt.json"

    code = main([
        "qualify",
        "realtime-venus",
        "--cases", str(CASE_PATH),
        "--evidence", str(evidence_path),
        "--execution-dir", str(output_dir),
        "--output", str(receipt_path),
    ])
    assert code == 2
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["qualified"] is False
    assert receipt["status"] == "rejected"
    assert any("capture_origin must be runtime" in reason for reason in receipt["reasons"])
    assert any("audit overall_status must be pass" in reason for reason in receipt["reasons"])


def test_pinned_source_commit_mismatch_is_rejected(tmp_path):
    records = _clean_runtime_records()
    records[0]["provenance"]["configuration"]["source_commit"] = "wrong-sha"
    evidence_path, output_dir = _execute(tmp_path, records)

    code = main([
        "qualify",
        "realtime-venus",
        "--cases", str(CASE_PATH),
        "--evidence", str(evidence_path),
        "--execution-dir", str(output_dir),
        "--output", str(tmp_path / "receipt.json"),
    ])
    assert code == 2
    receipt = json.loads((tmp_path / "receipt.json").read_text(encoding="utf-8"))
    assert any("source commit must equal pinned" in reason for reason in receipt["reasons"])


def test_receipt_fingerprint_is_deterministic(tmp_path):
    evidence = _clean_runtime_records()
    evidence_path, output_dir = _execute(tmp_path, evidence)
    observations = json.loads(
        (output_dir / "derived-observations.json").read_text(encoding="utf-8")
    )
    report = json.loads((output_dir / "audit-report.json").read_text(encoding="utf-8"))
    cases = _cases()

    first = qualify_realtime_venus_runtime(cases, evidence, observations, report)
    second = qualify_realtime_venus_runtime(cases, evidence, observations, report)
    assert first["qualification_bundle_sha256"] == second["qualification_bundle_sha256"]
    assert first["qualified"] is True
