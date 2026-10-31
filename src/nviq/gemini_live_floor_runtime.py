from __future__ import annotations

import argparse
import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import json
from pathlib import Path
import re
import time
from typing import Any

from .adapters.gemini_live import DEFAULT_MODEL, TRACE_VERSION
from .adapters.gemini_live_capture import GeminiLiveRuntimeCapture
from .gemini_live_runtime import resolve_api_key


MODEL_PROMPT = (
    "Count slowly and continuously from one to forty in a calm voice. "
    "Do not ask a question and do not stop early."
)

_PCM_BYTES_PER_SECOND = 16000 * 2
_DEFAULT_CHUNK_MS = 100
_DEFAULT_SILENCE_MS = 450


@dataclass(frozen=True)
class FloorStimulus:
    interaction_class: str
    spoken_text: str
    filename: str
    expected_yielded_floor: bool
    case_id: str = "NVIQ-GEMINI-FLOOR-001"


FLOOR_STIMULI: tuple[FloorStimulus, ...] = (
    FloorStimulus(
        interaction_class="background_speech",
        spoken_text="This is a radio bulletin. Traffic is moving slowly on the highway.",
        filename="background.pcm",
        expected_yielded_floor=False,
        case_id="NVIQ-GEMINI-FLOOR-BACKGROUND-001",
    ),
    FloorStimulus(
        interaction_class="other_directed_speech",
        spoken_text="Hey Alex, can you bring the red folder over here?",
        filename="other.pcm",
        expected_yielded_floor=False,
        case_id="NVIQ-GEMINI-FLOOR-OTHER-001",
    ),
    FloorStimulus(
        interaction_class="backchannel",
        spoken_text="Yeah, I understand. Uh huh, keep going.",
        filename="backchannel.pcm",
        expected_yielded_floor=False,
        case_id="NVIQ-GEMINI-FLOOR-BACKCHANNEL-001",
    ),
    FloorStimulus(
        interaction_class="genuine_interruption",
        spoken_text="Excuse me. Stop. I need to correct you.",
        filename="interruption.pcm",
        expected_yielded_floor=True,
        case_id="NVIQ-GEMINI-FLOOR-INTERRUPTION-001",
    ),
)


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _model_audio_present(message: Any) -> bool:
    content = _get(message, "server_content")
    if content is None:
        return False
    model_turn = _get(content, "model_turn")
    if model_turn is None:
        return False
    for part in _get(model_turn, "parts", []) or []:
        inline = _get(part, "inline_data")
        if inline is None:
            continue
        data = _get(inline, "data")
        if data:
            return True
    return False


def _input_transcription_text(message: Any) -> str:
    content = _get(message, "server_content")
    if content is None:
        return ""
    texts: list[str] = []
    for key in ("interim_input_transcription", "input_transcription"):
        transcription = _get(content, key)
        if transcription is None:
            continue
        text = str(_get(transcription, "text", "") or "").strip()
        if text and text not in texts:
            texts.append(text)
    return " ".join(texts)


def _transcription_overlap(expected: str, observed: str) -> float:
    expected_tokens = {
        token for token in re.findall(r"[a-z0-9]+", expected.casefold())
        if len(token) > 1
    }
    observed_tokens = {
        token for token in re.findall(r"[a-z0-9]+", observed.casefold())
        if len(token) > 1
    }
    if not expected_tokens:
        return 1.0
    return len(expected_tokens & observed_tokens) / len(expected_tokens)


def validate_calibration_transcript(
    expected: str,
    observed: str,
    *,
    interaction_class: str,
    minimum_overlap: float = 0.35,
) -> float:
    overlap = _transcription_overlap(expected, observed)
    if overlap < minimum_overlap:
        raise RuntimeError(
            "Gemini Live calibration transcription does not match floor stimulus "
            f"{interaction_class}: overlap={overlap:.3f}; transcript={observed!r}"
        )
    return overlap


