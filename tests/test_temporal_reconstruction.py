from nviq.execution.temporal_reconstruction import evaluate_temporal_windows

def test_sliding_windows_expose_local_information_loss():
    reference=[
      {"event_id":"a","time_ms":100,"uncertainty":0.4,"speaker_identity":"A","provenance":["x"]},
      {"event_id":"b","time_ms":1200,"prosody":"rising","floor_state":"holds","provenance":["y"]},
      {"event_id":"c","time_ms":2200,"repair":["fifty","fifteen"],"overlap":True,"provenance":["z"]}]
    reconstructed=[dict(reference[0]),dict(reference[1]),{"event_id":"c","time_ms":2200,"repair":["fifteen"],"overlap":False,"provenance":["z"]}]
    r=evaluate_temporal_windows(reference,reconstructed,1000)
    assert r["temporal_window_count"]==3.0
    assert r["worst_window_fidelity"]==0.0
    assert r["sliding_window_reconstruction_fidelity"] < 1.0

def test_lossless_temporal_reconstruction_scores_one():
    reference=[{"event_id":"a","time_ms":100,"uncertainty":0.4,"provenance":["x"]}]
    assert evaluate_temporal_windows(reference,[dict(reference[0])])["sliding_window_reconstruction_fidelity"]==1.0
