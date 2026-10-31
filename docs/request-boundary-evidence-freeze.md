# Request-Boundary Evidence Freeze

Status: CANONICAL — NVIQ/CSC

An asynchronous task MUST retain the evidence state available when it was authorized. Evidence arriving after authorization MAY cause an explicit revision or supersession, but MUST NOT be inserted retroactively into the task's original causal state.

CSC records result-delivery provenance as five distinct transitions: prepared, returned, accepted/rejected, committed, and actually spoken. Missing transitions reduce provenance completeness.

This invariant is evaluated alongside future-knowledge contamination, Temporal Commitment Fidelity, ACCI, Shared-State Integrity, and the Causal Speech Ledger.
