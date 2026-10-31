from __future__ import annotations

FRONTIER_TARGETS={
 "realtime-venus-audio":{
   "priority":1,
   "mode":"checkpoint",
   "benchmark_lanes":["conversational_floor_integrity","request_boundary_evidence_freeze","speaker_state_preservation","long_silence_continuity","aefr"],
   "status":"adapter_qualified_runtime_pending",
   "source_repository":"inclusionAI/Realtime-Venus",
   "source_commit":"e53ae8d5bde92b30364b26f2e4c13c9db7a8ffea",
 },
 "gemini-live":{
   "priority":2,
   "mode":"provider",
   "benchmark_lanes":["conversational_floor_integrity","async_future_contamination","result_delivery_provenance"],
   "status":"runtime_partial_qualified_floor_failed",
   "model":"gemini-3.8-live",
   "runtime_lanes":{
     "async_tool_provenance":{
       "status":"qualified",
       "evidence_run_id":36363152185,
       "request_boundary_evidence_freeze":1.0,
       "async_future_contamination_rate":0.0,
       "result_delivery_provenance":1.0,
     },
     "conversational_floor_integrity":{
       "status":"failed",
       "qualified":False,
       "evidence_run_id":36433099081,
       "stimulus_mode":"synthesized_speech_p0",
       "mean_score":0.25,
       "hard_gate_failures":3,
       "catastrophic_failures":3,
     },
   },
 },
 "gpt-live-1":{"priority":3,"mode":"provider","benchmark_lanes":["conversational_floor_integrity","long_silence_continuity","speaker_state_preservation"],"status":"provider_access_required"},
}

def ordered_targets()->list[tuple[str,dict]]:
    return sorted(FRONTIER_TARGETS.items(),key=lambda item:item[1]["priority"])
