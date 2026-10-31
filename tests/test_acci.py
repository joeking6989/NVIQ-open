from nviq.execution.async_integrity import evaluate_acci


def test_acci_complete_fork_preserves_integrity():
    e=[{"kind":"reasoning_fork","fork_time_ms":100,"parent_state_hash":"a"*64,"evidence_available_at_fork":["audio:1"],"background_result_time_ms":200,"merge_time_ms":250,"affected_claim_ids":["c1","c2"],"supersedes_claim_ids":["c1"],"does_not_supersede_claim_ids":["c2"]}]
    r=evaluate_acci(e)
    assert r["acci_integrity"]==1.0


def test_acci_rejects_temporal_and_supersession_corruption():
    e=[{"kind":"reasoning_fork","fork_time_ms":100,"parent_state_hash":"a"*64,"evidence_available_at_fork":[],"background_result_time_ms":90,"merge_time_ms":80,"affected_claim_ids":["c1"],"supersedes_claim_ids":["c1"],"does_not_supersede_claim_ids":["c1"]}]
    r=evaluate_acci(e)
    assert r["merge_temporal_integrity"]==0.0
    assert r["claim_supersession_integrity"]==0.0
    assert r["acci_integrity"]==0.0