async def _send_pcm_realtime(
    session: Any,
    types_module: Any,
    pcm: bytes,
    *,
    sleep: Callable[[float], Awaitable[None]],
    chunk_ms: int = _DEFAULT_CHUNK_MS,
    silence_ms: int = _DEFAULT_SILENCE_MS,
) -> None:
    if not pcm:
        raise ValueError("PCM stimulus is empty")
    if chunk_ms <= 0:
        raise ValueError("chunk_ms must be positive")
    if silence_ms < 0:
        raise ValueError("silence_ms must be non-negative")

    chunk_bytes = max(2, int(_PCM_BYTES_PER_SECOND * (chunk_ms / 1000.0)))
    chunk_bytes -= chunk_bytes % 2

    for offset in range(0, len(pcm), chunk_bytes):
        chunk = pcm[offset : offset + chunk_bytes]
        await session.send_realtime_input(
            audio=types_module.Blob(
                data=chunk,
                mime_type="audio/pcm;rate=16000",
            )
        )
        await sleep(len(chunk) / _PCM_BYTES_PER_SECOND)

    if silence_ms:
        silence = bytes(int(_PCM_BYTES_PER_SECOND * (silence_ms / 1000.0)))
        await session.send_realtime_input(
            audio=types_module.Blob(
                data=silence,
                mime_type="audio/pcm;rate=16000",
            )
        )
        await sleep(silence_ms / 1000.0)

    await session.send_realtime_input(audio_stream_end=True)


async def _send_pcm_manual_activity(
    session: Any,
    types_module: Any,
    pcm: bytes,
    *,
    sleep: Callable[[float], Awaitable[None]],
    chunk_ms: int = _DEFAULT_CHUNK_MS,
    silence_ms: int = _DEFAULT_SILENCE_MS,
) -> None:
    """Send one PCM utterance with explicit activity boundaries for ASR calibration."""

    if not pcm:
        raise ValueError("PCM stimulus is empty")
    if chunk_ms <= 0:
        raise ValueError("chunk_ms must be positive")
    if silence_ms < 0:
        raise ValueError("silence_ms must be non-negative")

    await session.send_realtime_input(
        activity_start=types_module.ActivityStart()
    )

    chunk_bytes = max(2, int(_PCM_BYTES_PER_SECOND * (chunk_ms / 1000.0)))
    chunk_bytes -= chunk_bytes % 2
    for offset in range(0, len(pcm), chunk_bytes):
        chunk = pcm[offset : offset + chunk_bytes]
        await session.send_realtime_input(
            audio=types_module.Blob(
                data=chunk,
                mime_type="audio/pcm;rate=16000",
            )
        )
        await sleep(len(chunk) / _PCM_BYTES_PER_SECOND)

    if silence_ms:
        silence = bytes(int(_PCM_BYTES_PER_SECOND * (silence_ms / 1000.0)))
        await session.send_realtime_input(
            audio=types_module.Blob(
                data=silence,
                mime_type="audio/pcm;rate=16000",
            )
        )
        await sleep(silence_ms / 1000.0)

    await session.send_realtime_input(
        activity_end=types_module.ActivityEnd()
    )


async def calibrate_floor_stimulus(
    session: Any,
    types_module: Any,
    *,
    stimulus: FloorStimulus,
    pcm: bytes,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    max_receive_cycles: int = 2,
) -> dict[str, Any]:
    """Prove the exact PCM stimulus is intelligible before floor scoring."""

    if max_receive_cycles < 1:
        raise ValueError("max_receive_cycles must be positive")
    content_sha256 = hashlib.sha256(pcm).hexdigest()
    await _send_pcm_manual_activity(
        session,
        types_module,
        pcm,
        sleep=sleep,
    )

    transcriptions: list[str] = []
    qualified = False
    for _ in range(max_receive_cycles):
        receiver = session.receive()
        try:
            while True:
                try:
                    message = await anext(receiver)
                except StopAsyncIteration:
                    break

                text = _input_transcription_text(message)
                if text:
                    transcriptions.append(text)
                combined = " ".join(transcriptions).strip()
                if (
                    combined
                    and _transcription_overlap(stimulus.spoken_text, combined) >= 0.35
                ):
                    qualified = True
                    break
        finally:
            close = getattr(receiver, "aclose", None)
            if callable(close):
                await close()

        if qualified:
            break

    combined = " ".join(transcriptions).strip()
    if not combined:
        raise RuntimeError(
            f"Gemini Live produced no calibration transcription for "
            f"{stimulus.interaction_class} floor stimulus"
        )
    overlap = validate_calibration_transcript(
        stimulus.spoken_text,
        combined,
        interaction_class=stimulus.interaction_class,
    )
    return {
        "case_id": stimulus.case_id,
        "interaction_class": stimulus.interaction_class,
        "expected_text": stimulus.spoken_text,
        "byte_length": len(pcm),
        "content_sha256": content_sha256,
        "input_transcription": combined,
        "transcription_overlap": round(overlap, 6),
    }


