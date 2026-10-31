from types import SimpleNamespace

from nviq.adapters.realtime_venus import adapt_realtime_venus_trace_manifest
from nviq.adapters.realtime_venus_capture import RealtimeVenusRuntimeCapture
from nviq.execution.async_integrity import evaluate_request_boundary


def _case(case_id="NVIQ-VENUS-ASYNC-001"):
    return {
        "case_id": case_id,
        "family": "asynchronous_cognitive_continuity_integrity",
    }


def test_runtime_capture_maps_context_snapshot_and_result_lifecycle(tmp_path):
    capture = RealtimeVenusRuntimeCapture(
        case_id="NVIQ-VENUS-ASYNC-001",
        session_id="session-1",
        source_commit="e53ae8d5bde92b30364b26f2e4c13c9db7a8ffea",
        audio_ref="runtime://session-1",
    )
    snapshot = SimpleNamespace(
        session_id="session-1",
        snapshot_id="snapshot-7",
        cutoff_ms=1000,
        cutoff_sequence=8,
    )
    capture.record_context_snapshot(
        snapshot,
        work_id="work-1",
        evidence_times_at_authorization=[200, 800, 1000],
    )
    capture.mark_async_transition(work_id="work-1", transition="prepared", at_ms=1600)
    capture.mark_async_transition(work_id="work-1", transition="returned", at_ms=1700)
    capture.mark_async_transition(work_id="work-1", transition="accepted", at_ms=1750)
    capture.mark_async_transition(work_id="work-1", transition="committed", at_ms=1800)
    capture.mark_async_transition(work_id="work-1", transition="spoken", at_ms=1900)

    path = capture.write_manifest(tmp_path / "capture.json")
    records = adapt_realtime_venus_trace_manifest([_case()], path)

    assert len(records) == 1
    record = records[0]
    task = record["async_tasks"][0]
    assert task["authorized_time_ms"] == 1000.0
    assert task["evidence_times_at_authorization"] == [200.0, 800.0, 1000.0]
    assert task["prepared_time_ms"] == 1600.0
    assert task["returned_time_ms"] == 1700.0
    assert task["accepted_time_ms"] == 1750.0
    assert task["committed_time_ms"] == 1800.0
    assert task["spoken_time_ms"] == 1900.0
    assert evaluate_request_boundary(record["async_tasks"]) == {
        "request_boundary_evidence_freeze": 1.0,
        "async_future_contamination_rate": 0.0,
        "result_delivery_provenance": 1.0,
    }
    config = record["provenance"]["configuration"]
    assert config["capture_origin"] == "runtime"
    assert config["source_commit"] == "e53ae8d5bde92b30364b26f2e4c13c9db7a8ffea"
    frozen = next(
        event
        for event in config["harness_events"]
        if event["event_type"] == "request_boundary_frozen"
    )
    assert frozen["details"]["cutoff_sequence"] == 8
    assert frozen["details"]["snapshot_id"] == "snapshot-7"


def test_capture_preserves_contamination_instead_of_sanitizing_it(tmp_path):
    capture = RealtimeVenusRuntimeCapture(
        case_id="NVIQ-VENUS-ASYNC-001",
        session_id="session-1",
        source_commit="upstream-sha",
    )
    capture.begin_async_task(
        work_id="work-1",
        authorized_time_ms=1000,
        evidence_times_at_authorization=[200, 1400],
        later_evidence_retroactively_added=True,
    )
    capture.mark_async_transition(work_id="work-1", transition="prepared", at_ms=1600)
    capture.mark_async_transition(work_id="work-1", transition="returned", at_ms=1700)
    capture.mark_async_transition(work_id="work-1", transition="accepted", at_ms=1750)
    capture.mark_async_transition(work_id="work-1", transition="rejected", at_ms=1760)
    capture.mark_async_transition(work_id="work-1", transition="committed", at_ms=1800)
    capture.mark_async_transition(work_id="work-1", transition="spoken", at_ms=1900)

    path = capture.write_manifest(tmp_path / "contaminated.json")
    record = adapt_realtime_venus_trace_manifest([_case()], path)[0]
    result = evaluate_request_boundary(record["async_tasks"])
    assert result["request_boundary_evidence_freeze"] == 0.0
    assert result["async_future_contamination_rate"] == 1.0
    assert result["result_delivery_provenance"] == 0.0


def test_capture_records_native_chunks_without_promoting_floor_semantics(tmp_path):
    capture = RealtimeVenusRuntimeCapture(
        case_id="NVIQ-VENUS-FLOOR-001",
        session_id="session-floor",
        source_commit="upstream-sha",
    )
    capture.record_duplex_chunk(
        at_ms=1000,
        chunk_index=1,
        is_listen=True,
        text="",
    )
    path = capture.write_manifest(tmp_path / "native.json")
    record = adapt_realtime_venus_trace_manifest(
        [_case("NVIQ-VENUS-FLOOR-001")],
        path,
    )[0]
    assert "floor_events" not in record
    assert record["provenance"]["configuration"]["native_duplex_chunks"][0]["is_listen"] is True


def test_capture_records_causal_events_for_aefr(tmp_path):
    capture = RealtimeVenusRuntimeCapture(
        case_id="NVIQ-VENUS-AEFR-001",
        session_id="session-aefr",
        source_commit="upstream-sha",
    )
    capture.record_causal_event({
        "event_id": "ghost",
        "kind": "acoustic_evidence",
        "event_time_ms": 300,
        "append_sequence": 0,
        "evidence_available_time_ms": 300,
        "fabricated": True,
        "provenance_refs": ["runtime:audio:ghost"],
    })
    path = capture.write_manifest(tmp_path / "aefr.json")
    record = adapt_realtime_venus_trace_manifest(
        [_case("NVIQ-VENUS-AEFR-001")],
        path,
    )[0]
    assert record["ledger"]["events"][0]["fabricated"] is True
    assert record["ledger"]["case_id"] == "NVIQ-VENUS-AEFR-001"


def test_snapshot_session_mismatch_fails_closed():
    capture = RealtimeVenusRuntimeCapture(
        case_id="NVIQ-VENUS-ASYNC-001",
        session_id="session-1",
        source_commit="upstream-sha",
    )
    snapshot = SimpleNamespace(
        session_id="wrong-session",
        snapshot_id="snapshot",
        cutoff_ms=1000,
        cutoff_sequence=1,
    )
    try:
        capture.record_context_snapshot(
            snapshot,
            work_id="work",
            evidence_times_at_authorization=[1000],
        )
    except ValueError as error:
        assert "session_id does not match" in str(error)
    else:
        raise AssertionError("expected mismatched runtime session to fail closed")
