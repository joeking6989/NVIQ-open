# NVIQ v0.2 — Architecture and Benchmark Design

Status: Canonical design baseline
Date: 2026-09-02
Owner: Noct-Tech

## Mission

NVIQ is Noct-Tech's benchmark and assurance system for speech cognition. It measures whether a voice system preserves, interprets, integrates, and acts on human speech without collapsing uncertainty, context, timing, prosody, or shared conversational state into a misleading transcript.

The benchmark is intended to pressure-test and guide the Cognitive Voice Fabric (CVF), Lossless Speech Representation (LSR), Context Mesh, Confidence Routing, Speech Cognitive Workspace (SCW), Temporal Context Ledger, Acoustic Continuity State, Floor-State Model, and future Noct-Tech flagship AI architecture.

## Canonical principles

1. **Transcript non-primacy** — the transcript is a derived view, not the canonical cognitive record.
2. **Preserve first, interpret second** — canonical evidence remains recoverable even when task-specific views are compressed.
3. **Observe first, contextualize second** — current acoustic/prosodic evidence is independently interpreted before historical inferred state may influence cognition.
4. **Historical inference is a prior, never an observation** — current evidence must be able to overturn prior beliefs.
5. **Uncertainty preservation** — uncertainty remains machine-readable through perception, interpretation, action, tools, and response claims.
6. **Expression Confidence Boundary** — spoken or linguistic certainty is an output policy; authoritative confidence lives in Confidence Routing and may not be inflated merely because the model is fluent.
7. **Shared-State Integrity** — generated context, transmitted context, playback-grounded context, interrupted context, and revoked/unheard context are distinct states.
8. **Abstention legitimacy** — `no recoverable message` is a valid cognitive state. The system must not fabricate lexical content.
9. **Behavioral grounding** — spoken certainty must not exceed the certainty of the underlying action/tool state.
10. **Reversible context transformation** — Context Mesh may summarize, compress, promote, offload, retrieve, or supersede active context, but canonical LSR, Temporal Context Ledger, provenance, and source evidence remain recoverable.

## Reference architecture

```text
Continuous Audio
    |
    v
Lossless Speech Representation (canonical evidence record)
    |
    +--> Cognition View
    +--> Paralinguistic View
    +--> Reconstruction / Evidence View
    |
    v
Current Observation Layer
    |
    v
Context Mesh <---- project memory / screen state / vocabulary / agent history
    |
    +--> Temporal Context Ledger
    +--> Acoustic Continuity State
    +--> Epistemic Memory
    +--> Human-State / Paralinguistic Memory
    +--> Provenance-Preserving Context Transformation Layer
    |
    v
Confidence Routing
    |
    +--> Evidence Confidence
    +--> Internal Decision Confidence
    +--> Action Confidence
    +--> Expression Policy
    |
    v
Speech Cognitive Workspace
    |
    +--> Floor-State Model
    +--> Intent + entity hypotheses
    +--> Prior-vs-current evidence reconciliation
    |
    v
Reasoning / Agent Planning / Tools
    |
    v
Response Claim + Spoken Output
```

## NVIQ scoring model

NVIQ reports a capability profile rather than hiding performance behind one opaque score.

| Pillar | Suggested weight | Scope |
|---|---:|---|
| Perceptual Fidelity | 20% | lexical, message-presence, entity, language, acoustic continuity |
| Cognitive Fidelity | 20% | information preservation, transcript-independent cognition, paralinguistics |
| Contextual Integrity | 15% | Context Mesh usefulness, contamination resistance, memory integrity, context transformation |
| Temporal / Turn Integrity | 15% | Shared-State Integrity, playback alignment, floor state, interruption handling |
| Confidence & Abstention | 15% | calibration, uncertainty propagation, abstention, confidence-channel fidelity |
| Agentic / State-Speech Integrity | 10% | action correctness, tool-result grounding, response-claim consistency |
| Evaluation Reliability | 5% | judge calibration, human agreement, metric confidence |

Composite scores must be accompanied by hard-failure counts. High average performance must not hide fabricated speech, false completion claims, unheard-context actions, prior contamination, critical-entity overcommit, or confidence inflation.

## Canonical benchmark families

1. Fidelity–Utility Split
2. Information-Loss / Reconstructability
3. Perception → Representation → Integration → Decision → Action
4. State-Speech Consistency
5. Uncertainty Fidelity
6. Cross-View Information Integrity
7. Code-Switch Continuity / Language-State Fidelity
8. Shared-State Integrity
9. Longitudinal Paralinguistic Memory Integrity
10. Cognitive Utilization Integrity
11. Cross-Turn Acoustic Continuity
12. Interpersonal Stance Fidelity
13. Abstention Fidelity / Message-Presence Calibration
14. Turn-State / Floor-State Cognition
15. Transcript-Independent Cognition
16. Evaluator Confidence
17. Prior-Contamination Resistance
18. Temporal Grounding
19. Confidence-Channel Fidelity
20. Context Transformation Integrity

## P0 benchmark families

The initial executable harness will prioritize seven families:

- Uncertainty Fidelity
- Abstention Fidelity
- State-Speech Consistency
- Shared-State Integrity
- Prior-Contamination Resistance
- Turn-State / Floor-State Cognition
- Confidence-Channel Fidelity

