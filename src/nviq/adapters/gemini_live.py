from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .provenance import require_capture_origin


TRACE_VERSION = "0.1"
CAPTURE_CONTRACT = "nviq-gemini-live-v0.1"
DEFAULT_MODEL = "gemini-3.8-live"
SOURCE_PRODUCT = "Gemini Live API"

_FORBIDDEN_SOURCE_FIELDS = {
    "metrics",
    "score",
    "scores",
    "passed",
    "verdict",
    "catastrophic_failures",
    "hard_gate_failures",
    "nviq_score",
}

_SUPPORTED_EVENT_TYPES = {
    "gemini.server_content",
    "gemini.client_content",
    "gemini.client_realtime_input",
    "gemini.tool_call",
    "gemini.tool_response",
    "nviq.floor",
    "nviq.async_task",
}

_ASYNC_FIELDS = (
    "kind",
    "authorized_time_ms",
    "evidence_times_at_authorization",
    "later_evidence_retroactively_added",
    "prepared_time_ms",
    "returned_time_ms",
    "accepted_time_ms",
    "rejected_time_ms",
    "committed_time_ms",
    "spoken_time_ms",
)


def load_gemini_live_events(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError(f"Gemini Live event JSON must contain an array: {path}")
        events = data
    else:
        events = [json.loads(line) for line in text.splitlines() if line.strip()]
    if any(not isinstance(event, dict) for event in events):
        raise ValueError(f"Gemini Live events must be JSON objects: {path}")
    return events


def _reject_source_scoring(value: Any, *, path: str = "trace") -> None:
    if isinstance(value, dict):
        forbidden = _FORBIDDEN_SOURCE_FIELDS & set(value)
        if forbidden:
            raise ValueError(
                f"{path}: source trace may not inject NVIQ scoring field(s): "
                + ", ".join(sorted(forbidden))
            )
        for key, nested in value.items():
            _reject_source_scoring(nested, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_source_scoring(nested, path=f"{path}[{index}]")


def _event_ref(event: dict, index: int) -> str:
    raw = event.get("event_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return f"gemini-live-event:{index}:{event.get('type', 'unknown')}"


def _require_event_type(event: dict, index: int) -> str:
    event_type = event.get("type")
    if event_type not in _SUPPORTED_EVENT_TYPES:
        raise ValueError(f"Gemini Live event {index} has unsupported type: {event_type!r}")
    return str(event_type)


def _floor_event(event: dict) -> dict:
    interaction_class = event.get("class")
    if interaction_class not in {
        "genuine_interruption",
        "backchannel",
        "other_directed_speech",
        "background_speech",
    }:
        raise ValueError(f"nviq.floor has unsupported class: {interaction_class!r}")
    if not isinstance(event.get("yielded_floor"), bool):
        raise ValueError("nviq.floor requires boolean yielded_floor")
    return {"class": interaction_class, "yielded_floor": event["yielded_floor"]}


def _async_event(event: dict) -> dict:
    required = {
        "authorized_time_ms",
        "evidence_times_at_authorization",
        "later_evidence_retroactively_added",
    }
    missing = required - set(event)
    if missing:
        raise ValueError("nviq.async_task missing field(s): " + ", ".join(sorted(missing)))
    if not isinstance(event["evidence_times_at_authorization"], list):
        raise ValueError("nviq.async_task evidence_times_at_authorization must be an array")
    if not isinstance(event["later_evidence_retroactively_added"], bool):
        raise ValueError("nviq.async_task later_evidence_retroactively_added must be boolean")
    result = {key: event.get(key) for key in _ASYNC_FIELDS if key in event}
    result["kind"] = "async_task"
    return result


def adapt_gemini_live_events(
    case: dict,
    events: list[dict],
    *,
    track: str = "audio_native",
    model: str | None = None,
    session_id: str | None = None,
    audio_ref: str | None = None,
    capture_origin: str | None = None,
) -> dict:
    """Convert a captured Gemini Live session into one NVIQ Evidence Bundle record.

    Provider-native interruption, transcription, realtime-input and function-call events are
    preserved as provenance only. Benchmark-critical floor classification and asynchronous
    request-boundary facts require explicit ``nviq.*`` capture events and are never inferred
    from Gemini-native signals. Missing instrumentation therefore fails closed downstream.
    """
    if not isinstance(case, dict) or not case.get("case_id"):
        raise ValueError("case requires case_id")
    if any(not isinstance(event, dict) for event in events):
        raise ValueError("Gemini Live events must be objects")

    _reject_source_scoring(events)

    floor_events: list[dict] = []
    async_tasks: list[dict] = []
    server_content: list[dict] = []
    client_content: list[dict] = []
    client_realtime_input: list[dict] = []
    tool_calls: list[dict] = []
    tool_responses: list[dict] = []
    event_types: Counter[str] = Counter()

    for index, event in enumerate(events):
        event_type = _require_event_type(event, index)
        event_types[event_type] += 1
        if event_type == "nviq.floor":
            floor_events.append(_floor_event(event))
        elif event_type == "nviq.async_task":
            async_tasks.append(_async_event(event))
        elif event_type == "gemini.server_content":
            server_content.append({
                key: value for key, value in event.items() if key not in {"type", "event_id"}
            })
        elif event_type == "gemini.client_content":
            client_content.append({
                key: value for key, value in event.items() if key not in {"type", "event_id"}
            })
        elif event_type == "gemini.client_realtime_input":
            client_realtime_input.append({
                key: value for key, value in event.items() if key not in {"type", "event_id"}
            })
        elif event_type == "gemini.tool_call":
            tool_calls.append({
                key: value for key, value in event.items() if key not in {"type", "event_id"}
            })
        elif event_type == "gemini.tool_response":
            tool_responses.append({
                key: value for key, value in event.items() if key not in {"type", "event_id"}
            })

    evidence: dict = {
        "evidence_version": "0.1",
        "case_id": case["case_id"],
        "track": track,
    }
    if floor_events:
        evidence["floor_events"] = floor_events
    if async_tasks:
        evidence["async_tasks"] = async_tasks

    refs = sorted({_event_ref(event, index) for index, event in enumerate(events)})
    evidence["provenance"] = {
        "evidence_refs": refs,
        "provider": "google",
        "model": model or DEFAULT_MODEL,
        "session_id": session_id,
        "audio_ref": audio_ref,
        "configuration": {
            "adapter": CAPTURE_CONTRACT,
            "source_product": SOURCE_PRODUCT,
            "capture_origin": require_capture_origin(capture_origin, "Gemini Live capture"),
            "event_count": len(events),
            "event_types": dict(sorted(event_types.items())),
            "native_server_content": server_content,
            "client_content": client_content,
            "client_realtime_input": client_realtime_input,
            "tool_calls": tool_calls,
            "tool_responses": tool_responses,
        },
    }
    return evidence


def adapt_gemini_live_trace_manifest(cases: list[dict], manifest_path: Path) -> list[dict]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Gemini Live trace manifest must contain a JSON object")
    _reject_source_scoring(data, path="manifest")
    if data.get("trace_version") != TRACE_VERSION:
        raise ValueError(f"Gemini Live trace manifest trace_version must be {TRACE_VERSION}")

    sessions = data.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise ValueError("Gemini Live trace manifest requires a non-empty sessions array")

    cases_by_id = {case["case_id"]: case for case in cases}
    default_track = str(data.get("default_track") or "audio_native")
    capture_origin = require_capture_origin(data.get("capture_origin"), "Gemini Live trace manifest")
    default_model = data.get("model") or DEFAULT_MODEL

    records = []
    seen: set[tuple[str, str]] = set()
    for index, session in enumerate(sessions):
        if not isinstance(session, dict):
            raise ValueError(f"Gemini Live trace manifest session {index} must be an object")
        case_id = session.get("case_id")
        if case_id not in cases_by_id:
            raise ValueError(f"unknown case_id: {case_id}")
        track = str(session.get("track") or default_track)
        key = (str(case_id), track)
        if key in seen:
            raise ValueError(f"duplicate Gemini Live trace for {case_id} on {track}")
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
            events = load_gemini_live_events(manifest_path.parent / str(session["events_path"]))

        records.append(
            adapt_gemini_live_events(
                cases_by_id[str(case_id)],
                events,
                track=track,
                model=session.get("model") or default_model,
                session_id=session.get("session_id"),
                audio_ref=session.get("audio_ref"),
                capture_origin=session.get("capture_origin") or capture_origin,
            )
        )
    return records
