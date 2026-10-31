import json
from math import exp

import pytest

from nviq.adapters.openai_realtime import adapt_openai_realtime_events, load_realtime_events
from nviq.execution.evaluators import derive_observation


def _case(family: str) -> dict:
    return {
        "case_id": "NVIQ-OPENAI-001",
        "family": family,
        "ground_truth": {
            "verbatim": None,
            "entity_candidates": [],
            "semantic_candidates": [],
            "message_presence_probability": 1.0,
            "allowed_ambiguity": False,
            "floor_state": None,
        },
        "expected_policy": {
            "action_mode": "observe_only",
            "must_preserve_alternatives": False,
        },
        "scoring": {"metrics": [], "catastrophic_failure_conditions": []},
    }


def test_load_realtime_events_accepts_jsonl(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(
        '\n'.join([
            json.dumps({"type": "input_audio_buffer.speech_started", "event_id": "ev-1", "item_id": "u-1", "audio_start_ms": 10}),
            json.dumps({"type": "input_audio_buffer.speech_stopped", "event_id": "ev-2", "item_id": "u-1", "audio_end_ms": 410}),
        ]) + "\n",
        encoding="utf-8",
    )
    events = load_realtime_events(path)
    assert [event["event_id"] for event in events] == ["ev-1", "ev-2"]


def test_adapter_keeps_asr_logprob_separate_from_authoritative_decision_confidence():
    case = _case("uncertainty_fidelity")
    case["ground_truth"]["allowed_ambiguity"] = True
    case["ground_truth"]["entity_candidates"] = [
        {"surface": "Miller", "resolved": "Miller", "confidence": 0.55},
        {"surface": "Millar", "resolved": "Millar", "confidence": 0.45},
    ]
    case["expected_policy"].update({"action_mode": "clarify", "must_preserve_alternatives": True})
    events = [
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "event_id": "ev-transcript",
            "item_id": "user-1",
            "transcript": "Miller or Millar",
            "logprobs": [
                {"token": "Miller", "logprob": -0.10536051565782628, "bytes": []},
                {"token": " Millar", "logprob": -0.2231435513142097, "bytes": []},
            ],
        },
        {
            "type": "nviq.evidence",
            "event_id": "nviq-1",
            "evidence": {"confidence": {"authoritative": 0.55, "expressed": 0.55, "action_mode": "clarify"}},
        },
    ]
    evidence = adapt_openai_realtime_events(case, events, track="audio_native", capture_origin="adapter_contract_fixture", model="gpt-realtime-2.1")
    expected_asr = exp((-0.10536051565782628 - 0.2231435513142097) / 2)
    assert evidence["message"]["lexical_output"] == "Miller or Millar"
    assert evidence["message"]["abstained"] is False
    assert evidence["confidence"]["authoritative"] == 0.55
    assert evidence["confidence"]["expressed"] == 0.55
    assert evidence["confidence"]["action_mode"] == "clarify"
    assert evidence["provenance"]["configuration"]["input_transcription_confidence"] == pytest.approx(expected_asr)
    assert evidence["alternatives"]["preserved"] == ["Millar", "Miller"]
    assert evidence["provenance"]["provider"] == "openai"
    assert evidence["provenance"]["model"] == "gpt-realtime-2.1"
    assert "ev-transcript" in evidence["provenance"]["evidence_refs"]


def test_runtime_alternatives_are_not_lost_when_transcript_contains_only_one_candidate():
    case = _case("uncertainty_fidelity")
    case["ground_truth"]["allowed_ambiguity"] = True
    case["ground_truth"]["entity_candidates"] = [
        {"surface": "Miller", "resolved": "Miller", "confidence": 0.55},
        {"surface": "Millar", "resolved": "Millar", "confidence": 0.45},
    ]
    case["expected_policy"].update({"action_mode": "clarify", "must_preserve_alternatives": True})
    events = [
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "event_id": "ev-transcript",
            "item_id": "user-1",
            "transcript": "Miller",
            "logprobs": [],
        },
        {
            "type": "nviq.evidence",
            "event_id": "nviq-1",
            "evidence": {
                "confidence": {"authoritative": 0.55, "expressed": 0.55, "action_mode": "clarify"},
                "alternatives": {"preserved": ["Miller", "Millar"]},
            },
        },
    ]
    evidence = adapt_openai_realtime_events(case, events, track="audio_native", capture_origin="adapter_contract_fixture")
    assert set(evidence["alternatives"]["preserved"]) == {"Miller", "Millar"}


