import asyncio
import hashlib
import importlib
import json

import pytest

from nviq.adapters.gemini_live_capture import GeminiLiveRuntimeCapture


class FakeBlob:
    def __init__(self, *, data, mime_type):
        self.data = data
        self.mime_type = mime_type


class FakeActivityStart:
    pass


class FakeActivityEnd:
    pass


class FakeTypes:
    Blob = FakeBlob
    ActivityStart = FakeActivityStart
    ActivityEnd = FakeActivityEnd


class FakeCapture:
    def __init__(self):
        self.calls = []

    def record_client_content(self, **kwargs):
        self.calls.append(("client_content", kwargs))

    def record_client_realtime_input(self, **kwargs):
        self.calls.append(("client_audio", kwargs))

    def record_server_message(self, message, **kwargs):
        self.calls.append(("server", message, kwargs))

    def record_floor(self, **kwargs):
        self.calls.append(("floor", kwargs))


class FakeSession:
    def __init__(self, *, interrupted):
        self.interrupted = interrupted
        self.sent_client = []
        self.sent_realtime = []
        self.receive_calls = 0

    async def send_client_content(self, **kwargs):
        self.sent_client.append(kwargs)

    async def send_realtime_input(self, **kwargs):
        self.sent_realtime.append(kwargs)

    def receive(self):
        self.receive_calls += 1
        if self.receive_calls == 1:
            messages = [
                {
                    "server_content": {
                        "model_turn": {
                            "parts": [{
                                "inline_data": {
                                    "mime_type": "audio/pcm",
                                    "data": b"model-audio",
                                },
                            }],
                        },
                    },
                },
                {
                    "server_content": {
                        "interrupted": self.interrupted,
                        "turn_complete": True,
                    },
                },
            ]
        else:
            messages = [
                {
                    "server_content": {
                        "input_transcription": {"text": "excuse me stop"},
                        "turn_complete": True,
                    },
                },
            ]

        async def generate():
            for item in messages:
                yield item

        return generate()


def _load_runtime():
    return importlib.import_module("nviq.gemini_live_floor_runtime")


def test_floor_runtime_declares_all_four_canonical_stimuli():
    runtime = _load_runtime()
    classes = [item.interaction_class for item in runtime.FLOOR_STIMULI]
    expected = [item.expected_yielded_floor for item in runtime.FLOOR_STIMULI]
    assert classes == [
        "background_speech",
        "other_directed_speech",
        "backchannel",
        "genuine_interruption",
    ]
    assert expected == [False, False, False, True]


def test_floor_episode_records_native_interruption_as_yield():
    runtime = _load_runtime()
    stimulus = runtime.FloorStimulus(
        interaction_class="genuine_interruption",
        spoken_text="Excuse me. Stop.",
        filename="interrupt.pcm",
        expected_yielded_floor=True,
    )
    capture = FakeCapture()
    session = FakeSession(interrupted=True)
    ticks = iter(range(100, 5000, 100))

    result = asyncio.run(
        runtime.exercise_floor_episode(
            session,
            capture,
            FakeTypes,
            stimulus=stimulus,
            pcm=b"\x00\x01" * 1600,
            now_ms=lambda: next(ticks),
            sleep=lambda _: asyncio.sleep(0),
        )
    )

    assert result["yielded_floor"] is True
    assert result["input_transcription"] == ""
    floor = next(entry[1] for entry in capture.calls if entry[0] == "floor")
    assert floor["class"] if "class" in floor else floor["interaction_class"]
    assert floor["yielded_floor"] is True


def test_floor_episode_can_score_calibrated_pcm_without_runtime_transcript():
    runtime = _load_runtime()
    stimulus = runtime.FloorStimulus(
        interaction_class="backchannel",
        spoken_text="Yeah, I understand. Uh huh, keep going.",
        filename="backchannel.pcm",
        expected_yielded_floor=False,
    )

    class NoTranscriptSession(FakeSession):
        def receive(self):
            self.receive_calls += 1
            messages = [
                {
                    "server_content": {
                        "model_turn": {
                            "parts": [{
                                "inline_data": {
                                    "mime_type": "audio/pcm",
                                    "data": b"model-audio",
                                },
                            }],
                        },
                    },
                },
                {
                    "server_content": {
                        "turn_complete": True,
                    },
                },
            ]

            async def generate():
                for item in messages:
                    yield item

            return generate()

    capture = FakeCapture()
    result = asyncio.run(
        runtime.exercise_floor_episode(
            NoTranscriptSession(interrupted=False),
            capture,
            FakeTypes,
            stimulus=stimulus,
            pcm=b"\x00\x01" * 1600,
            now_ms=iter(range(100, 5000, 100)).__next__,
            sleep=lambda _: asyncio.sleep(0),
            max_receive_cycles=1,
        )
    )
    assert result["yielded_floor"] is False
    assert result["input_transcription"] == ""
    floor = next(entry[1] for entry in capture.calls if entry[0] == "floor")
    assert floor["yielded_floor"] is False


