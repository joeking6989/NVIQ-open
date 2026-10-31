# Causal Speech Cognition — NVIQ Research Specification v0.1

Status: APPROVED / implementation target
Date: 2026-09-18
Owner: Noct-Tech

## Thesis

Speech cognition must be evaluated as a causal, time-indexed process rather than only by final transcript, final answer, or task success. NVIQ must be able to determine what evidence was available, what the system believed, how uncertain it was, when it committed, what state/action followed, and whether later evidence rewrote the historical record.

## Canonical constructs

- **Causal Speech Ledger (CSL):** append-only provenance graph spanning acoustic evidence, hypotheses, confidence, commitment, shared-state mutation, reasoning/tool actions, spoken consequence, correction and supersession.
- **Causal Cognition Integrity (CCI):** umbrella qualification construct measuring whether consequential cognition is causally defensible from evidence available at the time.
- **Temporal Commitment Fidelity (TCF):** measures whether commitment occurs neither prematurely nor unnecessarily late relative to sufficient evidence and confidence.
- **Time-Bounded Reconstruction Fidelity (TBRF):** ability to reconstruct a system's cognitive state using only evidence legitimately available at a specified historical instant.
- **Future-Knowledge Contamination Challenge:** tests whether future or otherwise unavailable information contaminates a historical decision.
- **Counterfactual Commitment Test:** evaluates whether alternate commitment timing would have prevented a failure without using future evidence.

## No-retroactive-rewrite invariant

Later evidence MAY create a new interpretation, correction, supersession edge or state version. It MUST NOT mutate the historical record so that the system appears to have possessed evidence or knowledge earlier than it actually did.

Every consequential ledger event SHALL distinguish:
- event_time
- evidence_available_time
- interpretation_time where applicable
- confidence_time where applicable
- commitment_time where applicable
- shared_state_write_time where applicable
- action_authorized_time where applicable
- spoken_consequence_time where applicable
- revision_time where applicable

## Causal chain

Acoustic Evidence -> Representation -> Hypothesis -> Confidence -> Commitment -> Shared-State Mutation -> Reasoning/Tool Action -> Spoken Consequence -> Revision/Supersession

Each event requires stable identity and provenance. Causal parents must refer only to events/evidence available no later than the decision being justified.

## Failure-locus diagnostics

NVIQ SHALL report more than pass/fail. When observable evidence permits, a failed scenario should identify the earliest causal divergence and subsystem class:
- perception
- representation / information loss
- interpretation
- confidence calibration
- repair/self-correction detection
- commitment routing
- shared-state mutation
- context/prior contamination
- reasoning/tool action
- response/state-speech consistency
- historical rewrite/provenance

A final correct answer is not sufficient for a pass when the decision relied on future/unavailable evidence. A later-wrong outcome is not automatically a cognitive failure when the decision was justified by evidence legitimately available at decision time.


### Developer diagnosis contract

For a causal failure, NVIQ records the earliest observable failure locus and, when reconstructable from the ledger graph:

- `belief_event_id` and `belief_time_ms`: the latest upstream hypothesis/confidence state that fed the failing decision;
- `decision_event_id` and `decision_time_ms`: the consequential commitment/action where the failure became operational.

These fields are diagnostic provenance, not a replacement for the full ledger. They let a developer distinguish when a system formed a problematic belief from when it committed that belief to consequential behavior.

## Initial NVIQ metrics

1. evidence_to_commit_delay_ms
2. confidence_to_commit_delay_ms
3. commit_to_action_delay_ms
4. premature_commitment_rate
5. abstention_timing_fidelity
6. revision_cost
7. historical_integrity
8. causal_parent_validity
9. future_knowledge_contamination_rate
10. time_bounded_reconstruction_fidelity
11. causal_cognition_integrity

CCI MUST remain decomposable; it must not hide hard failures behind an aggregate score.

## CSC-Bench

Causal Speech Cognition Benchmark (CSC-Bench) is an NVIQ benchmark family. Initial scenarios should include:
- lexical self-repair ("fifty — actually, fifteen")
- hesitation and abandoned commands
- prosodic reversal / sarcasm
- ambiguous speech resolved by later acoustic evidence
- interruption and overlap
- delayed asynchronous reasoning/tool results
- third-party speech and floor-state ambiguity
- conflicting multimodal evidence
- injected historical priors
- deliberate future-information contamination

## CVF integration

The Causal Speech Ledger spans, rather than replaces, CVF planes:
1. Acoustic Continuity Plane
2. Speech Cognitive Workspace / immediate cognition
3. Asynchronous Reasoning Plane

LSR remains canonical evidence. Derived/compressed representations may optimize utility but cannot destroy evidence required for reconstruction, provenance, uncertainty, prosody, overlap, repair, floor state or speaker identity.

## Lossless Optimization gate

An optimization cannot qualify as superior speech cognition when capability/latency gains are obtained by irreversibly discarding material speech evidence or making historical cognition unreconstructable.

## Acceptance gates for v0.1 implementation

- Machine-readable CSL event schema validates causal timestamps and provenance.
- Historical events are append-only by contract; corrections use supersession.
- CSC-Bench contains executable self-repair, premature-commitment and future-contamination cases.
- Evaluator produces TCF/TBRF/contamination metrics.
- At least one test demonstrates a final-answer PASS that is correctly converted to CCI FAIL because future evidence contaminated the decision.
- At least one test demonstrates an initially reasonable hypothesis that is not classified as a failure until premature commitment occurs.
- Failure-locus output identifies the earliest observable divergence.
- Existing NVIQ benchmark families remain backward compatible.
- Standard Evidence Bundle validation accepts CSL records only when they pass the versioned Causal Speech Ledger schema and the ledger/evidence `case_id` values match.
- CSC-Bench executes through the normal NVIQ evidence -> observation -> scoring -> Reliability Audit path.
