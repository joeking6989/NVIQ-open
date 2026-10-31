import json
from pathlib import Path
from nviq.execution.lossless_optimization import compression_boundary,evaluate_lossless_optimization

DATA=json.loads((Path(__file__).resolve().parent / "fixtures/compression-boundary-p0.json").read_text())

def test_optimization_cannot_win_by_discarding_material_speech_evidence():
    good,bad=DATA["candidates"]
    assert evaluate_lossless_optimization(DATA["reference"],good)["lossless_optimization_qualification"]==1.0
    r=evaluate_lossless_optimization(DATA["reference"],bad)
    assert r["task_utility"]==1.0
    assert r["optimization_induced_information_loss"]>0
    assert r["lossless_optimization_qualification"]==0.0

def test_compression_boundary_selects_highest_lossless_candidate():
    r=compression_boundary(DATA["reference"],DATA["candidates"])
    assert r["max_safe_compression_ratio"]==1.5
    assert r["safe_candidate_index"]==0
