from __future__ import annotations

import argparse
import asyncio
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .adapters.gemini_live import DEFAULT_MODEL
from .adapters.gemini_live_capture import GeminiLiveRuntimeCapture


PROMPT = (
    "For this NVIQ benchmark, call lookup_schedule exactly once with day Monday. "
    "Do not invent the result; wait for the tool response, then tell me the returned slot."
)


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _function_calls(message: Any) -> list[Any]:
    tool_call = _get(message, "tool_call")
    if tool_call is None:
        return []
    return list(_get(tool_call, "function_calls", []) or [])


def _has_spoken_output(message: Any) -> bool:
    content = _get(message, "server_content")
    if content is None:
        return False
    transcription = _get(content, "output_transcription")
    if transcription is not None and str(_get(transcription, "text", "")).strip():
        return True
    return _get(content, "model_turn") is not None


async def exercise_async_tool_session(
    session: Any,
    capture: Any,
    types_module: Any,
    *,
    now_ms: Callable[[], int],
) -> dict[str, Any]:
    """Exercise one real Gemini Live async tool round trip and capture its lifecycle."""

    prompt_time = int(now_ms())
    capture.record_client_content(at_ms=prompt_time, text=PROMPT, turn_complete=True)
    await session.send_client_content(
        turns={"role": "user", "parts": [{"text": PROMPT}]},
        turn_complete=True,
    )

    observed_times = [prompt_time]
    work_id: str | None = None
    authorized_time_ms: int | None = None
    accepted = committed = spoken = False

    complete = False
    while not complete:
        async for message in session.receive():
            at_ms = int(now_ms())
            capture.record_server_message(message, at_ms=at_ms)
            observed_times.append(at_ms)

            calls = _function_calls(message)
            if calls and work_id is None:
                fc = calls[0]
                work_id = str(_get(fc, "id") or "")
                name = str(_get(fc, "name") or "")
                if not work_id or name != "lookup_schedule":
                    raise RuntimeError("Gemini Live returned an unexpected benchmark tool call")

                authorized_time_ms = at_ms
                capture.begin_async_task(
                    work_id=work_id,
                    authorized_time_ms=authorized_time_ms,
                    evidence_times_at_authorization=[
                        value for value in observed_times if value <= authorized_time_ms
                    ],
                )

                prepared_ms = int(now_ms())
                capture.mark_async_transition(
                    work_id=work_id,
                    transition="prepared",
                    at_ms=prepared_ms,
                )

                result = {"available_slot": "10:00", "day": "Monday"}
                returned_ms = int(now_ms())
                capture.mark_async_transition(
                    work_id=work_id,
                    transition="returned",
                    at_ms=returned_ms,
                )
                capture.record_tool_response(
                    work_id=work_id,
                    at_ms=returned_ms,
                    response=result,
                )

                function_response = types_module.FunctionResponse(
                    id=work_id,
                    name=name,
                    response={
                        "result": result,
                        "scheduling": "WHEN_IDLE",
                    },
                )
                await session.send_tool_response(function_responses=function_response)

                accepted_ms = int(now_ms())
                capture.mark_async_transition(
                    work_id=work_id,
                    transition="accepted",
                    at_ms=accepted_ms,
                )
                accepted = True
                continue

            if work_id is not None and accepted and _get(message, "server_content") is not None:
                if _has_spoken_output(message):
                    if not committed:
                        capture.mark_async_transition(
                            work_id=work_id,
                            transition="committed",
                            at_ms=at_ms,
                        )
                        committed = True
                    if not spoken:
                        capture.mark_async_transition(
                            work_id=work_id,
                            transition="spoken",
                            at_ms=at_ms,
                        )
                        spoken = True

                content = _get(message, "server_content")
                if committed and spoken and bool(_get(content, "turn_complete", False)):
                    complete = True
                    break

        if complete:
            break
        if work_id is None:
            raise RuntimeError("Gemini Live did not issue the required lookup_schedule tool call")

    if work_id is None or authorized_time_ms is None:
        raise RuntimeError("Gemini Live did not issue the required lookup_schedule tool call")
    if not (accepted and committed and spoken):
        raise RuntimeError(
            "Gemini Live tool result did not complete the required delivery lifecycle"
        )

    capture.flush_async_task(work_id)
    return {
        "work_id": work_id,
        "authorized_time_ms": authorized_time_ms,
    }


def resolve_api_key() -> str:
    value = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not value:
        raise RuntimeError(
            "Gemini API key is not configured; set GEMINI_API_KEY or GOOGLE_API_KEY"
        )
    return value


async def run_authenticated_async_probe(
    *,
    api_key: str,
    output: Path,
    model: str = DEFAULT_MODEL,
    timeout_s: float = 45.0,
) -> Path:
    """Run the authenticated Gemini Live async lane and write a runtime trace manifest."""

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError(
            "Gemini Live runtime requires the optional 'live' dependency"
        ) from exc

    client = genai.Client(api_key=api_key)
    started_ns = time.monotonic_ns()

    def now_ms() -> int:
        return int((time.monotonic_ns() - started_ns) / 1_000_000)

    config = {
        "response_modalities": ["AUDIO"],
        "output_audio_transcription": {},
        "system_instruction": (
            "You are executing an automated NVIQ runtime benchmark. "
            "Follow the user's explicit tool instruction exactly and do not fabricate tool results."
        ),
        "tools": [{
            "function_declarations": [{
                "name": "lookup_schedule",
                "description": "Returns one deterministic benchmark schedule slot.",
                "behavior": "NON_BLOCKING",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "day": {"type": "STRING"},
                    },
                    "required": ["day"],
                },
            }],
        }],
    }

    try:
        async with client.aio.live.connect(model=model, config=config) as session:
            session_id = (
                getattr(session, "session_id", None)
                or getattr(session, "_session_id", None)
                or "provider-session-id-unavailable"
            )
            capture = GeminiLiveRuntimeCapture(
                case_id="NVIQ-GEMINI-ASYNC-001",
                session_id=str(session_id),
                model=model,
                track="audio_native",
                audio_ref="runtime://gemini-live-async-tool-roundtrip",
            )
            await asyncio.wait_for(
                exercise_async_tool_session(
                    session,
                    capture,
                    types,
                    now_ms=now_ms,
                ),
                timeout=timeout_s,
            )
            return capture.write_manifest(output)
    finally:
        client.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the authenticated NVIQ Gemini Live async runtime probe"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=float, default=45.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    path = asyncio.run(
        run_authenticated_async_probe(
            api_key=resolve_api_key(),
            output=args.output,
            model=args.model,
            timeout_s=args.timeout,
        )
    )
    print(f"NVIQ Gemini Live authenticated runtime trace: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
