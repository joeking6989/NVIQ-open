# NVIQ Execution Engine v0.1

The Execution Engine is the product layer that converts raw voice-agent interaction evidence into NVIQ measurements. It exists so a customer does **not** need to calculate NVIQ metrics before Noct-Tech can audit their system.

## Product flow

```text
raw interaction evidence
        |
        v
Evidence Bundle v0.1
        |
        v
deterministic NVIQ evaluators
        |
        v
derived-observations.json
        |
        v
NVIQ v0.2 scorer / hard gates
        |
        v
Reliability Audit v0.1
        |
        +--> audit-report.json
        +--> audit-report.html
        +--> regression-snapshot.json
```

The raw evidence artifact and the derived observation artifact are intentionally separate. An adapter may report facts about its execution, but it cannot assign itself an NVIQ score.

## Evidence Bundle v0.1

Schema: `src/nviq/schemas/evidence-bundle.v0.1.schema.json` (bundled with the package)

One record represents one benchmark case on one NVIQ track.

```json
{
  "evidence_version": "0.1",
  "case_id": "NVIQ-STATE-001",
  "track": "lsr_cvf",
  "action": {
    "requested": true,
    "execution_status": "failed",
    "spoken_claim": "failure"
  },
  "provenance": {
    "evidence_refs": ["trace-44"],
    "session_id": "session-9",
    "audio_ref": "customer://recording/9.wav"
  }
}
```

Evidence sections are sparse. A case only needs the evidence required by its evaluator.

Supported sections:

- `message` — message presence, lexical output, abstention and correctness state;
- `confidence` — authoritative confidence, expressed confidence and observed action policy;
- `alternatives` — candidate hypotheses retained by the target;
- `action` — requested action, actual execution state and spoken completion claim;
- `shared_state` — context IDs used versus context actually playback-grounded to the human;
- `prior` — prior-blind current state, contextual state and historical prior distributions;
- `context_retrieval` — decisive evidence recovery, provenance, latency and stale-summary state;
- `turn` — predicted floor state;
- `provenance` — stable evidence/session/audio/model references.

Raw audio may be referenced by URI/path/evidence ID. NVIQ core does not silently copy or retain it.

## Validate evidence

```bash
nviq evidence validate \
  --evidence examples/evidence/p0-executable.json \
  --cases cases/v0.2/executable-p0.json
```

## Execute an audit from raw evidence

```bash
nviq execute \
  --manifest examples/audit/executable-p0-manifest.json \
  --evidence examples/evidence/p0-executable.json \
  --output-dir out/execution-p0
```

Expected artifacts:

```text
out/execution-p0/
  derived-observations.json
  evidence-summary.json
  audit-report.json
  audit-report.html
  regression-snapshot.json
```

`derived-observations.json` is the boundary between the Execution Engine and the canonical v0.2 benchmark scorer.

## Live HTTP target protocol

The first live adapter is intentionally generic. A target endpoint receives one benchmark case at a time.

NVIQ request:

```http
POST /nviq
Content-Type: application/json
Authorization: Bearer <runtime token, when configured>
```

```json
{
  "protocol_version": "0.1",
  "track": "lsr_cvf",
  "case": {
    "case_id": "NVIQ-ABSTAIN-001",
    "family": "abstention_fidelity"
  }
}
```

The real request contains the complete selected benchmark case.

The target returns **raw evidence**, not scores:

```json
{
  "evidence_version": "0.1",
  "case_id": "NVIQ-ABSTAIN-001",
  "track": "lsr_cvf",
  "message": {
    "presence_probability": 0.02,
    "lexical_output": null,
    "abstained": true
  },
  "provenance": {
    "evidence_refs": ["session-77/audio-segment-4"]
  }
}
```

Run it with:

```bash
export NVIQ_TARGET_BEARER_TOKEN='runtime-secret'

nviq target run \
  --manifest examples/audit/executable-p0-manifest.json \
  --endpoint https://voice-agent.example/internal/nviq \
  --output-dir out/live-target
```

If the target returns the wrong `case_id` or `track`, NVIQ rejects the response rather than attributing evidence to the wrong benchmark scenario.

## Executable benchmark families

`cases/v0.2/executable-p0.json` covers:

1. Uncertainty Fidelity
2. Abstention Fidelity
3. State-Speech Consistency
4. Shared-State Integrity
5. Prior-Contamination Resistance
6. Turn-State / Floor-State Cognition
7. Confidence-Channel Fidelity
8. Context Transformation Integrity (P1 extension)

The reference evidence bundle is deliberately green. Tests separately inject failures to prove the evaluators detect confidence inflation, entity overcommit, fabricated speech, false tool-completion claims, unheard-context dependency, prior contamination, false floor seizure and irreversible context-evidence loss.

## What is independent and what is supplied

NVIQ independently derives benchmark metrics, hard gates, catastrophic failures, findings and remediation mappings.

A target/export supplies observable facts and traces. For example, the target may supply its authoritative confidence state and its actual spoken claim; NVIQ independently computes whether those violate the Expression Confidence Boundary.

This distinction is essential: a customer can supply evidence, but cannot self-report a passing NVIQ score.

## Adapter strategy

The HTTP adapter is the generic integration surface. Vendor-specific integrations can later transform provider traces, recordings, tool logs or realtime sessions into the same Evidence Bundle without altering the scorer.

The benchmark core remains provider-neutral.

## Commercial use

For a service-first Reliability Audit, Noct-Tech can now accept:

- an evidence export converted to the Evidence Bundle;
- an instrumented test endpoint implementing the HTTP target protocol;
- traces/transcripts/tool-state data that Noct-Tech maps into the evidence contract during the engagement.

The resulting audit preserves stable evidence references so a customer can see why each material finding exists and re-run the same case set after remediation.