Context Transformation Integrity is the first P1 family because it becomes critical as Context Mesh starts editing its own active working set.

## Hard-failure classes

- **Fabricated speech** — lexical content asserted where no recoverable message exists.
- **False completion claim** — spoken response claims success when tool/action state says otherwise.
- **Unheard-context action** — consequential action relies on assistant content the human never received.
- **Prior override** — weak historical inference defeats strong contradictory current evidence.
- **Critical entity overcommit** — system acts on a low-confidence person, account, project, number, or command without required clarification.
- **Confidence inflation** — expressed confidence materially exceeds evidence-backed internal/action confidence without an explicit calibrated policy basis.
- **Irrecoverable context loss** — active-context compression destroys canonical evidence or provenance required for a later decision.

## Test-case contract

Every executable NVIQ scenario should be representable by a machine-readable object containing, at minimum:

```json
{
  "id": "string",
  "family": "string",
  "description": "string",
  "input": {
    "audio": "reference-or-fixture",
    "transcript_hint": "optional",
    "context": {},
    "prior_state": {},
    "shared_state": {}
  },
  "ground_truth": {
    "verbatim": "optional",
    "semantic_candidates": [],
    "entity_candidates": [],
    "prosodic_observations": {},
    "paralinguistic_hypotheses": {},
    "language_distribution": {},
    "floor_state": "optional",
    "message_presence": 0.0,
    "confidence_targets": {},
    "expected_action_policy": "string",
    "allowed_abstention": true
  },
  "assertions": [],
  "hard_failures": []
}
```

## Harness architecture

The first implementation should be modular:

```text
nviq/
  cases/             benchmark case loading + validation
  adapters/          transcript-only, audio-native, structured-LSR/CVF adapters
  trace/             stage-by-stage cognitive trace contract
  scoring/           metric implementations + pillar aggregation
  gates/             catastrophic/hard-failure checks
  simulators/        tool result + playback/shared-state simulators
  reports/           machine-readable and human-readable result profiles
  cli/               local runner
```

### Adapter interface

Each adapter receives a normalized NVIQ case and returns a stage trace containing as much of the following as the system can expose:

- perception
- representation
- context retrieval/transformation
- confidence routing
- integration / decision state
- tool/action state
- response claim

An adapter may omit inaccessible internal states, but NVIQ will explicitly mark observability gaps rather than silently treating them as passes.

## Data and provenance rules

- Natural human speech and controlled synthetic perturbations must be labeled separately.
- Ambiguity may remain multi-label or probabilistic where annotators genuinely disagree.
- Every inference should be traceable to source audio spans and/or contextual sources where the tested system permits it.
- Paralinguistic observations and inferred user state must remain distinct.
- One low-confidence affective observation may not become a durable user fact.
- Context transformation must record source provenance, transformation type, timestamp, confidence, recoverability pointer, and supersession history.

## Initial acceptance gates

1. No critical evidence channel is silently discarded without an explicit derived-view boundary.
2. Confidence falls appropriately under degraded evidence.
3. System can choose uncertainty or no-message states without fabricating text.
4. Context improves ambiguous cases without overpowering strong contradictory current evidence.
5. No consequential action depends on unheard assistant content.
6. No success claim follows a failed or unverified tool result.
7. Backchannels are not routinely mistaken for floor-taking interruptions.
8. Subjective evaluation reports judge confidence or human calibration.
9. Spoken confidence does not materially exceed evidence-backed internal/action confidence without an explicit calibrated policy reason.
10. Context compression/offloading does not make canonical evidence or provenance irrecoverable.

## Implementation sequence

### Phase 0 — repository foundation

- README and architecture specification
- machine-readable test-case JSON Schema
- starter test cases
- package skeleton
- deterministic local CLI
- unit tests and schema validation
- CI

### Phase 1 — P0 executable benchmark

- implement seven P0 family scorers
- tool-state simulator
- playback/shared-state simulator
- prior-injection harness
- message-free/noise fixtures
- capability-profile report

### Phase 2 — LSR/CVF research tracks

- structured LSR adapter
- information-loss/reconstructability tests
- cross-view integrity
- Context Transformation Integrity
- transcript-independent cognition

### Phase 3 — evaluator calibration and public packaging

- metric-specific automated-judge calibration
- human-review protocol
- reproducible benchmark bundle
- dataset cards
- leaderboard protocol

## Success criteria for v0.2 foundation

The repository foundation is complete when:

- JSON cases validate deterministically against the schema;
- the CLI can discover and run local fixture-based cases without external API credentials;
- stage traces use a versioned contract;
- hard-failure gates are separate from weighted scoring;
- test results are reproducible;
- CI validates schema, tests, formatting, and package importability;
- the codebase contains no dependency on a specific commercial model provider in its core benchmark logic.

## Non-goals for the foundation

- training a foundation model;
- claiming NVIQ is scientifically validated before evaluator calibration and human studies;
- building a production voice assistant;
- forcing every vendor/model to expose hidden internal states;
- publishing sensitive user speech or affective memory.

## Decision

This document is the implementation design baseline for NVIQ v0.2. The next step after review is to implement the repository foundation and P0 harness against this contract.
