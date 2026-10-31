import json
from pathlib import Path
from nviq.execution.continuity import evaluate_long_silence
from nviq.execution.floor_integrity import evaluate_floor_integrity
from nviq.execution.async_integrity import evaluate_request_boundary

DATA=json.loads((Path(__file__).resolve().parent / "fixtures/continuity-floor-async-p0.json").read_text())

def test_long_silence_continuity():
    r=evaluate_long_silence(DATA["long_silence"])
    assert r["long_silence_state_retention"]==1.0
    assert r["long_silence_speaker_retention"]==0.5
    assert r["long_silence_continuity"]==0.5

def test_conversational_floor_integrity():
    r=evaluate_floor_integrity(DATA["floor"])
    assert r["conversational_floor_integrity"]==1.0

def test_request_boundary_freeze_and_result_provenance():
    clean=evaluate_request_boundary(DATA["async_clean"])
    bad=evaluate_request_boundary(DATA["async_contaminated"])
    assert clean["request_boundary_evidence_freeze"]==1.0
    assert clean["result_delivery_provenance"]==1.0
    assert bad["request_boundary_evidence_freeze"]==0.0
    assert bad["async_future_contamination_rate"]==1.0
