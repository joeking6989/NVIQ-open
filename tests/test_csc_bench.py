import json
from pathlib import Path

from nviq.execution.csc import developer_trace, run_csc_case


def _cases():
    return json.loads((Path(__file__).resolve().parent / "fixtures/csc-bench-p0.json").read_text(encoding="utf-8"))


def test_csc_bench_p0_contract():
    results = [run_csc_case(case) for case in _cases()]
    assert all(result["passed"] for result in results)
    contaminated = next(r for r in results if "FUTURE-CONTAMINATION" in r["case_id"])
    assert contaminated["metrics"]["causal_cognition_integrity"] == 0.0
    repair = next(r for r in results if "SELF-REPAIR" in r["case_id"])
    assert repair["failure_locus"] == "commitment_routing"
    assert repair["metrics"]["revision_cost_ms"] == 240.0
    justified = next(r for r in results if "JUSTIFIED" in r["case_id"])
    assert justified["metrics"]["causal_cognition_integrity"] == 1.0


def test_developer_trace_exposes_failure_time_and_locus():
    result = run_csc_case(_cases()[0])
    trace = developer_trace(result)
    assert "1020ms | commitment" in trace
    assert "EARLIEST FAILURE LOCUS: commitment_routing @ 1020ms" in trace
