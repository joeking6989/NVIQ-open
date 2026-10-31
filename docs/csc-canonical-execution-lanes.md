# CSC canonical execution lanes

Status: executable reference path

This tranche connects four already-canonical NVIQ/CSC speech-cognition checks to the standard NVIQ Evidence Bundle and execution pipeline:

- Conversational Floor Integrity
- Long-Silence Continuity
- Asynchronous Cognitive Continuity Integrity, including Request-Boundary Evidence Freeze
- Speaker-State Preservation

The reference case set is `cases/v0.2/csc-canonical-p0.json` and the corresponding provider-neutral evidence fixture is `examples/evidence/csc-canonical-p0.json`.

Result-delivery provenance treats **accepted** and **rejected** as mutually exclusive decision transitions. A complete task record requires prepared, returned, exactly one of accepted/rejected, committed, and actually spoken timestamps.

These lanes do not weaken the existing causal-speech ledger. They provide a validated execution path for the approved speech-cognition invariants through the same evidence -> derived observation -> scoring/audit architecture used by NVIQ.
