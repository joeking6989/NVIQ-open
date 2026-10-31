import json
from pathlib import Path
from nviq.execution.speaker_state import evaluate_speaker_state

def test_speaker_state_cases():
    cases=json.loads((Path(__file__).resolve().parent / "fixtures/speaker-state-preservation-p0.json").read_text())
    results={c["case_id"]:evaluate_speaker_state(c["events"]) for c in cases}
    assert results["NVIQ-SPEAKER-CONTINUITY-001"]["speaker_state_preservation"] == 1.0
    assert results["NVIQ-SPEAKER-MISATTRIBUTION-001"]["speaker_identity_continuity"] == 0.5
    assert results["NVIQ-SPEAKER-MISATTRIBUTION-001"]["speaker_switch_accuracy"] == 0.0
    assert results["NVIQ-SPEAKER-OVERLAP-001"]["overlap_ownership_accuracy"] == 0.5
