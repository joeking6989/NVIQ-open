# NVIQ OpenAI Realtime Adapter v0.1

The OpenAI Realtime adapter converts captured OpenAI Realtime event streams into NVIQ Evidence Bundle v0.1 records. It is an ingestion boundary, not a scorer: the adapter preserves observable facts and runtime instrumentation, then the NVIQ Execution Engine independently derives metrics, hard gates, catastrophic failures, findings and remediation mappings.

## Product flow

```text
OpenAI Realtime events / JSONL
        |
        v
OpenAI Realtime Adapter v0.1
        |
        v
Evidence Bundle v0.1
        |
        v
NVIQ Execution Engine
        |
        v
v0.2 scorer + hard gates
        |
        v
Reliability Audit
```

## Supported inputs

The adapter accepts either:

1. one JSON or JSONL event stream for one benchmark case; or
2. a trace manifest containing multiple benchmark sessions, each with inline events or an `events_path` relative to the manifest.

### Single trace

```bash
nviq ingest openai-realtime \
  --cases cases/v0.2/executable-p0.json \
  --case-id NVIQ-ABSTAIN-001 \
  --events captured/abstention.jsonl \
  --track audio_native \
  --capture-origin runtime \
  --output out/openai-evidence.json
```

`--capture-origin` is required for single-trace ingestion: use `runtime` for traces captured from a live session and `adapter_contract_fixture` for hand-built traces.

### Multi-case trace manifest

```bash
nviq ingest openai-realtime \
  --cases cases/v0.2/executable-p0.json \
  --trace-manifest examples/openai-realtime/p0-trace-manifest.json \
  --output out/openai-p0-evidence.json
```

A trace manifest must declare a top-level `capture_origin` (a session may override it). There is no default, so an unlabelled fixture can never be read as runtime evidence. The value is recorded at `provenance.configuration.capture_origin` on every evidence record.

Then execute the audit:

```bash
nviq execute \
  --manifest examples/audit/openai-realtime-p0-manifest.json \
  --evidence out/openai-p0-evidence.json \
  --output-dir out/openai-p0-audit
```

## Standard OpenAI evidence

The adapter currently recognizes observable Realtime events including:

- `conversation.item.input_audio_transcription.completed` for finalized input transcription and optional transcription logprobs;
- `input_audio_buffer.speech_started` and `input_audio_buffer.speech_stopped` for captured speech timing;
- `response.output_audio_transcript.done` and `response.output_text.done` for finalized assistant output text;
- `conversation.item.truncated` for interrupted/truncated assistant audio state;
- `response.function_call_arguments.done` for completed function-call arguments;
- `conversation.item.created` containing `function_call_output` for tool-result evidence;
- `response.done` for terminal response status;
- `session.created` and `session.updated` for session/model provenance.

All captured event IDs are retained as evidence references when present. Events without IDs receive deterministic synthetic references derived from their stream position and event type.

## Confidence boundary

OpenAI input-audio transcription logprobs are preserved as **ASR/transcription confidence only** in adapter provenance.

They are not promoted into NVIQ's authoritative decision, entity, intent or action confidence. Those confidence states must come from explicit runtime instrumentation when a benchmark family requires them.

This prevents a strong transcript probability from being misrepresented as strong cognitive/action certainty.

## Runtime sidecar evidence

Some NVIQ properties are not directly observable from the standard Realtime event stream. The test/runtime can emit a local instrumentation event:

```json
{
  "type": "nviq.evidence",
  "event_id": "nviq-runtime-17",
  "evidence": {
    "confidence": {
      "authoritative": 0.55,
      "expressed": 0.55,
      "action_mode": "clarify"
    }
  }
}
```

Allowed sections are the canonical Evidence Bundle sections:

- `message`
- `confidence`
- `alternatives`
- `action`
- `shared_state`
- `prior`
- `context_retrieval`
- `turn`

The sidecar may report facts and state. It cannot provide benchmark scores or bypass the canonical scorer.

## Fail-closed policy

The adapter does not infer unsupported cognitive state from weak proxies. If a benchmark family requires a field that is not present in standard Realtime events or explicit runtime sidecar evidence, the adapter omits that evidence section. The Execution Engine then marks the case as failed due to missing required evidence/metrics instead of manufacturing a passing value.

Examples:

- speech-start/stop timing alone does not prove `listener_backchannel` versus `holds_floor`;
- function-call events alone do not prove whether the spoken success claim was truthful without tool-result and claim state;
- transcription logprobs do not prove authoritative action confidence;
- assistant text generation alone does not prove the human actually heard it after playback interruption.

## Qualification fixture

`examples/openai-realtime/p0-trace-manifest.json` is a sanitised eight-session qualification fixture covering:

1. Confidence-Channel Fidelity
2. Uncertainty Fidelity
3. Abstention Fidelity
4. State-Speech Consistency
5. Shared-State Integrity
6. Prior-Contamination Resistance
7. Turn-State / Floor-State Cognition
8. Context Transformation Integrity

It is test data, not customer evidence and not a claim about live OpenAI model performance. It is labelled `"capture_origin": "adapter_contract_fixture"`, and CI asserts that label on every ingested record.

The corresponding audit manifest is `examples/audit/openai-realtime-p0-manifest.json`.

## Data handling

The adapter reads local JSON/JSONL traces and emits local Evidence Bundle JSON. It does not upload customer traces, persist API keys, or retain raw audio by itself. Audio references are provenance pointers only unless another acquisition component explicitly stores audio.

## Provider neutrality

OpenAI-specific parsing remains isolated under `src/nviq/adapters/`. The canonical Evidence Bundle, Execution Engine, scorer, hard gates, findings and commercial audit remain provider-neutral. Additional providers should emit the same Evidence Bundle contract rather than introducing provider-specific scoring logic.
