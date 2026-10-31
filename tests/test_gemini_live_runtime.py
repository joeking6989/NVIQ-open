import asyncio
import json

import pytest

from nviq.adapters.gemini_live_capture import GeminiLiveRuntimeCapture
from nviq.gemini_live_runtime import exercise_async_tool_session, resolve_api_key


class FakeCapture:
    def __init__(self):
        self.calls = []

    def record_client_content(self, **kwargs):
        self.calls.append(("client", kwargs))

    def record_server_message(self, message, **kwargs):
        self.calls.append(("server", message, kwargs))

    def begin_async_task(self, **kwargs):
        self.calls.append(("begin", kwargs))

    def mark_async_transition(self, **kwargs):
        self.calls.append(("transition", kwargs))

    def record_tool_response(self, **kwargs):
        self.calls.append(("tool_response", kwargs))

    def flush_async_task(self, work_id):
        self.calls.append(("flush", work_id))


class FakeFunctionResponse:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeTypes:
    FunctionResponse = FakeFunctionResponse


class FakeSession:
    def __init__(self):
        self.sent = []

    async def send_client_content(self, **kwargs):
        self.sent.append(("client", kwargs))

    async def send_tool_response(self, **kwargs):
        self.sent.append(("tool", kwargs))

    def receive(self):
        messages = [
            {
                "server_content": {
                    "output_transcription": {"text": "Checking."},
                },
            },
            {
                "tool_call": {
                    "function_calls": [{
                        "id": "work-1",
                        "name": "lookup_schedule",
                        "args": {"day": "Monday"},
                    }],
                },
            },
            {
                "server_content": {
                    "model_turn": {
                        "parts": [{
                            "inline_data": {"mime_type": "audio/pcm"},
                        }],
                    },
                    "output_transcription": {
                        "text": "Ten o'clock is available.",
                    },
                    "turn_complete": True,
                },
            },
        ]

        async def generate():
            for item in messages:
                yield item

        return generate()


def test_async_runtime_exercise_records_complete_tool_provenance():
    ticks = iter([100, 200, 300, 400, 500, 600, 700, 800, 900])
    capture = FakeCapture()
    session = FakeSession()

    result = asyncio.run(
        exercise_async_tool_session(
            session,
            capture,
            FakeTypes,
            now_ms=lambda: next(ticks),
        )
    )

    assert result["work_id"] == "work-1"
    transitions = [
        entry[1]["transition"]
        for entry in capture.calls
        if entry[0] == "transition"
    ]
    assert transitions == [
        "prepared",
        "returned",
        "accepted",
        "committed",
        "spoken",
    ]

    begin = next(entry[1] for entry in capture.calls if entry[0] == "begin")
    assert begin["authorized_time_ms"] == 300
    assert all(
        value <= begin["authorized_time_ms"]
        for value in begin["evidence_times_at_authorization"]
    )

    assert any(entry[0] == "tool_response" for entry in capture.calls)
    assert session.sent[0][0] == "client"
    assert session.sent[1][0] == "tool"


def test_capture_records_client_content_in_runtime_manifest(tmp_path):
    capture = GeminiLiveRuntimeCapture(
        case_id="NVIQ-GEMINI-ASYNC-001",
        session_id="session-1",
    )
    event = capture.record_client_content(
        at_ms=10,
        text="benchmark prompt",
        turn_complete=True,
    )
    assert event["type"] == "gemini.client_content"

    path = capture.write_manifest(tmp_path / "trace.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["capture_origin"] == "runtime"
    assert payload["sessions"][0]["events"][0]["text"] == "benchmark prompt"


def test_resolve_api_key_accepts_gemini_or_google_name(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
    assert resolve_api_key() == "google-key"

    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    assert resolve_api_key() == "gemini-key"


def test_resolve_api_key_fails_closed_when_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="not configured"):
        resolve_api_key()


class FakeSplitTurnSession:
    def __init__(self):
        self.sent = []
        self.receive_calls = 0

    async def send_client_content(self, **kwargs):
        self.sent.append(("client", kwargs))

    async def send_tool_response(self, **kwargs):
        self.sent.append(("tool", kwargs))

    def receive(self):
        self.receive_calls += 1
        if self.receive_calls == 1:
            messages = [
                {
                    "tool_call": {
                        "function_calls": [{
                            "id": "work-1",
                            "name": "lookup_schedule",
                            "args": {"day": "Monday"},
                        }],
                    },
                },
                {
                    "server_content": {
                        "turn_complete": True,
                    },
                },
            ]
        else:
            messages = [
                {
                    "server_content": {
                        "model_turn": {
                            "parts": [{
                                "inline_data": {"mime_type": "audio/pcm"},
                            }],
                        },
                        "output_transcription": {
                            "text": "Ten o'clock is available.",
                        },
                        "turn_complete": True,
                    },
                },
            ]

        async def generate():
            for item in messages:
                yield item

        return generate()


def test_async_runtime_continues_receiving_after_nonblocking_tool_turn_completes():
    ticks = iter([100, 200, 300, 400, 500, 600, 700, 800, 900, 1000])
    capture = FakeCapture()
    session = FakeSplitTurnSession()

    result = asyncio.run(
        exercise_async_tool_session(
            session,
            capture,
            FakeTypes,
            now_ms=lambda: next(ticks),
        )
    )

    assert result["work_id"] == "work-1"
    assert session.receive_calls == 2
    transitions = [
        entry[1]["transition"]
        for entry in capture.calls
        if entry[0] == "transition"
    ]
    assert transitions == [
        "prepared",
        "returned",
        "accepted",
        "committed",
        "spoken",
    ]