def test_capture_redacts_binary_model_audio(tmp_path):
    capture = GeminiLiveRuntimeCapture(
        case_id="NVIQ-GEMINI-FLOOR-001",
        session_id="session-1",
    )
    raw = b"\x00\x01" * 128
    capture.record_server_message(
        {
            "server_content": {
                "model_turn": {
                    "parts": [{
                        "inline_data": {
                            "mime_type": "audio/pcm",
                            "data": raw,
                        },
                    }],
                },
            },
        },
        at_ms=10,
    )

    path = capture.write_manifest(tmp_path / "trace.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    stored = payload["sessions"][0]["events"][0]["model_turn"]["parts"][0]["inline_data"]["data"]
    assert stored == {
        "byte_length": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def test_floor_stimuli_use_independent_case_ids():
    runtime = _load_runtime()
    case_ids = [item.case_id for item in runtime.FLOOR_STIMULI]
    assert len(case_ids) == 4
    assert len(set(case_ids)) == 4
    assert all(case_id.startswith("NVIQ-GEMINI-FLOOR-") for case_id in case_ids)


def test_floor_episode_does_not_wait_for_fragmentary_transcript_after_interruption():
    runtime = _load_runtime()
    stimulus = runtime.FloorStimulus(
        case_id="NVIQ-GEMINI-FLOOR-BACKGROUND-001",
        interaction_class="background_speech",
        spoken_text="This is a radio bulletin. Traffic is moving slowly on the highway.",
        filename="background.pcm",
        expected_yielded_floor=False,
    )

    class PoorTranscriptSession(FakeSession):
        def receive(self):
            self.receive_calls += 1
            if self.receive_calls == 1:
                messages = [
                    {
                        "server_content": {
                            "model_turn": {
                                "parts": [{
                                    "inline_data": {
                                        "mime_type": "audio/pcm",
                                        "data": b"model-audio",
                                    },
                                }],
                            },
                        },
                    },
                    {
                        "server_content": {
                            "interrupted": True,
                            "turn_complete": True,
                        },
                    },
                ]
            else:
                messages = [
                    {
                        "server_content": {
                            "input_transcription": {"text": "de"},
                            "turn_complete": True,
                        },
                    },
                ]

            async def generate():
                for item in messages:
                    yield item

            return generate()

    result = asyncio.run(
        runtime.exercise_floor_episode(
            PoorTranscriptSession(interrupted=True),
            FakeCapture(),
            FakeTypes,
            stimulus=stimulus,
            pcm=b"\x00\x01" * 1600,
            now_ms=iter(range(100, 5000, 100)).__next__,
            sleep=lambda _: asyncio.sleep(0),
        )
    )
    assert result["yielded_floor"] is True
    assert result["input_transcription"] == ""
    assert result["transcription_overlap"] == 0.0


def test_calibration_rejects_transcription_that_does_not_match_stimulus():
    runtime = _load_runtime()
    with pytest.raises(RuntimeError, match="calibration transcription does not match"):
        runtime.validate_calibration_transcript(
            "This is a radio bulletin. Traffic is moving slowly on the highway.",
            "de",
            interaction_class="background_speech",
        )


def test_capture_client_audio_records_content_sha256():
    capture = GeminiLiveRuntimeCapture(
        case_id="NVIQ-GEMINI-FLOOR-BACKGROUND-001",
        session_id="session-1",
    )
    capture.record_client_realtime_input(
        at_ms=10,
        kind="audio",
        mime_type="audio/pcm;rate=16000",
        byte_length=256,
        text="background speech",
        content_sha256="abc123",
    )
    assert capture.events[0]["content_sha256"] == "abc123"

def test_floor_episode_does_not_require_followup_interim_transcription_after_interruption():
    runtime = _load_runtime()
    stimulus = runtime.FloorStimulus(
        case_id="NVIQ-GEMINI-FLOOR-BACKGROUND-001",
        interaction_class="background_speech",
        spoken_text="This is a radio bulletin. Traffic is moving slowly on the highway.",
        filename="background.pcm",
        expected_yielded_floor=False,
    )

    class InterimTranscriptSession(FakeSession):
        def receive(self):
            self.receive_calls += 1
            if self.receive_calls == 1:
                messages = [
                    {
                        "server_content": {
                            "model_turn": {
                                "parts": [{
                                    "inline_data": {
                                        "mime_type": "audio/pcm",
                                        "data": b"model-audio",
                                    },
                                }],
                            },
                        },
                    },
                    {
                        "server_content": {
                            "interrupted": True,
                            "turn_complete": True,
                        },
                    },
                ]
            else:
                messages = [
                    {
                        "server_content": {
                            "interim_input_transcription": {
                                "text": "This is a radio bulletin. Traffic is moving slowly on the highway."
                            },
                            "input_transcription": {"text": "de"},
                            "turn_complete": True,
                        },
                    },
                ]

            async def generate():
                for item in messages:
                    yield item

            return generate()

    result = asyncio.run(
        runtime.exercise_floor_episode(
            InterimTranscriptSession(interrupted=True),
            FakeCapture(),
            FakeTypes,
            stimulus=stimulus,
            pcm=b"\x00\x01" * 1600,
            now_ms=iter(range(100, 5000, 100)).__next__,
            sleep=lambda _: asyncio.sleep(0),
        )
    )
    assert result["yielded_floor"] is True
    assert result["input_transcription"] == ""
    assert result["transcription_overlap"] == 0.0


def test_capture_preserves_interim_input_transcription(tmp_path):
    capture = GeminiLiveRuntimeCapture(
        case_id="NVIQ-GEMINI-FLOOR-BACKGROUND-001",
        session_id="session-1",
    )
    capture.record_server_message(
        {
            "server_content": {
                "interim_input_transcription": {
                    "text": "This is a radio bulletin."
                }
            }
        },
        at_ms=10,
    )
    path = capture.write_manifest(tmp_path / "trace.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    event = payload["sessions"][0]["events"][0]
    assert event["interim_input_transcription"]["text"] == "This is a radio bulletin."


def test_calibrate_floor_stimulus_accepts_matching_idle_transcription():
    runtime = _load_runtime()
    stimulus = runtime.FloorStimulus(
        case_id="NVIQ-GEMINI-FLOOR-BACKGROUND-001",
        interaction_class="background_speech",
        spoken_text="This is a radio bulletin. Traffic is moving slowly on the highway.",
        filename="background.pcm",
        expected_yielded_floor=False,
    )

    class CalibrationSession:
        def __init__(self):
            self.sent = []

        async def send_realtime_input(self, **kwargs):
            self.sent.append(kwargs)

        def receive(self):
            messages = [
                {
                    "server_content": {
                        "interim_input_transcription": {
                            "text": "This is a radio bulletin. Traffic is moving slowly on the highway."
                        },
                        "turn_complete": True,
                    },
                },
            ]

            async def generate():
                for item in messages:
                    yield item

            return generate()

    session = CalibrationSession()
    result = asyncio.run(
        runtime.calibrate_floor_stimulus(
            session,
            FakeTypes,
            stimulus=stimulus,
            pcm=b"\x00\x01" * 1600,
            sleep=lambda _: asyncio.sleep(0),
        )
    )
    assert result["transcription_overlap"] == 1.0
    assert len(result["content_sha256"]) == 64
    assert any("activity_start" in item for item in session.sent)
    assert any("activity_end" in item for item in session.sent)


def test_calibration_returns_after_valid_transcription_without_turn_complete():
    runtime = _load_runtime()
    stimulus = runtime.FloorStimulus(
        case_id="NVIQ-GEMINI-FLOOR-BACKCHANNEL-001",
        interaction_class="backchannel",
        spoken_text="Uh huh.",
        filename="backchannel.pcm",
        expected_yielded_floor=False,
    )

    class NoTurnCompleteSession:
        async def send_realtime_input(self, **kwargs):
            pass

        def receive(self):
            async def generate():
                yield {
                    "server_content": {
                        "interim_input_transcription": {"text": "Uh huh."}
                    }
                }
                await asyncio.Event().wait()

            return generate()

    async def run():
        return await asyncio.wait_for(
            runtime.calibrate_floor_stimulus(
                NoTurnCompleteSession(),
                FakeTypes,
                stimulus=stimulus,
                pcm=b"\x00\x01" * 1600,
                sleep=lambda _: asyncio.sleep(0),
            ),
            timeout=0.1,
        )

    result = asyncio.run(run())
    assert result["transcription_overlap"] == 1.0


def test_backchannel_stimulus_is_long_enough_for_audibility_calibration():
    runtime = _load_runtime()
    stimulus = next(
        item for item in runtime.FLOOR_STIMULI
        if item.interaction_class == "backchannel"
    )
    tokens = stimulus.spoken_text.replace(",", " ").replace(".", " ").split()
    assert len(tokens) >= 6
    assert "uh" in stimulus.spoken_text.casefold()
    assert "huh" in stimulus.spoken_text.casefold()
