# Realtime-Venus-Audio NVIQ adapter

Status: **adapter qualified / runtime benchmark pending**

Pinned upstream source for this adapter tranche:

- Repository: `inclusionAI/Realtime-Venus`
- Commit: `e53ae8d5bde92b30364b26f2e4c13c9db7a8ffea`
- Upstream license: Apache-2.0 for the released source, subject to the repository's separate notices.

## Why this target

Realtime-Venus-Audio is a public audio-native full-duplex checkpoint with a streaming example that feeds one-second audio chunks through `as_duplex()`. The upstream runtime exposes whether a chunk is in listen/speak mode and its generated text/audio. The companion Harness exposes frozen request context, asynchronous work state, result delivery and playback acknowledgment primitives.

Those properties make it relevant to NVIQ's priority speech-cognition lanes:

- Conversational Floor Integrity
- Request-Boundary Evidence Freeze / ACCI
- Result-delivery provenance
- Speaker-State Preservation
- Long-Silence Continuity
- Acoustic Evidence Fabrication Rate / causal consequence

## Evidence boundary

NVIQ does **not** infer benchmark semantics from weak provider signals.

For example, a Venus `is_listen=true` chunk is retained in provenance but is **not** automatically interpreted as a backchannel, background speech, or genuine interruption. Those labels require explicit benchmark instrumentation or independently grounded annotations.

The adapter therefore has two event layers:

### Native provenance events

- `venus.duplex_chunk` — preserves chunk time/index, listen state and emitted text.
- `venus.harness_event` — preserves Harness lifecycle observations such as request cutoff, completion, delivery admission and playback acknowledgment.

These events are evidence, not NVIQ scores.

### Explicit NVIQ capture events

- `nviq.floor`
- `nviq.silence`
- `nviq.speaker_state`
- `nviq.async_task`
- `nviq.causal_event`

These carry the machine-verifiable facts needed by the corresponding NVIQ evaluator. If required instrumentation is absent, the execution path fails closed rather than manufacturing evidence.

Provider traces are forbidden from injecting fields such as `score`, `metrics`, `passed`, `verdict`, hard-gate counts or catastrophic-failure lists.

## Request-boundary mapping

The upstream Harness already freezes a `ContextSnapshot` at delegate capture with `cutoff_ms` and `cutoff_sequence`. For NVIQ runtime capture, the integration shim should record:

1. **authorized** — the delegate opening/cutoff instant and evidence available at that boundary;
2. **prepared** — terminal work result / prepared reply available;
3. **returned** — result queued back to the originating conversation;
4. **accepted or rejected** — delivery admission decision;
5. **committed** — private result admitted to the conversational model for response generation;
6. **spoken** — associated playback actually acknowledged.

Accepted and rejected are mutually exclusive in NVIQ result-delivery provenance.

## Runtime capture shim

NVIQ now includes a dependency-free `RealtimeVenusRuntimeCapture` helper. It is designed to be called from a Realtime-Venus integration without importing Venus internals into NVIQ.

```python
from nviq.adapters import RealtimeVenusRuntimeCapture

capture = RealtimeVenusRuntimeCapture(
    case_id="NVIQ-VENUS-ASYNC-001",
    session_id=session_id,
    source_commit="e53ae8d5bde92b30364b26f2e4c13c9db7a8ffea",
    audio_ref=audio_ref,
)

# At Harness delegate capture:
capture.record_context_snapshot(
    context_snapshot,
    work_id=work_id,
    evidence_times_at_authorization=evidence_times_ms,
)

# At the corresponding result lifecycle transitions:
capture.mark_async_transition(work_id=work_id, transition="prepared", at_ms=prepared_ms)
capture.mark_async_transition(work_id=work_id, transition="returned", at_ms=returned_ms)
capture.mark_async_transition(work_id=work_id, transition="accepted", at_ms=accepted_ms)
capture.mark_async_transition(work_id=work_id, transition="committed", at_ms=committed_ms)
capture.mark_async_transition(work_id=work_id, transition="spoken", at_ms=playback_ack_ms)

capture.write_manifest(output_path)
```

The shim also records native duplex chunks, Harness events, floor annotations, silence continuity, speaker-state observations and Causal Speech Ledger events. It does not rewrite contradictory or contaminated evidence. If the runtime records both accepted and rejected, or includes post-boundary evidence in a request snapshot, the trace preserves that state so NVIQ can fail it.

`record_context_snapshot()` uses duck typing for the upstream `ContextSnapshot` fields `session_id`, `snapshot_id`, `cutoff_ms` and `cutoff_sequence`. A session mismatch fails closed.

## Adapter-contract qualification

The repository fixture at
`examples/realtime-venus/adapter-contract-trace-manifest.json`
is deliberately marked `capture_origin=adapter_contract_fixture`.

It validates conversion and scoring behavior only. It is **not** evidence of Realtime-Venus-Audio model performance.

Run it with:

```bash
nviq ingest realtime-venus \
  --cases cases/v0.2/realtime-venus-adapter-p0.json \
  --trace-manifest examples/realtime-venus/adapter-contract-trace-manifest.json \
  --output /tmp/realtime-venus-evidence.json

nviq execute \
  --manifest examples/audit/realtime-venus-adapter-p0-manifest.json \
  --evidence /tmp/realtime-venus-evidence.json \
  --output-dir /tmp/realtime-venus-adapter-audit
```

The fixture includes one deliberately fabricated-acoustic-evidence case so the resulting audit is expected to contain a critical finding. That demonstrates the detector path; it is not a vendor result.

## Runtime qualification gate

Do not mark Realtime-Venus-Audio as NVIQ-verified until a real checkpoint run produces captured evidence from compatible GPU infrastructure.

The pinned upstream documentation requires Python 3.10, CUDA and FFmpeg for standalone Audio inference and loads the model in bfloat16 on CUDA. Its online full-duplex demo documentation calls for at least one NVIDIA A100 GPU.

Until an authentic runtime trace is captured and passed through NVIQ, the target status remains:

`adapter_qualified_runtime_pending`

## Runtime qualification receipt

After a real runtime capture has been ingested and executed, NVIQ can issue a deterministic qualification receipt:

```bash
nviq execute \
  --manifest examples/audit/realtime-venus-runtime-p0-manifest.json \
  --evidence runtime-captured-evidence.json \
  --output-dir out/realtime-venus-runtime

nviq qualify realtime-venus \
  --cases cases/v0.2/realtime-venus-adapter-p0.json \
  --evidence runtime-captured-evidence.json \
  --execution-dir out/realtime-venus-runtime \
  --output out/realtime-venus-runtime/qualification-receipt.json
```

The gate rejects adapter fixtures and requires all of the following:

- `capture_origin=runtime`;
- provider `inclusionAI` and model `Realtime-Venus-Audio-9B`;
- the pinned upstream source repository and commit;
- non-empty runtime session and audio references;
- exact coverage of all five priority benchmark families;
- successful NVIQ execution for every case;
- no catastrophic failures or hard-gate failures;
- passing floor, silence, async-boundary/result-delivery, speaker-state and AEFR/causal metrics;
- an audit manifest explicitly identifying the runtime environment and pinned target version.

The receipt includes a SHA-256 fingerprint over the cases, evidence, derived observations and audit report. A rejected bundle still produces a receipt with explicit reasons and a non-zero CLI exit code.