def test_asr_logprobs_alone_do_not_satisfy_decision_confidence_evidence():
    case = _case("uncertainty_fidelity")
    case["ground_truth"]["allowed_ambiguity"] = True
    events = [{
        "type": "conversation.item.input_audio_transcription.completed",
        "event_id": "ev-transcript",
        "item_id": "user-1",
        "transcript": "Miller",
        "logprobs": [{"token": "Miller", "logprob": -0.05, "bytes": []}],
    }]
    evidence = adapt_openai_realtime_events(case, events, track="audio_native", capture_origin="adapter_contract_fixture")
    assert "confidence" not in evidence
    assert evidence["provenance"]["configuration"]["input_transcription_confidence"] > 0.9
    observation = derive_observation(case, evidence)
    assert observation["execution"]["status"] == "failed"
    assert "confidence" in observation["execution"]["failure_reason"]


def test_empty_completed_transcription_becomes_abstention_evidence():
    case = _case("abstention_fidelity")
    case["ground_truth"]["message_presence_probability"] = 0.0
    case["expected_policy"]["action_mode"] = "abstain"
    events = [{
        "type": "conversation.item.input_audio_transcription.completed",
        "event_id": "ev-empty",
        "item_id": "user-1",
        "transcript": "   ",
        "logprobs": [],
    }]
    evidence = adapt_openai_realtime_events(case, events, track="audio_native", capture_origin="adapter_contract_fixture")
    assert evidence["message"]["lexical_output"] is None
    assert evidence["message"]["abstained"] is True


def test_unsupported_turn_state_fails_closed_in_execution_engine():
    case = _case("turn_state_floor_state_cognition")
    case["ground_truth"]["floor_state"] = "listener_backchannel"
    events = [
        {"type": "input_audio_buffer.speech_started", "event_id": "ev-1", "item_id": "u-1", "audio_start_ms": 100},
        {"type": "input_audio_buffer.speech_stopped", "event_id": "ev-2", "item_id": "u-1", "audio_end_ms": 300},
        {"type": "conversation.item.input_audio_transcription.completed", "event_id": "ev-3", "item_id": "u-1", "transcript": "mm-hm", "logprobs": []},
    ]
    evidence = adapt_openai_realtime_events(case, events, track="audio_native", capture_origin="adapter_contract_fixture")
    assert "turn" not in evidence
    observation = derive_observation(case, evidence)
    assert observation["execution"]["status"] == "failed"
    assert "turn" in observation["execution"]["failure_reason"]


def test_adapter_keeps_playback_and_tool_events_as_trace_provenance():
    case = _case("abstention_fidelity")
    events = [
        {"type": "response.output_audio_transcript.done", "event_id": "ev-out", "item_id": "a-1", "response_id": "r-1", "transcript": "I have done that."},
        {"type": "conversation.item.truncated", "event_id": "ev-trunc", "item_id": "a-1", "content_index": 0, "audio_end_ms": 850},
        {"type": "response.function_call_arguments.done", "event_id": "ev-call", "item_id": "fc-1", "call_id": "call-1", "name": "send_message", "arguments": "{\"to\":\"Miller\"}"},
        {"type": "conversation.item.created", "event_id": "ev-tool", "item": {"id": "out-1", "type": "function_call_output", "call_id": "call-1", "output": "{\"status\":\"success\"}"}},
    ]
    evidence = adapt_openai_realtime_events(case, events, track="audio_native", capture_origin="adapter_contract_fixture")
    config = evidence["provenance"]["configuration"]
    assert config["assistant_transcripts"] == [{"item_id": "a-1", "response_id": "r-1", "transcript": "I have done that."}]
    assert config["truncations"] == [{"item_id": "a-1", "audio_end_ms": 850}]
    assert config["function_calls"][0]["name"] == "send_message"
    assert config["function_outputs"][0]["call_id"] == "call-1"
    assert "action" not in evidence