async def exercise_floor_episode(
    session: Any,
    capture: Any,
    types_module: Any,
    *,
    stimulus: FloorStimulus,
    pcm: bytes,
    now_ms: Callable[[], int],
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    max_receive_cycles: int = 3,
) -> dict[str, Any]:
    """Inject one calibrated speech class while Gemini is audibly holding the floor.

    The semantic class and exact PCM identity are independently qualified by
    calibrate_floor_stimulus before scoring. The yielded-floor value comes only
    from Gemini's native interruption signal. Runtime transcription is retained
    when present but is not required a second time for the same calibrated PCM.
    """

    if max_receive_cycles < 1:
        raise ValueError("max_receive_cycles must be positive")

    prompt_time = int(now_ms())
    capture.record_client_content(
        at_ms=prompt_time,
        text=MODEL_PROMPT,
        turn_complete=True,
    )
    await session.send_client_content(
        turns={"role": "user", "parts": [{"text": MODEL_PROMPT}]},
        turn_complete=True,
    )

    injected = False
    interrupted = False
    input_transcripts: list[str] = []
    injection_time_ms: int | None = None
    content_sha256 = hashlib.sha256(pcm).hexdigest()

    for cycle_index in range(max_receive_cycles):
        async for message in session.receive():
            at_ms = int(now_ms())
            capture.record_server_message(message, at_ms=at_ms)

            if not injected and _model_audio_present(message):
                injection_time_ms = at_ms
                capture.record_client_realtime_input(
                    at_ms=injection_time_ms,
                    kind="audio",
                    mime_type="audio/pcm;rate=16000",
                    byte_length=len(pcm),
                    text=stimulus.spoken_text,
                    content_sha256=content_sha256,
                )
                await _send_pcm_realtime(
                    session,
                    types_module,
                    pcm,
                    sleep=sleep,
                )
                injected = True

            if injected:
                transcript = _input_transcription_text(message)
                if transcript:
                    input_transcripts.append(transcript)

                content = _get(message, "server_content")
                if (
                    cycle_index == 0
                    and content is not None
                    and bool(_get(content, "interrupted", False))
                ):
                    interrupted = True

        if not injected:
            raise RuntimeError(
                "Gemini Live completed the model turn before floor stimulus injection"
            )
        break

    combined_transcript = " ".join(input_transcripts).strip()

    overlap = _transcription_overlap(stimulus.spoken_text, combined_transcript)

    floor_time = int(now_ms())
    capture.record_floor(
        interaction_class=stimulus.interaction_class,
        yielded_floor=interrupted,
        at_ms=floor_time,
    )
    return {
        "interaction_class": stimulus.interaction_class,
        "expected_yielded_floor": stimulus.expected_yielded_floor,
        "yielded_floor": interrupted,
        "input_transcription": combined_transcript,
        "transcription_overlap": round(overlap, 6),
        "content_sha256": content_sha256,
        "injection_time_ms": injection_time_ms,
    }


