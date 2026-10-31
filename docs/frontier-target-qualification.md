# Frontier speech target qualification

External model comparisons are subordinate to NVIQ benchmark development.

Current order:
1. Realtime-Venus-Audio checkpoint
2. Gemini Live provider target
3. GPT-Live-1 provider target

Realtime-Venus-Audio is the first checkpoint target for Conversational Floor Integrity, Request-Boundary Evidence Freeze, Speaker-State Preservation, Long-Silence Continuity, and AEFR. Runtime execution requires a compatible model host; absence of such hardware must not weaken, skip, or fabricate benchmark evidence.

Provider targets require authenticated access and are never treated as verified from vendor-reported numbers alone.

## Gemini Live provider target

The Gemini Live adapter contract is implemented against `gemini-3.8-live`. Native provider interruption, transcription, realtime-input and tool-call/tool-response messages are retained as evidence provenance; they are not promoted directly into NVIQ scores.

Conversational floor labels and asynchronous request-boundary/result-delivery facts require explicit NVIQ capture instrumentation. The deterministic repository fixture qualifies the adapter contract only. The target remains `adapter_qualified_provider_runtime_pending` until authenticated live execution produces real provider evidence.
