from nviq.execution.runner import derive_observations

def test_csc_runs_through_normal_execution_path():
    case={"case_id":"NVIQ-CSC-RUNNER-001","family":"causal_speech_cognition","expected":{"forbidden_failures":["future_knowledge_contamination"]}}
    evidence={"case_id":case["case_id"],"track":"reference","ledger":{"ledger_version":"0.1","case_id":case["case_id"],"events":[
      {"event_id":"a","kind":"acoustic_evidence","event_time_ms":0,"evidence_available_time_ms":0,"provenance_refs":["audio"]},
      {"event_id":"c","kind":"commitment","event_time_ms":100,"evidence_available_time_ms":0,"commitment_time_ms":100,"parent_event_ids":["a"],"provenance_refs":["audio"]}
    ]},"provenance":{"evidence_refs":["audio"],"provider":"test","model":"fixture"}}
    result=derive_observations([case],[evidence])[0]
    assert result["execution"]["status"]=="success"
    assert result["metrics"]["causal_cognition_integrity"]==1.0
    assert result["trace"]["source"]=="nviq_csc_engine_v0.1"
