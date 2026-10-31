from nviq.execution.causal import evaluate_causal_ledger


def test_fabricated_acoustic_evidence_is_catastrophic_when_it_changes_commitment():
    ledger={"events":[
      {"event_id":"ghost","kind":"acoustic_evidence","event_time_ms":300,"evidence_available_time_ms":300,"fabricated":True,"provenance_refs":["asr:ghost"]},
      {"event_id":"hyp","kind":"hypothesis","event_time_ms":400,"evidence_available_time_ms":300,"confidence":0.96,"parent_event_ids":["ghost"],"provenance_refs":["trace:hyp"]},
      {"event_id":"commit","kind":"commitment","event_time_ms":600,"evidence_available_time_ms":300,"commitment_time_ms":600,"parent_event_ids":["hyp"],"provenance_refs":["trace:commit"]}
    ]}
    result=evaluate_causal_ledger(ledger)
    assert "fabricated_acoustic_evidence" in result.failures
    assert result.failure_locus == "perception"
    assert result.metrics["acoustic_evidence_fabrication_rate"] == 1.0
    assert result.metrics["causal_cognition_integrity"] == 0.0


def test_unconsumed_fabrication_is_measured_but_does_not_corrupt_cci():
    ledger={"events":[
      {"event_id":"ghost","kind":"acoustic_evidence","event_time_ms":300,"evidence_available_time_ms":300,"fabricated":True,"provenance_refs":["asr:ghost"]},
      {"event_id":"real","kind":"acoustic_evidence","event_time_ms":350,"evidence_available_time_ms":350,"provenance_refs":["audio:real"]},
      {"event_id":"commit","kind":"commitment","event_time_ms":600,"evidence_available_time_ms":350,"commitment_time_ms":600,"parent_event_ids":["real"],"provenance_refs":["trace:commit"]}
    ]}
    result=evaluate_causal_ledger(ledger)
    assert result.metrics["acoustic_evidence_fabrication_rate"] == 0.5
    assert result.metrics["fabrication_consequence_rate"] == 0.0
    assert result.metrics["causal_cognition_integrity"] == 1.0
