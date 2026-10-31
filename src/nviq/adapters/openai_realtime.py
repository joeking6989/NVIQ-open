from __future__ import annotations

import json
from collections import Counter
from math import exp, fsum
from pathlib import Path
from typing import Any

from nviq.execution.evaluators import REQUIRED_EVIDENCE_FIELDS

from .provenance import require_capture_origin


_ALLOWED_SIDECAR_SECTIONS = {
    "message",
    "confidence",
    "alternatives",
    "action",
    "shared_state",
    "prior",
    "context_retrieval",
    "turn",
}

_REQUIRED_FIELDS_BY_FAMILY = REQUIRED_EVIDENCE_FIELDS


def load_realtime_events(path: Path) -> list[dict]:
    """Load captured Realtime events from a JSON array or JSONL file."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError(f"Realtime event JSON must contain an array: {path}")
        events = data
    else:
        events = [json.loads(line) for line in text.splitlines() if line.strip()]
    if any(not isinstance(event, dict) for event in events):
        raise ValueError(f"Realtime events must be JSON objects: {path}")
    return events


def _merge_dict(target: dict, incoming: dict) -> dict:
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge_dict(target[key], value)
        else:
            target[key] = value
    return target


def _merge_sidecar_evidence(target: dict, sidecar: dict) -> dict:
    """Add runtime-only facts without overwriting facts directly observed in provider events."""
    for section, value in sidecar.items():
        if section == "alternatives" and isinstance(value, dict):
            target_section = target.setdefault("alternatives", {})
            incoming = value.get("preserved")
            existing = target_section.get("preserved")
            if isinstance(incoming, list):
                merged = set(str(item) for item in incoming)
                if isinstance(existing, list):
                    merged.update(str(item) for item in existing)
                target_section["preserved"] = sorted(merged)
            for key, nested_value in value.items():
                if key != "preserved" and key not in target_section:
                    target_section[key] = nested_value
            continue

        if not isinstance(value, dict):
            target.setdefault(section, value)
            continue
        target_section = target.setdefault(section, {})
        if not isinstance(target_section, dict):
            continue
        for key, nested_value in value.items():
            target_section.setdefault(key, nested_value)
    return target


def _event_ref(event: dict, index: int) -> str:
    event_id = event.get("event_id")
    if event_id:
        return str(event_id)
    return f"openai-event:{index}:{event.get('type', 'unknown')}"


def _asr_confidence(logprobs: Any) -> float | None:
    if not isinstance(logprobs, list):
        return None
    values = []
    for item in logprobs:
        if isinstance(item, dict) and item.get("logprob") is not None:
            values.append(float(item["logprob"]))
    if not values:
        return None
    return round(max(0.0, min(1.0, exp(fsum(values) / len(values)))), 6)


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _annotated_alternatives(case: dict) -> list[str]:
    values: set[str] = set()
    for item in case.get("ground_truth", {}).get("entity_candidates", []):
        surface = item.get("surface")
        resolved = item.get("resolved")
        if surface:
            values.add(str(surface))
        elif resolved:
            values.add(str(resolved))
    return sorted(values)


def _sidecar_evidence(events: list[dict]) -> dict:
    result: dict = {}
    for event in events:
        if event.get("type") != "nviq.evidence":
            continue
        payload = event.get("evidence")
        if not isinstance(payload, dict):
            raise ValueError("nviq.evidence event requires an evidence object")
        unknown = set(payload) - _ALLOWED_SIDECAR_SECTIONS
        if unknown:
            raise ValueError("unsupported nviq.evidence section(s): " + ", ".join(sorted(unknown)))
        _merge_dict(result, payload)
    return result


def _latest_transcription(events: list[dict]) -> dict | None:
    matches = [
        event
        for event in events
        if event.get("type") == "conversation.item.input_audio_transcription.completed"
    ]
    return matches[-1] if matches else None


def _standard_evidence(case: dict, events: list[dict]) -> dict:
    result: dict = {}
    transcription = _latest_transcription(events)
    if transcription is not None:
        transcript = str(transcription.get("transcript") or "")
        stripped = transcript.strip()
        message = {
            "lexical_output": stripped or None,
            "abstained": not bool(stripped),
        }
        verbatim = case.get("ground_truth", {}).get("verbatim")
        if isinstance(verbatim, str):
            message["correct"] = _normalize(stripped) == _normalize(verbatim)
        result["message"] = message

        if stripped:
            normalized_transcript = _normalize(stripped)
            preserved = [
                value
                for value in _annotated_alternatives(case)
                if _normalize(value) in normalized_transcript
            ]
            if preserved:
                result["alternatives"] = {"preserved": sorted(preserved)}
    return result


def _speech_intervals(events: list[dict]) -> list[dict]:
    starts: dict[str, int] = {}
    intervals = []
    for event in events:
        event_type = event.get("type")
        item_id = event.get("item_id")
        if not item_id:
            continue
        if event_type == "input_audio_buffer.speech_started" and event.get("audio_start_ms") is not None:
            starts[str(item_id)] = int(event["audio_start_ms"])
        elif event_type == "input_audio_buffer.speech_stopped" and event.get("audio_end_ms") is not None:
            start_ms = starts.get(str(item_id))
            end_ms = int(event["audio_end_ms"])
            row = {"item_id": str(item_id), "end_ms": end_ms}
            if start_ms is not None:
                row["start_ms"] = start_ms
                row["duration_ms"] = max(0, end_ms - start_ms)
            intervals.append(row)
    return intervals


def _trace_configuration(events: list[dict]) -> dict:
    event_types = Counter(str(event.get("type", "unknown")) for event in events)
    assistant_transcripts = []
    truncations = []
    function_calls = []
    function_outputs = []
    response_statuses = []
    session_model = None
    session_id = None

    for event in events:
        event_type = event.get("type")
        if event_type in {"response.output_audio_transcript.done", "response.output_text.done"}:
            text = event.get("transcript") if event_type == "response.output_audio_transcript.done" else event.get("text")
            assistant_transcripts.append({
                "item_id": event.get("item_id"),
                "response_id": event.get("response_id"),
                "transcript": str(text or ""),
            })
        elif event_type == "conversation.item.truncated":
            truncations.append({
                "item_id": event.get("item_id"),
                "audio_end_ms": event.get("audio_end_ms"),
            })
        elif event_type == "response.function_call_arguments.done":
            function_calls.append({
                "item_id": event.get("item_id"),
                "call_id": event.get("call_id"),
                "name": event.get("name"),
                "arguments": event.get("arguments"),
            })
        elif event_type == "conversation.item.created":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "function_call_output":
                function_outputs.append({
                    "item_id": item.get("id"),
                    "call_id": item.get("call_id"),
                    "output": item.get("output"),
                })
        elif event_type == "response.done":
            response = event.get("response")
            if isinstance(response, dict):
                response_statuses.append({
                    "response_id": response.get("id"),
                    "status": response.get("status"),
                })
        elif event_type in {"session.created", "session.updated"}:
            session = event.get("session")
            if isinstance(session, dict):
                session_model = session.get("model") or session_model
                session_id = session.get("id") or session_id

    transcription = _latest_transcription(events)
    input_transcription_confidence = (
        _asr_confidence(transcription.get("logprobs")) if transcription is not None else None
    )
    return {
        "event_count": len(events),
        "event_types": dict(sorted(event_types.items())),
        "speech_intervals": _speech_intervals(events),
        "assistant_transcripts": assistant_transcripts,
        "truncations": truncations,
        "function_calls": function_calls,
        "function_outputs": function_outputs,
        "response_statuses": response_statuses,
        "input_transcription_confidence": input_transcription_confidence,
        "session_model": session_model,
        "session_id": session_id,
    }


def _fail_closed_for_family(case: dict, evidence: dict) -> None:
    requirements = _REQUIRED_FIELDS_BY_FAMILY.get(case.get("family"), {})
    for section, required_fields in requirements.items():
        value = evidence.get(section)
        if not isinstance(value, dict) or not required_fields.issubset(value):
            evidence.pop(section, None)


def adapt_openai_realtime_events(
    case: dict,
    events: list[dict],
    *,
    track: str,
    model: str | None = None,
    session_id: str | None = None,
    audio_ref: str | None = None,
    capture_origin: str | None = None,
) -> dict:
    """Convert one captured OpenAI Realtime case trace into an NVIQ Evidence Bundle record.

    OpenAI transcription logprobs are preserved as ASR evidence in provenance; they are not
    promoted into NVIQ authoritative decision confidence. Optional ``nviq.evidence`` sidecar
    events may provide additional machine-readable runtime facts, but cannot assign benchmark
    scores. Provider-observed fields remain authoritative when sidecar data conflicts. Where a
    family cannot be proven from the trace, the relevant section is omitted so the Execution
    Engine fails closed on missing evidence.
    """
    if not isinstance(case, dict) or not case.get("case_id"):
        raise ValueError("case requires case_id")
    capture_origin = require_capture_origin(capture_origin, "OpenAI Realtime capture")
    if any(not isinstance(event, dict) for event in events):
        raise ValueError("Realtime events must be objects")

    standard = _standard_evidence(case, events)
    sidecar = _sidecar_evidence(events)
    evidence = {"evidence_version": "0.1", "case_id": case["case_id"], "track": track}
    _merge_dict(evidence, standard)
    _merge_sidecar_evidence(evidence, sidecar)

    config = _trace_configuration(events)
    config["capture_origin"] = capture_origin
    effective_model = model or config.pop("session_model", None)
    effective_session_id = session_id or config.pop("session_id", None)
    refs = sorted({_event_ref(event, index) for index, event in enumerate(events)})
    provenance = {
        "evidence_refs": refs,
        "provider": "openai",
        "model": effective_model,
        "session_id": effective_session_id,
        "audio_ref": audio_ref,
        "configuration": config,
    }
    evidence["provenance"] = provenance
    _fail_closed_for_family(case, evidence)
    return evidence


def adapt_openai_realtime_trace_manifest(cases: list[dict], manifest_path: Path) -> list[dict]:
    """Convert a versioned multi-case OpenAI Realtime trace manifest into evidence records."""
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Realtime trace manifest must contain a JSON object")
    if data.get("trace_version") != "0.1":
        raise ValueError("Realtime trace manifest trace_version must be 0.1")
    sessions = data.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise ValueError("Realtime trace manifest requires a non-empty sessions array")

    cases_by_id = {case["case_id"]: case for case in cases}
    default_track = str(data.get("default_track") or "audio_native")
    capture_origin = require_capture_origin(data.get("capture_origin"), "OpenAI Realtime trace manifest")
    records = []
    seen: set[tuple[str, str]] = set()
    for index, session in enumerate(sessions):
        if not isinstance(session, dict):
            raise ValueError(f"Realtime trace manifest session {index} must be an object")
        case_id = session.get("case_id")
        if case_id not in cases_by_id:
            raise ValueError(f"unknown case_id: {case_id}")
        track = str(session.get("track") or default_track)
        key = (str(case_id), track)
        if key in seen:
            raise ValueError(f"duplicate Realtime trace for {case_id} on {track}")
        seen.add(key)

        has_inline = "events" in session
        has_path = "events_path" in session
        if has_inline == has_path:
            raise ValueError(f"{case_id}: provide exactly one of events or events_path")
        if has_inline:
            events = session["events"]
            if not isinstance(events, list) or any(not isinstance(event, dict) for event in events):
                raise ValueError(f"{case_id}: events must be an array of objects")
        else:
            events_path = manifest_path.parent / str(session["events_path"])
            events = load_realtime_events(events_path)

        records.append(adapt_openai_realtime_events(
            cases_by_id[str(case_id)],
            events,
            track=track,
            model=session.get("model"),
            session_id=session.get("session_id"),
            audio_ref=session.get("audio_ref"),
            capture_origin=session.get("capture_origin") or capture_origin,
        ))
    return records
