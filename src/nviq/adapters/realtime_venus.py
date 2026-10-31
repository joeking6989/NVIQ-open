from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .provenance import require_capture_origin


TRACE_VERSION = "0.1"
CAPTURE_CONTRACT = "nviq-realtime-venus-v0.1"
DEFAULT_MODEL = "Realtime-Venus-Audio-9B"
SOURCE_REPOSITORY = "inclusionAI/Realtime-Venus"

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
    "venus.duplex_chunk",
    "venus.harness_event",
    "nviq.floor",
    "nviq.silence",
    "nviq.speaker_state",
    "nviq.async_task",
    "nviq.causal_event",
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


def load_venus_events(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError(f"Realtime-Venus event JSON must contain an array: {path}")
        events = data
    else:
        events = [json.loads(line) for line in text.splitlines() if line.strip()]
    if any(not isinstance(event, dict) for event in events):
        raise ValueError(f"Realtime-Venus events must be JSON objects: {path}")
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
    return f"venus-event:{index}:{event.get('type', 'unknown')}"


def _require_event_type(event: dict, index: int) -> str:
    event_type = event.get("type")
    if event_type not in _SUPPORTED_EVENT_TYPES:
        raise ValueError(
            f"Realtime-Venus event {index} has unsupported type: {event_type!r}"
        )
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
    return {
        "class": interaction_class,
        "yielded_floor": event["yielded_floor"],
    }


def _silence_event(event: dict) -> dict:
    required = ("silence_ms", "state_preserved", "speaker_preserved")
    if any(key not in event for key in required):
        raise ValueError("nviq.silence requires silence_ms, state_preserved and speaker_preserved")
    if not isinstance(event["state_preserved"], bool) or not isinstance(event["speaker_preserved"], bool):
        raise ValueError("nviq.silence preservation fields must be boolean")
    return {
        "silence_ms": float(event["silence_ms"]),
        "state_preserved": event["state_preserved"],
        "speaker_preserved": event["speaker_preserved"],
    }


def _speaker_event(event: dict) -> dict:
    if "expected_speaker_id" not in event or "speaker_id" not in event:
        raise ValueError("nviq.speaker_state requires expected_speaker_id and speaker_id")
    result = {
        "expected_speaker_id": event.get("expected_speaker_id"),
        "speaker_id": event.get("speaker_id"),
    }
    for key in ("overlap_owner_correct", "speaker_switch_correct"):
        if key in event:
            if not isinstance(event[key], bool):
                raise ValueError(f"nviq.speaker_state {key} must be boolean")
            result[key] = event[key]
    return result


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
    result = {
        key: event.get(key)
        for key in _ASYNC_FIELDS
        if key in event
    }
    result["kind"] = "async_task"
    return result


def _causal_event(event: dict) -> dict:
    payload = event.get("event")
    if not isinstance(payload, dict):
        raise ValueError("nviq.causal_event requires an event object")
    return dict(payload)


def adapt_realtime_venus_events(
    case: dict,
    events: list[dict],
    *,
    track: str = "audio_native",
    model: str | None = None,
    session_id: str | None = None,
    audio_ref: str | None = None,
    source_commit: str | None = None,
    capture_origin: str | None = None,
) -> dict:
    """Convert a captured Realtime-Venus session into one NVIQ Evidence Bundle record.

    Native Venus telemetry is preserved in provenance. Benchmark-critical semantic labels are
    accepted only through explicit nviq.* capture events; for example, is_listen from a duplex
    chunk is never treated as proof that speech was a backchannel or interruption. Missing
    instrumentation therefore fails closed later in the NVIQ execution engine.
    """
    if not isinstance(case, dict) or not case.get("case_id"):
        raise ValueError("case requires case_id")
    if any(not isinstance(event, dict) for event in events):
        raise ValueError("Realtime-Venus events must be objects")

    _reject_source_scoring(events)

    floor_events: list[dict] = []
    silence_events: list[dict] = []
    speaker_events: list[dict] = []
    async_tasks: list[dict] = []
    causal_events: list[dict] = []
    native_chunks: list[dict] = []
    harness_events: list[dict] = []
    event_types: Counter[str] = Counter()

    for index, event in enumerate(events):
        event_type = _require_event_type(event, index)
        event_types[event_type] += 1

        if event_type == "nviq.floor":
            floor_events.append(_floor_event(event))
        elif event_type == "nviq.silence":
            silence_events.append(_silence_event(event))
        elif event_type == "nviq.speaker_state":
            speaker_events.append(_speaker_event(event))
        elif event_type == "nviq.async_task":
            async_tasks.append(_async_event(event))
        elif event_type == "nviq.causal_event":
            causal_events.append(_causal_event(event))
        elif event_type == "venus.duplex_chunk":
            native_chunks.append({
                "at_ms": event.get("at_ms"),
                "chunk_index": event.get("chunk_index"),
                "is_listen": event.get("is_listen"),
                "text": event.get("text"),
            })
        elif event_type == "venus.harness_event":
            harness_events.append({
                "at_ms": event.get("at_ms"),
                "event_type": event.get("event_type"),
                "work_id": event.get("work_id"),
                "details": event.get("details", {}),
            })

    evidence: dict = {
        "evidence_version": "0.1",
        "case_id": case["case_id"],
        "track": track,
    }
    if floor_events:
        evidence["floor_events"] = floor_events
    if silence_events:
        evidence["silence_events"] = silence_events
    if speaker_events:
        evidence["speaker_state_events"] = speaker_events
    if async_tasks:
        evidence["async_tasks"] = async_tasks
    if causal_events:
        evidence["ledger"] = {
            "ledger_version": "0.1",
            "case_id": case["case_id"],
            "events": causal_events,
        }

    refs = sorted({_event_ref(event, index) for index, event in enumerate(events)})
    evidence["provenance"] = {
        "evidence_refs": refs,
        "provider": "inclusionAI",
        "model": model or DEFAULT_MODEL,
        "session_id": session_id,
        "audio_ref": audio_ref,
        "configuration": {
            "adapter": CAPTURE_CONTRACT,
            "source_repository": SOURCE_REPOSITORY,
            "source_commit": source_commit,
            "capture_origin": require_capture_origin(capture_origin, "Realtime-Venus capture"),
            "event_count": len(events),
            "event_types": dict(sorted(event_types.items())),
            "native_duplex_chunks": native_chunks,
            "harness_events": harness_events,
        },
    }
    return evidence


def adapt_realtime_venus_trace_manifest(cases: list[dict], manifest_path: Path) -> list[dict]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Realtime-Venus trace manifest must contain a JSON object")
    _reject_source_scoring(data, path="manifest")
    if data.get("trace_version") != TRACE_VERSION:
        raise ValueError(f"Realtime-Venus trace manifest trace_version must be {TRACE_VERSION}")

    sessions = data.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise ValueError("Realtime-Venus trace manifest requires a non-empty sessions array")

    cases_by_id = {case["case_id"]: case for case in cases}
    default_track = str(data.get("default_track") or "audio_native")
    source_commit = data.get("source_commit")
    capture_origin = require_capture_origin(data.get("capture_origin"), "Realtime-Venus trace manifest")
    default_model = data.get("model") or DEFAULT_MODEL

    records = []
    seen: set[tuple[str, str]] = set()
    for index, session in enumerate(sessions):
        if not isinstance(session, dict):
            raise ValueError(f"Realtime-Venus trace manifest session {index} must be an object")
        case_id = session.get("case_id")
        if case_id not in cases_by_id:
            raise ValueError(f"unknown case_id: {case_id}")
        track = str(session.get("track") or default_track)
        key = (str(case_id), track)
        if key in seen:
            raise ValueError(f"duplicate Realtime-Venus trace for {case_id} on {track}")
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
            events = load_venus_events(manifest_path.parent / str(session["events_path"]))

        records.append(
            adapt_realtime_venus_events(
                cases_by_id[str(case_id)],
                events,
                track=track,
                model=session.get("model") or default_model,
                session_id=session.get("session_id"),
                audio_ref=session.get("audio_ref"),
                source_commit=session.get("source_commit") or source_commit,
                capture_origin=session.get("capture_origin") or capture_origin,
            )
        )
    return records
