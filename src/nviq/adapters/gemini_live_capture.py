from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .gemini_live import DEFAULT_MODEL, TRACE_VERSION


_RESULT_TRANSITIONS = {
    "prepared": "prepared_time_ms",
    "returned": "returned_time_ms",
    "accepted": "accepted_time_ms",
    "rejected": "rejected_time_ms",
    "committed": "committed_time_ms",
    "spoken": "spoken_time_ms",
}


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _plain(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        payload = bytes(value)
        return {
            "byte_length": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    if isinstance(value, Mapping):
        return {str(key): _plain(nested) for key, nested in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, (str, int, float, bool)):
        return enum_value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _plain(model_dump(exclude_none=True))
        except TypeError:
            return _plain(model_dump())
    to_json_dict = getattr(value, "to_json_dict", None)
    if callable(to_json_dict):
        return _plain(to_json_dict())
    return str(value)


def _transcription(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    text = _get(value, "text")
    if text is None:
        return {"raw": _plain(value)}
    return {"text": str(text)}


class GeminiLiveRuntimeCapture:
    """Capture Gemini Live runtime callbacks without taking a Google SDK dependency.

    This shim records provider facts and explicit NVIQ instrumentation. It deliberately does
    not infer semantic floor labels from ``interrupted`` or infer request-boundary integrity
    from function-call timing. Those judgments remain independently derived by NVIQ.
    """

    def __init__(
        self,
        *,
        case_id: str,
        session_id: str,
        model: str = DEFAULT_MODEL,
        track: str = "audio_native",
        audio_ref: str | None = None,
    ) -> None:
        if not case_id:
            raise ValueError("case_id is required")
        if not session_id:
            raise ValueError("session_id is required")
        self.case_id = case_id
        self.session_id = session_id
        self.model = model
        self.track = track
        self.audio_ref = audio_ref
        self._events: list[dict[str, Any]] = []
        self._async_tasks: dict[str, dict[str, Any]] = {}
        self._next_event = 1

    @property
    def events(self) -> tuple[dict[str, Any], ...]:
        return tuple(json.loads(json.dumps(event)) for event in self._events)

    def _emit(self, record_type: str, **payload: Any) -> dict[str, Any]:
        event = {
            "type": record_type,
            "event_id": f"gemini-live-capture-{self._next_event:06d}",
            **payload,
        }
        self._next_event += 1
        self._events.append(event)
        return event

    def record_server_message(self, message: Any, *, at_ms: int) -> None:
        server_content = _get(message, "server_content")
        if server_content is not None:
            payload: dict[str, Any] = {"at_ms": int(at_ms)}
            for key in (
                "interrupted",
                "turn_complete",
                "generation_complete",
                "waiting_for_input",
                "turn_complete_reason",
                "interaction_status",
            ):
                value = _get(server_content, key)
                if value is not None:
                    payload[key] = _plain(value)
            for key in (
                "interim_input_transcription",
                "input_transcription",
                "output_transcription",
            ):
                value = _transcription(_get(server_content, key))
                if value is not None:
                    payload[key] = value
            model_turn = _get(server_content, "model_turn")
            if model_turn is not None:
                payload["model_turn"] = _plain(model_turn)
            self._emit("gemini.server_content", **payload)

        tool_call = _get(message, "tool_call")
        function_calls = _get(tool_call, "function_calls", []) if tool_call is not None else []
        for call in function_calls or []:
            call_id = _get(call, "id")
            name = _get(call, "name")
            if not call_id or not name:
                raise ValueError("Gemini Live function call requires id and name")
            self._emit(
                "gemini.tool_call",
                at_ms=int(at_ms),
                call_id=str(call_id),
                name=str(name),
                args=_plain(_get(call, "args", {})),
            )

    def record_client_content(
        self,
        *,
        at_ms: int,
        text: str,
        turn_complete: bool = True,
    ) -> dict[str, Any]:
        if not text.strip():
            raise ValueError("text is required")
        return self._emit(
            "gemini.client_content",
            at_ms=int(at_ms),
            text=text,
            turn_complete=bool(turn_complete),
        )

    def record_client_realtime_input(
        self,
        *,
        at_ms: int,
        kind: str,
        mime_type: str | None = None,
        byte_length: int | None = None,
        text: str | None = None,
        content_sha256: str | None = None,
    ) -> dict[str, Any]:
        if not kind:
            raise ValueError("kind is required")
        payload: dict[str, Any] = {"at_ms": int(at_ms), "kind": kind}
        if mime_type is not None:
            payload["mime_type"] = mime_type
        if byte_length is not None:
            if byte_length < 0:
                raise ValueError("byte_length must be non-negative")
            payload["byte_length"] = int(byte_length)
        if text is not None:
            payload["text"] = text
        if content_sha256 is not None:
            if not content_sha256:
                raise ValueError("content_sha256 must be non-empty when provided")
            payload["content_sha256"] = content_sha256
        return self._emit("gemini.client_realtime_input", **payload)

    def record_tool_response(
        self,
        *,
        work_id: str,
        at_ms: int,
        response: Any,
    ) -> dict[str, Any]:
        if not work_id:
            raise ValueError("work_id is required")
        return self._emit(
            "gemini.tool_response",
            at_ms=int(at_ms),
            call_id=work_id,
            work_id=work_id,
            response=_plain(response),
        )

    def record_floor(
        self,
        *,
        interaction_class: str,
        yielded_floor: bool,
        at_ms: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "class": interaction_class,
            "yielded_floor": bool(yielded_floor),
        }
        if at_ms is not None:
            payload["at_ms"] = int(at_ms)
        return self._emit("nviq.floor", **payload)

    def begin_async_task(
        self,
        *,
        work_id: str,
        authorized_time_ms: int | float,
        evidence_times_at_authorization: Sequence[int | float],
        later_evidence_retroactively_added: bool = False,
    ) -> None:
        if not work_id:
            raise ValueError("work_id is required")
        if work_id in self._async_tasks:
            raise ValueError(f"async task already exists: {work_id}")
        self._async_tasks[work_id] = {
            "kind": "async_task",
            "work_id": work_id,
            "authorized_time_ms": float(authorized_time_ms),
            "evidence_times_at_authorization": [
                float(value) for value in evidence_times_at_authorization
            ],
            "later_evidence_retroactively_added": bool(
                later_evidence_retroactively_added
            ),
        }

    def mark_async_transition(
        self,
        *,
        work_id: str,
        transition: str,
        at_ms: int | float,
    ) -> None:
        task = self._async_tasks.get(work_id)
        if task is None:
            raise ValueError(f"unknown async task: {work_id}")
        field = _RESULT_TRANSITIONS.get(transition)
        if field is None:
            raise ValueError(
                "transition must be one of: " + ", ".join(_RESULT_TRANSITIONS)
            )
        task[field] = float(at_ms)

    def mark_retroactive_evidence(self, *, work_id: str) -> None:
        task = self._async_tasks.get(work_id)
        if task is None:
            raise ValueError(f"unknown async task: {work_id}")
        task["later_evidence_retroactively_added"] = True

    def flush_async_task(self, work_id: str) -> dict[str, Any]:
        task = self._async_tasks.pop(work_id, None)
        if task is None:
            raise ValueError(f"unknown async task: {work_id}")
        payload = {key: value for key, value in task.items() if key != "work_id"}
        return self._emit("nviq.async_task", **payload)

    def flush_all_async_tasks(self) -> None:
        for work_id in list(self._async_tasks):
            self.flush_async_task(work_id)

    def session_record(self, *, flush_async: bool = True) -> dict[str, Any]:
        if flush_async:
            self.flush_all_async_tasks()
        if self._async_tasks:
            raise ValueError("unflushed async tasks remain")
        return {
            "case_id": self.case_id,
            "track": self.track,
            "model": self.model,
            "session_id": self.session_id,
            "audio_ref": self.audio_ref,
            "capture_origin": "runtime",
            "events": list(self.events),
        }

    def manifest(self, *, flush_async: bool = True) -> dict[str, Any]:
        return {
            "trace_version": TRACE_VERSION,
            "default_track": self.track,
            "model": self.model,
            "capture_origin": "runtime",
            "sessions": [self.session_record(flush_async=flush_async)],
        }

    def write_manifest(self, path: Path, *, flush_async: bool = True) -> Path:
        payload = self.manifest(flush_async=flush_async)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path
