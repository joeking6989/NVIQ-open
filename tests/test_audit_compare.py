from nviq.audit.compare import compare_audits


def _audit(audit_id, score, findings=None, family_score=None):
    family_score=score if family_score is None else family_score
    return {"manifest":{"audit_id":audit_id,"target_name":"Agent","target_version":audit_id},"benchmark":{"tracks":{"lsr_cvf":{"case_count":1,"mean_score":score,"hard_gate_failures":0,"catastrophic_failures":0,"families":{"confidence_channel_fidelity":{"case_count":1,"mean_score":family_score,"hard_gate_failures":0,"catastrophic_failures":0}},"cases":[{"case_id":"NVIQ-C-001","family":"confidence_channel_fidelity","track":"lsr_cvf","score":score,"hard_gate_pass":True,"catastrophic_failure":False,"catastrophic_failures":[],"missing_metrics":[],"metrics":[]}]}},"missing_observations":[]},"findings":findings or []}


def test_compare_reports_score_family_and_case_deltas():
    result=compare_audits(_audit("base",0.6),_audit("cand",0.9))
    assert result["overall_score_delta"]==0.3
    assert result["family_deltas"]["lsr_cvf/confidence_channel_fidelity"]==0.3
    assert result["case_deltas"][0]["delta"]==0.3
    assert result["recommendation"]=="candidate_better"


def test_compare_identifies_fixed_and_new_hard_gates():
    base_f=[{"finding_id":"F-old","finding_type":"hard_gate_failure","severity":"High","family":"confidence_channel_fidelity","case_id":"A","track":"lsr_cvf","metric_name":"old","failure_id":None}]
    cand_f=[{"finding_id":"F-new","finding_type":"hard_gate_failure","severity":"High","family":"confidence_channel_fidelity","case_id":"B","track":"lsr_cvf","metric_name":"new","failure_id":None}]
    result=compare_audits(_audit("base",0.7,base_f),_audit("cand",0.7,cand_f))
    assert result["gates_fixed"]==["F-old"]
    assert result["gates_newly_failed"]==["F-new"]


def test_new_catastrophic_failure_vetoes_positive_score_recommendation():
    catastrophic=[{"finding_id":"F-cat","finding_type":"catastrophic_failure","severity":"Critical","family":"abstention_fidelity","case_id":"X","track":"lsr_cvf","metric_name":None,"failure_id":"fabricated_speech"}]
    result=compare_audits(_audit("base",0.5),_audit("cand",0.95,catastrophic))
    assert result["catastrophic_failures_new"]==["F-cat"]
    assert result["recommendation"]=="candidate_rejected_new_catastrophic_failure"
