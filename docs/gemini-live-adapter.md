# Gemini Live Adapter v0.1

NVIQ's Gemini Live adapter converts captured Gemini Live provider events plus explicit NVIQ runtime instrumentation into the provider-neutral Evidence Bundle v0.1 contract.

## Current target

The adapter targets `gemini-3.8-live`, Google's generally available Live API model released in September 2026.

Official references:

- https://ai.google.dev/gemini-api/docs/models/gemini-3.8-live
- https://ai.google.dev/api/live
- https://ai.google.dev/gemini-api/docs/live-api/best-practices
- https://googleapis.github.io/python-genai/genai.html

## Evidence boundary

Gemini-native events are facts, not NVIQ scores.

NVIQ preserves these provider signals as provenance:

- `server_content.interrupted`
- input/output transcription
- turn-completion and generation-completion state
- model-turn payloads
- realtime input metadata
- function calls and function responses

The adapter does **not** infer a benchmark judgment from those fields. In particular, `interrupted=true` proves that model generation was interrupted; it does not prove whether the incoming speech was a genuine interruption, a backchannel, other-directed speech, or background speech.

Likewise, Gemini function-call timing does not by itself prove Request-Boundary Evidence Freeze or Result Delivery Provenance. Those facts must be captured explicitly as `nviq.async_task` evidence.

This separation prevents a provider adapter from becoming a second scorer.

## Why ordering is captured explicitly

Google documents `send_realtime_input` as responsiveness-oriented rather than deterministically ordered, and input transcription can arrive independently from other server messages. NVIQ therefore records event identity and timing without reconstructing a cleaner chronology than the runtime actually exposed.

The request boundary used by an asynchronous task must be frozen by the host integration at authorization time. Later evidence must never be retroactively inserted into that task's authorization context.

## Runtime capture

`GeminiLiveRuntimeCapture` is dependency-free. A host using the Google Gen AI SDK can pass received SDK objects directly into the capture shim without making NVIQ itself depend on `google-genai`.

Typical integration shape:

```python
capture.record_client_realtime_input(
    at_ms=clock_ms(),
    kind="audio",
    mime_type="audio/pcm;rate=16000",
    byte_length=len(chunk),
)

async for message in session.receive():
    capture.record_server_message(message, at_ms=clock_ms())
```

When a tool call is authorized, the host records the immutable evidence times used for that request:

```python
capture.begin_async_task(
    work_id=call_id,
    authorized_time_ms=authorization_ms,
    evidence_times_at_authorization=evidence_times,
)
```

Lifecycle transitions are then captured as the result moves through:

```text
prepared -> returned -> accepted/rejected -> committed -> spoken
```

The host can flag any future-knowledge contamination with `mark_retroactive_evidence()`.

## Adapter-contract qualification

The repository includes a deterministic fixture covering the current Gemini frontier lanes:

- Conversational Floor Integrity
- asynchronous future-knowledge contamination resistance
- Request-Boundary Evidence Freeze
- Result Delivery Provenance

Run:

```bash
nviq ingest gemini-live \
  --cases cases/v0.2/gemini-live-adapter-p0.json \
  --trace-manifest examples/gemini-live/adapter-contract-trace-manifest.json \
  --output out/gemini-live-evidence.json

nviq execute \
  --manifest examples/audit/gemini-live-adapter-p0-manifest.json \
  --evidence out/gemini-live-evidence.json \
  --output-dir out/gemini-live-adapter-audit
```

The bundled trace is an **adapter-contract fixture**, not a Gemini model-performance result.

## Authenticated runtime probe

The GitHub-only runtime probe exercises a real Gemini 3.8 Live WebSocket session with a deterministic asynchronous function call. It freezes evidence at tool authorization, records the tool lifecycle, waits for provider output after the result is returned, and emits a runtime trace with `capture_origin=runtime`.

The probe is intentionally one-shot. It is triggered only from `run/gemini-live-runtime` or manually through the workflow and accepts the API key from either `GEMINI_API_KEY` or `GOOGLE_API_KEY`. The secret value is never written into evidence or logs.

A passing async runtime probe qualifies only the asynchronous request-boundary/result-delivery lane. Conversational Floor Integrity still requires real audio interruption scenarios and remains independently gated.

## Runtime gate

The provider target remains `adapter_qualified_provider_runtime_pending` until authentic provider evidence clears the required runtime lanes. Vendor documentation or deterministic fixtures are never promoted to runtime qualification results.

## Authenticated Conversational Floor Integrity probe

The automated floor probe sends real 16 kHz, 16-bit PCM speech into an authenticated Gemini Live session while the model is actively producing audio. Four canonical classes are exercised in independent authenticated provider sessions, in this order:

1. background speech — should not seize the floor;
2. other-directed speech — should not seize the floor;
3. backchannel — should not seize the floor;
4. genuine interruption — should cause Gemini to yield.

The speech fixtures are generated independently with espeak-ng, converted with ffmpeg, and are not produced by Gemini. The host supplies the known stimulus class; Gemini's native server_content.interrupted signal supplies the observed yield behavior.

Before floor scoring, NVIQ sends each exact PCM clip in its own idle Gemini session with automatic activity detection disabled and explicit activity-start/activity-end boundaries, then requires at least 35% lexical overlap in Gemini's input transcription. The calibration record stores the PCM byte length and SHA-256. The identical SHA-pinned bytes are then reused during the overlapping floor test with Gemini's default automatic activity detection restored.

Raw model audio is not written into the evidence bundle. Binary payloads are represented by byte length and SHA-256 so runtime evidence remains compact and reproducible.

Each floor class uses a fresh provider session so an interruption in one scenario cannot contaminate the next. Interim and final input-transcription evidence are preserved for diagnostics during overlap, but fragmentary overlap transcription does not invalidate a floor result after the exact PCM stimulus has passed idle calibration. A floor episode still fails closed if Gemini exposes neither transcription nor an interruption signal.

This probe qualifies an automated synthesized-speech runtime lane, not broad human conversational performance. Natural-speaker, multi-speaker, accent, noisy-room and device-microphone coverage remain separate benchmark expansions.

Gemini Live's documented default automatic-activity policy is START_OF_ACTIVITY_INTERRUPTS: detected user activity interrupts model generation. NVIQ keeps that default unchanged for this benchmark. Therefore a background-speech or backchannel interruption is recorded as a provider behavior finding, not tuned away by changing VAD policy.

Calibration exits as soon as sufficient input-transcription evidence is observed; it does not require a model response or turn-complete event. This matters for short backchannels, which may be transcribed without eliciting a reply.


## Authenticated floor result — 2026-09-28

GitHub Actions run `36433099081` completed the authenticated synthesized-speech P0 floor tranche against `gemini-3.8-live`. All four exact PCM stimuli passed independent intelligibility calibration before scoring.

Observed provider behavior:

- background speech: yielded floor = true — failed;
- other-directed speech: yielded floor = false — passed;
- backchannel: yielded floor = true — failed;
- genuine interruption: yielded floor = false — failed.

NVIQ result: mean score `0.25`, three hard-gate failures, three catastrophic `conversational_floor_integrity_failure` findings, overall audit status `critical`.

This is a valid failed target qualification, not a harness failure. The evidence indicates that Gemini Live's native interruption signal must not be treated as the authoritative semantic floor policy. The canonical P0 remediation is `NVIQ-R-FLOOR-001`: explicit CVF/CSC floor-state arbitration ahead of provider VAD/interruption behavior.

The authenticated async/tool lane remains qualified. The Gemini frontier target is therefore recorded as `runtime_partial_qualified_floor_failed`, not fully runtime-qualified.
