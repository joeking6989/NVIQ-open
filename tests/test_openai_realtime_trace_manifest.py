import json

import pytest

from nviq.adapters.openai_realtime import adapt_openai_realtime_trace_manifest


def _case(case_id: str, family: str) -> dict:
    return {
        "case_id": case_id,
        "family": family,
        "ground_truth": {
            "verbatim": None,
            "entity_candidates": [],
            "semantic_candidates": [],
            "message_presence_probability": 1.0,
            "allowed_ambiguity": False,
            "floor_state": None,
        },
        "expected_policy": {"action_mode": "observe_only", "must_preserve_alternatives": False},
        "scoring": {"metrics": [], "catastrophic_failure_conditions": []},
    }


def test_trace_manifest_adapts_inline_and_file_backed_sessions(tmp_path):
    trace = tmp_path / "uncertainty.jsonl"
    trace.write_text(
        "\n".join([
            json.dumps({
                "type": "conversation.item.input_audio_transcription.completed",
                "event_id": "ev-u",
                "item_id": "user-u",
                "transcript": "Miller or Millar",
                "logprobs": [{"token": "Miller", "logprob": -0.1, "bytes": []}],
            }),
            json.dumps({
                "type": "nviq.evidence",
                "event_id": "nviq-u",
                "evidence": {"confidence": {"authoritative": 0.55, "expressed": 0.6, "action_mode": "clarify"}},
            }),
        ]) + "\n",
        encoding="utf-8",
    )

    manifest = tmp_path / "trace-manifest.json"
    manifest.write_text(json.dumps({
        "trace_version": "0.1",
        "capture_origin": "adapter_contract_fixture",
        "default_track": "audio_native",
        "sessions": [
            {
                "case_id": "NVIQ-ABSTAIN-001",
                "events": [{
                    "type": "conversation.item.input_audio_transcription.completed",
                    "event_id": "ev-a",
                    "item_id": "user-a",
                    "transcript": "",
                    "logprobs": [],
                }],
            },
            {
                "case_id": "NVIQ-UNC-001",
                "events_path": "uncertainty.jsonl",
                "model": "gpt-realtime-2.1",
            },
        ],
    }), encoding="utf-8")

    cases = [
        _case("NVIQ-ABSTAIN-001", "abstention_fidelity"),
        _case("NVIQ-UNC-001", "uncertainty_fidelity"),
    ]
    cases[0]["ground_truth"]["message_presence_probability"] = 0.0
    cases[0]["expected_policy"]["action_mode"] = "abstain"
    cases[1]["ground_truth"]["allowed_ambiguity"] = True
    cases[1]["ground_truth"]["entity_candidates"] = [
        {"surface": "Miller", "resolved": "Miller", "confidence": 0.55},
        {"surface": "Millar", "resolved": "Millar", "confidence": 0.45},
    ]
    cases[1]["expected_policy"].update({"action_mode": "clarify", "must_preserve_alternatives": True})

    evidence = adapt_openai_realtime_trace_manifest(cases, manifest)
    assert [row["case_id"] for row in evidence] == ["NVIQ-ABSTAIN-001", "NVIQ-UNC-001"]
    assert evidence[0]["message"]["abstained"] is True
    assert evidence[1]["provenance"]["model"] == "gpt-realtime-2.1"
    assert evidence[1]["confidence"]["authoritative"] == 0.55
    assert evidence[1]["confidence"]["action_mode"] == "clarify"
    assert evidence[1]["provenance"]["configuration"]["input_transcription_confidence"] > 0.9


def test_trace_manifest_rejects_unknown_case(tmp_path):
    manifest = tmp_path / "trace-manifest.json"
    manifest.write_text(json.dumps({
        "trace_version": "0.1",
        "capture_origin": "adapter_contract_fixture",
        "sessions": [{"case_id": "NVIQ-NOT-HERE", "track": "audio_native", "events": []}],
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown case_id"):
        adapt_openai_realtime_trace_manifest([_case("NVIQ-ABSTAIN-001", "abstention_fidelity")], manifest)


def test_trace_manifest_requires_capture_origin(tmp_path):
    import json as _json

    import pytest as _pytest

    from nviq.adapters.openai_realtime import adapt_openai_realtime_trace_manifest

    manifest = tmp_path / "manifest.json"
    manifest.write_text(_json.dumps({"trace_version": "0.1", "sessions": [{"case_id": "X", "events": []}]}), encoding="utf-8")
    with _pytest.raises(ValueError, match="capture_origin is required"):
        adapt_openai_realtime_trace_manifest([{"case_id": "X"}], manifest)


def test_bundled_openai_trace_is_labelled_as_a_fixture():
    import json as _json
    from pathlib import Path as _Path

    root = _Path(__file__).resolve().parents[1]
    data = _json.loads((root / "examples/openai-realtime/p0-trace-manifest.json").read_text(encoding="utf-8"))
    assert data["capture_origin"] == "adapter_contract_fixture"
