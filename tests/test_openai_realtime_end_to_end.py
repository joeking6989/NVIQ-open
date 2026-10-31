import json
from pathlib import Path

from nviq.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_openai_realtime_eight_case_trace_runs_through_reliability_audit(tmp_path):
    evidence_path = tmp_path / "openai-realtime-evidence.json"
    audit_dir = tmp_path / "audit"

    ingest_code = main([
        "ingest",
        "openai-realtime",
        "--cases", str(ROOT / "cases/v0.2/executable-p0.json"),
        "--trace-manifest", str(ROOT / "examples/openai-realtime/p0-trace-manifest.json"),
        "--output", str(evidence_path),
    ])
    assert ingest_code == 0

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert len(evidence) == 8
    assert {row["case_id"] for row in evidence} == {
        "NVIQ-CONF-001",
        "NVIQ-UNC-001",
        "NVIQ-ABSTAIN-001",
        "NVIQ-STATE-001",
        "NVIQ-SHARED-001",
        "NVIQ-PRIOR-001",
        "NVIQ-TURN-001",
        "NVIQ-CTX-001",
    }
    assert all(row["track"] == "audio_native" for row in evidence)
    assert all(row["provenance"]["provider"] == "openai" for row in evidence)

    execute_code = main([
        "execute",
        "--manifest", str(ROOT / "examples/audit/openai-realtime-p0-manifest.json"),
        "--evidence", str(evidence_path),
        "--output-dir", str(audit_dir),
    ])
    assert execute_code == 0

    report = json.loads((audit_dir / "audit-report.json").read_text(encoding="utf-8"))
    track = report["benchmark"]["tracks"]["audio_native"]
    assert track["case_count"] == 8
    assert track["hard_gate_failures"] == 0
    assert track["catastrophic_failures"] == 0
    assert track["mean_score"] == 1.0
    assert report["summary"]["overall_status"] == "pass"
    assert (audit_dir / "derived-observations.json").exists()
    assert (audit_dir / "evidence-summary.json").exists()
    assert (audit_dir / "audit-report.html").exists()
    assert (audit_dir / "regression-snapshot.json").exists()
