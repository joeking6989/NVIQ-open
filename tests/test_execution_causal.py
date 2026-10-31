from nviq.execution.causal import canonical_state_hash, evaluate_causal_ledger


def test_future_knowledge_turns_final_answer_into_cci_failure():
    ledger={"events":[{"event_id":"future","kind":"acoustic_evidence","event_time_ms":1200,"evidence_available_time_ms":1200,"provenance_refs":["audio:2"]},{"event_id":"decision","kind":"commitment","event_time_ms":1000,"evidence_available_time_ms":900,"commitment_time_ms":1000,"parent_event_ids":["future"],"provenance_refs":["trace:1"]}]}
    r=evaluate_causal_ledger(ledger); assert r.metrics["causal_cognition_integrity"]==0.0; assert "future_knowledge_contamination" in r.failures


def test_reasonable_hypothesis_fails_only_when_committed_before_repair():
    ledger={"events":[{"event_id":"conf","kind":"confidence","event_time_ms":540,"evidence_available_time_ms":420,"confidence_time_ms":540,"confidence":0.91,"provenance_refs":["audio:fifty"]},{"event_id":"commit","kind":"commitment","event_time_ms":1020,"evidence_available_time_ms":420,"commitment_time_ms":1020,"parent_event_ids":["conf"],"provenance_refs":["trace:commit"]},{"event_id":"repair","kind":"revision","event_time_ms":1260,"evidence_available_time_ms":1170,"revision_time_ms":1260,"supersedes_event_ids":["commit"],"provenance_refs":["audio:fifteen"]}]}
    r=evaluate_causal_ledger(ledger); assert "premature_commitment" in r.failures; assert r.metrics["revision_cost_ms"]==240.0


def test_missing_parent_is_provenance_failure():
    r=evaluate_causal_ledger({"events":[{"event_id":"decision","kind":"commitment","event_time_ms":800,"evidence_available_time_ms":500,"commitment_time_ms":800,"parent_event_ids":["missing"],"provenance_refs":["trace:decision"]}]})
    assert "invalid_causal_parent" in r.failures


def test_clean_causal_chain_retains_full_integrity():
    ledger={"events":[{"event_id":"e","kind":"acoustic_evidence","event_time_ms":100,"evidence_available_time_ms":100,"provenance_refs":["audio:1"]},{"event_id":"c","kind":"confidence","event_time_ms":200,"evidence_available_time_ms":100,"confidence_time_ms":200,"confidence":0.95,"parent_event_ids":["e"],"provenance_refs":["trace:c"]},{"event_id":"d","kind":"commitment","event_time_ms":300,"evidence_available_time_ms":100,"commitment_time_ms":300,"parent_event_ids":["c"],"provenance_refs":["trace:d"]},{"event_id":"a","kind":"tool_action","event_time_ms":350,"evidence_available_time_ms":100,"action_authorized_time_ms":350,"parent_event_ids":["d"],"provenance_refs":["tool:a"]}]}
    r=evaluate_causal_ledger(ledger); assert r.failures==(); assert r.metrics["causal_cognition_integrity"]==1.0


def test_non_append_only_history_fails_historical_integrity():
    r=evaluate_causal_ledger({"events":[{"event_id":"later","kind":"acoustic_evidence","event_time_ms":500,"append_sequence":2,"evidence_available_time_ms":500,"provenance_refs":["a"]},{"event_id":"inserted","kind":"acoustic_evidence","event_time_ms":100,"append_sequence":1,"evidence_available_time_ms":100,"provenance_refs":["b"]}]})
    assert "non_append_only_history" in r.failures; assert r.metrics["historical_integrity"]==0.0


def test_state_hash_tamper_is_detected():
    event={"event_id":"e","kind":"acoustic_evidence","event_time_ms":100,"evidence_available_time_ms":100,"provenance_refs":["audio"]}
    event["state_hash"]=canonical_state_hash(event)
    assert evaluate_causal_ledger({"events":[event]}).metrics["historical_integrity"]==1.0
    event["value"]="mutated"
    r=evaluate_causal_ledger({"events":[event]}); assert "state_hash_mismatch" in r.failures


def test_revision_must_supersede_existing_earlier_event():
    r=evaluate_causal_ledger({"events":[{"event_id":"r","kind":"revision","event_time_ms":100,"evidence_available_time_ms":100,"revision_time_ms":100,"supersedes_event_ids":["missing"],"provenance_refs":["repair"]}]})
    assert "invalid_supersession_target" in r.failures; assert r.metrics["historical_integrity"]==0.0


def test_event_time_can_arrive_out_of_order_without_rewriting_append_history():
    ledger={"events":[
        {"event_id":"later-evidence","kind":"acoustic_evidence","event_time_ms":1200,"evidence_available_time_ms":1200,"provenance_refs":["audio:future"]},
        {"event_id":"earlier-decision","kind":"commitment","event_time_ms":1000,"evidence_available_time_ms":900,"commitment_time_ms":1000,"parent_event_ids":["later-evidence"],"provenance_refs":["trace:decision"]}
    ]}
    r=evaluate_causal_ledger(ledger)
    assert "non_append_only_history" not in r.failures
    assert "future_knowledge_contamination" in r.failures
    assert r.failure_locus=="context/prior_contamination"


def test_failure_diagnostic_pinpoints_belief_and_decision_times():
    ledger={"events":[
        {"event_id":"heard","kind":"acoustic_evidence","event_time_ms":300,"evidence_available_time_ms":300,"provenance_refs":["audio"]},
        {"event_id":"uncertain","kind":"confidence","event_time_ms":500,"evidence_available_time_ms":300,"confidence_time_ms":500,"confidence":0.31,"parent_event_ids":["heard"],"provenance_refs":["trace:uncertain"]},
        {"event_id":"commit","kind":"commitment","event_time_ms":650,"evidence_available_time_ms":300,"commitment_time_ms":650,"parent_event_ids":["uncertain"],"provenance_refs":["trace:commit"]}
    ]}
    result=evaluate_causal_ledger(ledger)
    assert result.belief_event_id=="uncertain"
    assert result.belief_time_ms==500.0
    assert result.decision_event_id=="commit"
    assert result.decision_time_ms==650.0
    assert result.failure_locus=="commitment_routing"
