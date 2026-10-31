import json
from pathlib import Path

import pytest

from nviq.adapters.realtime_venus import (
    adapt_realtime_venus_events,
    adapt_realtime_venus_trace_manifest,
)
from nviq.cases import load_cases, load_schema, validate_cases
from nviq.cli import main
from nviq.execution.evidence import validate_evidence


ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = ROOT / "cases/v0.2/realtime-venus-adapter-p0.json"
TRACE_PATH = ROOT / "examples/realtime-venus/adapter-contract-trace-manifest.json"


def _cases():
    cases = load_cases(CASE_PATH)
    validate_cases(cases, load_schema(ROOT / "src/nviq/schemas/test-case.v0.2.schema.json"))
    return cases


def test_adapter_contract_manifest_maps_all_priority_lanes():
    cases = _cases()
    records = adapt_realtime_venus_trace_manifest(cases, TRACE_PATH)
    by_case = {record["case_id"]: record for record in records}

    assert len(records) == 5
    assert by_case["NVIQ-VENUS-FLOOR-001"]["floor_events"][1] == {
        "class": "backchannel",
        "yielded_floor": False,
    }
    assert by_case["NVIQ-VENUS-SILENCE-001"]["silence_events"][0]["state_preserved"] is True
    assert by_case["NVIQ-VENUS-ASYNC-001"]["async_tasks"][0]["authorized_time_ms"] == 1000
    assert by_case["NVIQ-VENUS-SPEAKER-001"]["speaker_state_events"][1]["speaker_id"] == "B"
    assert by_case["NVIQ-VENUS-AEFR-001"]["ledger"]["events"][0]["fabricated"] is True
    assert all(record["provenance"]["provider"] == "inclusionAI" for record in records)
    assert all(
        record["provenance"]["configuration"]["source_commit"]
        == "e53ae8d5bde92b30364b26f2e4c13c9db7a8ffea"
        for record in records
    )
    assert all(
        record["provenance"]["configuration"]["capture_origin"]
        == "adapter_contract_fixture"
        for record in records
    )

    validate_evidence(
        records,
        load_schema(ROOT / "src/nviq/schemas/evidence-bundle.v0.1.schema.json"),
        {case["case_id"] for case in cases},
        load_schema(ROOT / "src/nviq/schemas/causal-speech-ledger.v0.1.schema.json"),
    )


def test_native_listen_state_is_not_promoted_to_floor_semantics():
    case = next(case for case in _cases() if case["case_id"] == "NVIQ-VENUS-FLOOR-001")
    record = adapt_realtime_venus_events(
        case,
        [
            {
                "type": "venus.duplex_chunk",
                "event_id": "native-1",
                "at_ms": 1000,
                "chunk_index": 1,
                "is_listen": True,
                "text": "",
            }
        ],
        capture_origin="adapter_contract_fixture",
    )
    assert "floor_events" not in record
    assert record["provenance"]["configuration"]["native_duplex_chunks"][0]["is_listen"] is True


def test_provider_trace_cannot_inject_nviq_scores():
    case = next(case for case in _cases() if case["case_id"] == "NVIQ-VENUS-FLOOR-001")
    with pytest.raises(ValueError, match="may not inject NVIQ scoring"):
        adapt_realtime_venus_events(
            case,
            [
                {
                    "type": "nviq.floor",
                    "event_id": "bad",
                    "class": "backchannel",
                    "yielded_floor": False,
                    "score": 1.0,
                }
            ],
        )


def test_realtime_venus_cli_ingest_and_execute_adapter_fixture(tmp_path, capsys):
    output = tmp_path / "venus-evidence.json"
    audit_dir = tmp_path / "venus-audit"

    code = main([
        "ingest",
        "realtime-venus",
        "--cases", str(CASE_PATH),
        "--trace-manifest", str(TRACE_PATH),
        "--output", str(output),
    ])
    assert code == 0
    assert "Realtime-Venus adapter v0.1" in capsys.readouterr().out

    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert len(evidence) == 5

    code = main([
        "execute",
        "--manifest", str(ROOT / "examples/audit/realtime-venus-adapter-p0-manifest.json"),
        "--evidence", str(output),
        "--output-dir", str(audit_dir),
    ])
    assert code == 0

    report = json.loads((audit_dir / "audit-report.json").read_text(encoding="utf-8"))
    derived = json.loads((audit_dir / "derived-observations.json").read_text(encoding="utf-8"))
    track = report["benchmark"]["tracks"]["audio_native"]

    assert track["case_count"] == 5
    assert report["summary"]["overall_status"] == "critical"
    by_case = {row["case_id"]: row for row in derived}
    assert by_case["NVIQ-VENUS-FLOOR-001"]["metrics"]["conversational_floor_integrity"] == 1.0
    assert by_case["NVIQ-VENUS-ASYNC-001"]["metrics"]["request_boundary_evidence_freeze"] == 1.0
    assert by_case["NVIQ-VENUS-SPEAKER-001"]["metrics"]["speaker_state_preservation"] == 1.0
    assert "fabricated_acoustic_evidence" in by_case["NVIQ-VENUS-AEFR-001"]["catastrophic_failures"]


def test_capture_origin_is_required_and_never_defaulted_to_runtime():
    case = next(case for case in _cases() if case["case_id"] == "NVIQ-VENUS-FLOOR-001")
    events = [{"type": "venus.duplex_chunk", "event_id": "native-1", "at_ms": 1000, "chunk_index": 1, "is_listen": True, "text": ""}]
    with pytest.raises(ValueError, match="capture_origin is required"):
        adapt_realtime_venus_events(case, events)
