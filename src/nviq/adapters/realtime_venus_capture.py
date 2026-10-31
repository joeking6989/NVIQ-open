from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .realtime_venus import DEFAULT_MODEL, TRACE_VERSION


_RESULT_TRANSITIONS = {
    "prepared": "prepared_time_ms",
    "returned": "returned_time_ms",
    "accepted": "accepted_time_ms",
    "rejected": "rejected_time_ms",
    "committed": "committed_time_ms",
    "spoken": "spoken_time_ms",
}


class RealtimeVenusRuntimeCapture:
    """Build one NVIQ Realtime-Venus trace session from live runtime callbacks.

    The class is deliberately dependency-free: integrations can pass upstream
    ContextSnapshot/HarnessEvent-like objects by attribute instead of importing
    Realtime-Venus into NVIQ. It records facts; it does not score or repair them.
    Causal contamination and contradictory lifecycle transitions therefore
    remain observable by NVIQ rather than being sanitized at capture time.
    """

    def __init__(
        self,
        *,
        case_id: str,
        session_id: str,
        source_commit: str,
        model: str = DEFAULT_MODEL,
        track: str = "audio_native",
        audio_ref: str | None = None,
    ) -> None:
        if not case_id:
            raise ValueError("case_id is required")
        if not session_id:
            raise ValueError("session_id is required")
        if not source_commit:
            raise ValueError("source_commit is required")
        self.case_id = case_id
        self.session_id = session_id
        self.source_commit = source_commit
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
            "event_id": f"venus-capture-{self._next_event:06d}",
            **payload,
        }
        self._next_event += 1
        self._events.append(event)
        return event

    def record_duplex_chunk(
        self,
        *,
        at_ms: int,
        chunk_index: int,
        is_listen: bool,
        text: str | None = None,
    ) -> dict[str, Any]:
        return self._emit(
            "venus.duplex_chunk",
            at_ms=int(at_ms),
            chunk_index=int(chunk_index),
            is_listen=bool(is_listen),
            text=text,
        )

    def record_harness_event(
        self,
        *,
        at_ms: int,
        event_type: str,
        work_id: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not event_type:
            raise ValueError("event_type is required")
        return self._emit(
            "venus.harness_event",
            at_ms=int(at_ms),
            event_type=event_type,
            work_id=work_id,
            details=dict(details or {}),
        )

    def record_context_snapshot(
        self,
        snapshot: Any,
        *,
        work_id: str,
        evidence_times_at_authorization: Sequence[int | float],
    ) -> None:
        """Capture the upstream immutable request boundary without importing it."""

        cutoff_ms = getattr(snapshot, "cutoff_ms", None)
        cutoff_sequence = getattr(snapshot, "cutoff_sequence", None)
        snapshot_id = getattr(snapshot, "snapshot_id", None)
        snapshot_session_id = getattr(snapshot, "session_id", None)
        if cutoff_ms is None or cutoff_sequence is None:
            raise ValueError("snapshot requires cutoff_ms and cutoff_sequence")
        if snapshot_session_id and str(snapshot_session_id) != self.session_id:
            raise ValueError("snapshot session_id does not match capture session_id")

        self.begin_async_task(
            work_id=work_id,
            authorized_time_ms=int(cutoff_ms),
            evidence_times_at_authorization=evidence_times_at_authorization,
        )
        self.record_harness_event(
            at_ms=int(cutoff_ms),
            event_type="request_boundary_frozen",
            work_id=work_id,
            details={
                "snapshot_id": snapshot_id,
                "cutoff_ms": int(cutoff_ms),
                "cutoff_sequence": int(cutoff_sequence),
            },
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

    def record_silence(
        self,
        *,
        silence_ms: int | float,
        state_preserved: bool,
        speaker_preserved: bool,
        at_ms: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "silence_ms": float(silence_ms),
            "state_preserved": bool(state_preserved),
            "speaker_preserved": bool(speaker_preserved),
        }
        if at_ms is not None:
            payload["at_ms"] = int(at_ms)
        return self._emit("nviq.silence", **payload)

    def record_speaker_state(
        self,
        *,
        expected_speaker_id: str | None,
        speaker_id: str | None,
        overlap_owner_correct: bool | None = None,
        speaker_switch_correct: bool | None = None,
        at_ms: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "expected_speaker_id": expected_speaker_id,
            "speaker_id": speaker_id,
        }
        if overlap_owner_correct is not None:
            payload["overlap_owner_correct"] = bool(overlap_owner_correct)
        if speaker_switch_correct is not None:
            payload["speaker_switch_correct"] = bool(speaker_switch_correct)
        if at_ms is not None:
            payload["at_ms"] = int(at_ms)
        return self._emit("nviq.speaker_state", **payload)

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
        self.record_harness_event(
            at_ms=int(at_ms),
            event_type=f"result_{transition}",
            work_id=work_id,
            details={},
        )

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

    def record_causal_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        required = {
            "event_id",
            "kind",
            "event_time_ms",
            "evidence_available_time_ms",
            "provenance_refs",
        }
        missing = required - set(event)
        if missing:
            raise ValueError(
                "causal event missing field(s): " + ", ".join(sorted(missing))
            )
        return self._emit("nviq.causal_event", event=dict(event))

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
            "source_commit": self.source_commit,
            "capture_origin": "runtime",
            "events": list(self.events),
        }

    def manifest(self, *, flush_async: bool = True) -> dict[str, Any]:
        return {
            "trace_version": TRACE_VERSION,
            "default_track": self.track,
            "model": self.model,
            "source_commit": self.source_commit,
            "capture_origin": "runtime",
            "sessions": [self.session_record(flush_async=flush_async)],
        }

    def write_manifest(
        self,
        path: Path,
        *,
        flush_async: bool = True,
    ) -> Path:
        payload = self.manifest(flush_async=flush_async)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path
