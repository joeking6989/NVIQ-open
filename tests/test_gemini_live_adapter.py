import json
from pathlib import Path

import pytest

from nviq.adapters.gemini_live import (
    adapt_gemini_live_events,
    adapt_gemini_live_trace_manifest,
    load_gemini_live_events,
)
from nviq.adapters.gemini_live_capture import GeminiLiveRuntimeCapture
from nviq.cases import load_cases, load_schema, validate_cases
from nviq.cli import main
from nviq.execution.evidence import validate_evidence
from nviq.frontier_targets import FRONTIER_TARGETS


ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = ROOT / "cases/v0.2/gemini-live-adapter-p0.json"
TRACE_PATH = ROOT / "examples/gemini-live/adapter-contract-trace-manifest.json"


def _cases():
    cases = load_cases(CASE_PATH)
    validate_cases(cases, load_schema(ROOT / "src/nviq/schemas/test-case.v0.2.schema.json"))
    return cases


def test_load_gemini_live_events_accepts_jsonl(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(
        "\n".join([
            json.dumps({"type": "gemini.server_content", "event_id": "g-1", "interrupted": True}),
            json.dumps({"type": "gemini.client_realtime_input", "event_id": "g-2", "kind": "audio"}),
        ]) + "\n",
        encoding="utf-8",
    )
    events = load_gemini_live_events(path)
    assert [event["event_id"] for event in events] == ["g-1", "g-2"]


def test_adapter_contract_manifest_maps_all_gemini_priority_lanes():
    cases = _cases()
    records = adapt_gemini_live_trace_manifest(cases, TRACE_PATH)
    by_case = {record["case_id"]: record for record in records}

    assert len(records) == 2
    assert by_case["NVIQ-GEMINI-FLOOR-001"]["floor_events"][1] == {
        "class": "backchannel",
        "yielded_floor": False,
    }
    assert by_case["NVIQ-GEMINI-ASYNC-001"]["async_tasks"][0]["authorized_time_ms"] == 1000
    assert all(record["provenance"]["provider"] == "google" for record in records)
    assert all(record["provenance"]["model"] == "gemini-3.8-live" for record in records)
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


def test_native_interrupted_signal_is_not_promoted_to_floor_semantics():
    case = next(case for case in _cases() if case["case_id"] == "NVIQ-GEMINI-FLOOR-001")
    record = adapt_gemini_live_events(
        case,
        [{
            "type": "gemini.server_content",
            "event_id": "native-1",
            "at_ms": 1000,
            "interrupted": True,
            "turn_complete": True,
        }],
        session_id="session-1",
        capture_origin="adapter_contract_fixture",
    )
    assert "floor_events" not in record
    assert record["provenance"]["configuration"]["native_server_content"][0]["interrupted"] is True


def test_provider_trace_cannot_inject_nviq_scores():
    case = next(case for case in _cases() if case["case_id"] == "NVIQ-GEMINI-FLOOR-001")
    with pytest.raises(ValueError, match="may not inject NVIQ scoring"):
        adapt_gemini_live_events(
            case,
            [{
                "type": "nviq.floor",
                "event_id": "bad",
                "class": "backchannel",
                "yielded_floor": False,
                "score": 1.0,
            }],
        )


def test_runtime_capture_preserves_server_tool_input_and_async_lifecycle(tmp_path):
    capture = GeminiLiveRuntimeCapture(
        case_id="NVIQ-GEMINI-ASYNC-001",
        session_id="live-session",
        model="gemini-3.8-live",
    )
    capture.record_client_realtime_input(
        at_ms=900,
        kind="audio",
        mime_type="audio/pcm;rate=16000",
        byte_length=640,
    )
    capture.record_server_message(
        {
            "server_content": {
                "interrupted": True,
                "turn_complete": False,
                "input_transcription": {"text": "book it"},
                "output_transcription": {"text": "I can do that"},
            },
            "tool_call": {
                "function_calls": [{
                    "id": "work-1",
                    "name": "lookup_schedule",
                    "args": {"day": "Monday"},
                }]
            },
        },
        at_ms=1000,
    )
    capture.begin_async_task(
        work_id="work-1",
        authorized_time_ms=1000,
        evidence_times_at_authorization=[200, 800, 1000],
    )
    for transition, at_ms in [
        ("prepared", 1600),
        ("returned", 1700),
        ("accepted", 1750),
        ("committed", 1800),
        ("spoken", 1900),
    ]:
        capture.mark_async_transition(
            work_id="work-1",
            transition=transition,
            at_ms=at_ms,
        )
    capture.record_tool_response(
        work_id="work-1",
        at_ms=1700,
        response={"status": "ok"},
    )

    output = capture.write_manifest(tmp_path / "runtime.json")
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["capture_origin"] == "runtime"
    types = [event["type"] for event in manifest["sessions"][0]["events"]]
    assert "gemini.client_realtime_input" in types
    assert "gemini.server_content" in types
    assert "gemini.tool_call" in types
    assert "gemini.tool_response" in types
    assert "nviq.async_task" in types


def test_runtime_capture_marks_retroactive_evidence():
    capture = GeminiLiveRuntimeCapture(
        case_id="NVIQ-GEMINI-ASYNC-001",
        session_id="live-session",
    )
    capture.begin_async_task(
        work_id="work-1",
        authorized_time_ms=1000,
        evidence_times_at_authorization=[1000],
    )
    capture.mark_retroactive_evidence(work_id="work-1")
    event = capture.flush_async_task("work-1")
    assert event["later_evidence_retroactively_added"] is True


def test_gemini_live_cli_ingest_and_execute_adapter_fixture(tmp_path, capsys):
    output = tmp_path / "gemini-live-evidence.json"
    audit_dir = tmp_path / "gemini-live-audit"

    code = main([
        "ingest",
        "gemini-live",
        "--cases", str(CASE_PATH),
        "--trace-manifest", str(TRACE_PATH),
        "--output", str(output),
    ])
    assert code == 0
    assert "Gemini Live adapter v0.1" in capsys.readouterr().out

    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert len(evidence) == 2

    code = main([
        "execute",
        "--manifest", str(ROOT / "examples/audit/gemini-live-adapter-p0-manifest.json"),
        "--evidence", str(output),
        "--output-dir", str(audit_dir),
    ])
    assert code == 0

    report = json.loads((audit_dir / "audit-report.json").read_text(encoding="utf-8"))
    derived = json.loads((audit_dir / "derived-observations.json").read_text(encoding="utf-8"))
    track = report["benchmark"]["tracks"]["audio_native"]
    by_case = {row["case_id"]: row for row in derived}

    assert track["case_count"] == 2
    assert track["hard_gate_failures"] == 0
    assert track["catastrophic_failures"] == 0
    assert by_case["NVIQ-GEMINI-FLOOR-001"]["metrics"]["conversational_floor_integrity"] == 1.0
    assert by_case["NVIQ-GEMINI-ASYNC-001"]["metrics"]["request_boundary_evidence_freeze"] == 1.0
    assert by_case["NVIQ-GEMINI-ASYNC-001"]["metrics"]["async_future_contamination_rate"] == 0.0
    assert by_case["NVIQ-GEMINI-ASYNC-001"]["metrics"]["result_delivery_provenance"] == 1.0


def test_frontier_target_tracks_partial_authenticated_runtime_state():
    target = FRONTIER_TARGETS["gemini-live"]
    assert target["status"] == "runtime_partial_qualified_floor_failed"
    assert target["model"] == "gemini-3.8-live"
    assert target["runtime_lanes"]["async_tool_provenance"]["status"] == "qualified"
    assert target["runtime_lanes"]["conversational_floor_integrity"]["status"] == "failed"


def test_capture_origin_is_required_and_never_defaulted_to_runtime():
    case = next(case for case in _cases() if case["case_id"] == "NVIQ-GEMINI-FLOOR-001")
    events = [{"type": "gemini.server_content", "event_id": "native-1", "at_ms": 1000, "interrupted": True}]
    with pytest.raises(ValueError, match="capture_origin is required"):
        adapt_gemini_live_events(case, events)