async def run_authenticated_floor_probe(
    *,
    api_key: str,
    stimulus_dir: Path,
    output: Path,
    model: str = DEFAULT_MODEL,
    episode_timeout_s: float = 35.0,
) -> Path:
    """Run all four canonical floor stimuli in one authenticated Live session."""

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError(
            "Gemini Live runtime requires the optional 'live' dependency"
        ) from exc

    payloads: dict[str, bytes] = {}
    for stimulus in FLOOR_STIMULI:
        path = stimulus_dir / stimulus.filename
        if not path.exists():
            raise RuntimeError(f"missing floor stimulus: {path}")
        pcm = path.read_bytes()
        if not pcm:
            raise RuntimeError(f"empty floor stimulus: {path}")
        payloads[stimulus.interaction_class] = pcm

    client = genai.Client(api_key=api_key)
    started_ns = time.monotonic_ns()

    def now_ms() -> int:
        return int((time.monotonic_ns() - started_ns) / 1_000_000)

    config = {
        "response_modalities": ["AUDIO"],
        "input_audio_transcription": {},
        "output_audio_transcription": {},
        "system_instruction": (
            "Respond naturally to the user's conversation. "
            "When explicitly asked to count, count slowly and continuously. "
            "Do not treat this instruction as guidance about interruptions."
        ),
    }
    calibration_config = {
        "response_modalities": ["AUDIO"],
        "input_audio_transcription": {},
        "realtime_input_config": {
            "automatic_activity_detection": {
                "disabled": True,
            }
        },
        "system_instruction": (
            "This session is only validating incoming speech intelligibility. "
            "Listen to each explicitly bounded utterance without changing its meaning."
        ),
    }

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        calibration_path = output.parent / "calibration.json"
        calibration_results: list[dict[str, Any]] = []
        for stimulus in FLOOR_STIMULI:
            async with client.aio.live.connect(
                model=model,
                config=calibration_config,
            ) as calibration_session:
                result = await asyncio.wait_for(
                    calibrate_floor_stimulus(
                        calibration_session,
                        types,
                        stimulus=stimulus,
                        pcm=payloads[stimulus.interaction_class],
                    ),
                    timeout=episode_timeout_s,
                )
            calibration_results.append(result)
            calibration_path.write_text(
                json.dumps(calibration_results, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(
                "NVIQ Gemini Live calibration "
                f"class={result['interaction_class']} "
                f"overlap={result['transcription_overlap']} "
                f"sha256={result['content_sha256']} "
                f"transcript={result['input_transcription']!r}"
            )

        sessions: list[dict[str, Any]] = []
        for stimulus in FLOOR_STIMULI:
            async with client.aio.live.connect(model=model, config=config) as session:
                session_id = (
                    getattr(session, "session_id", None)
                    or getattr(session, "_session_id", None)
                    or f"provider-session-id-unavailable-{stimulus.interaction_class}"
                )
                capture = GeminiLiveRuntimeCapture(
                    case_id=stimulus.case_id,
                    session_id=str(session_id),
                    model=model,
                    track="audio_native",
                    audio_ref=(
                        "runtime://gemini-live-floor-synthesized-speech/"
                        + stimulus.interaction_class
                    ),
                )
                result = await asyncio.wait_for(
                    exercise_floor_episode(
                        session,
                        capture,
                        types,
                        stimulus=stimulus,
                        pcm=payloads[stimulus.interaction_class],
                        now_ms=now_ms,
                    ),
                    timeout=episode_timeout_s,
                )
                print(
                    "NVIQ Gemini Live floor "
                    f"class={result['interaction_class']} "
                    f"yielded={result['yielded_floor']} "
                    f"expected={result['expected_yielded_floor']} "
                    f"overlap={result['transcription_overlap']} "
                    f"sha256={result['content_sha256']} "
                    f"transcript={result['input_transcription']!r}"
                )
                sessions.append(capture.session_record())

        manifest = {
            "trace_version": TRACE_VERSION,
            "default_track": "audio_native",
            "model": model,
            "capture_origin": "runtime",
            "sessions": sessions,
        }
        output.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return output
    finally:
        client.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run authenticated Gemini Live Conversational Floor Integrity"
    )
    parser.add_argument("--stimulus-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--episode-timeout", type=float, default=35.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    path = asyncio.run(
        run_authenticated_floor_probe(
            api_key=resolve_api_key(),
            stimulus_dir=args.stimulus_dir,
            output=args.output,
            model=args.model,
            episode_timeout_s=args.episode_timeout,
        )
    )
    print(f"NVIQ Gemini Live authenticated floor trace: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
