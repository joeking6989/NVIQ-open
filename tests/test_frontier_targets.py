from nviq.frontier_targets import FRONTIER_TARGETS, ordered_targets

def test_realtime_venus_is_first_external_target():
    assert ordered_targets()[0][0]=="realtime-venus-audio"
    lanes=FRONTIER_TARGETS["realtime-venus-audio"]["benchmark_lanes"]
    assert "conversational_floor_integrity" in lanes
    assert "request_boundary_evidence_freeze" in lanes
    assert "aefr" in lanes


def test_realtime_venus_adapter_is_qualified_but_runtime_is_not_yet_claimed():
    target=FRONTIER_TARGETS["realtime-venus-audio"]
    assert target["status"]=="adapter_qualified_runtime_pending"
    assert target["source_repository"]=="inclusionAI/Realtime-Venus"
    assert target["source_commit"]=="e53ae8d5bde92b30364b26f2e4c13c9db7a8ffea"


def test_gemini_live_records_authenticated_runtime_lane_outcomes():
    target=FRONTIER_TARGETS["gemini-live"]
    assert target["status"]=="runtime_partial_qualified_floor_failed"
    assert target["model"]=="gemini-3.8-live"
    lanes=target["runtime_lanes"]
    assert lanes["async_tool_provenance"]["status"]=="qualified"
    floor=lanes["conversational_floor_integrity"]
    assert floor["status"]=="failed"
    assert floor["mean_score"]==0.25
    assert floor["hard_gate_failures"]==3
    assert floor["catastrophic_failures"]==3
