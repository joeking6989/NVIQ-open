import json
from pathlib import Path

from nviq.execution.csc import run_csc_case


def test_csc_bench_p1_adversarial_contract():
    cases = json.loads((Path(__file__).resolve().parent / "fixtures/csc-bench-p1.json").read_text(encoding="utf-8"))
    results = {case["case_id"]: run_csc_case(case) for case in cases}
    assert all(result["passed"] for result in results.values())
    assert results["NVIQ-CSC-HESITATION-001"]["failure_locus"] == "commitment_routing"
    assert results["NVIQ-CSC-DELAYED-ASYNC-001"]["failure_locus"] == "context/prior_contamination"
    assert results["NVIQ-CSC-CLEAN-OVERLAP-001"]["metrics"]["causal_cognition_integrity"] == 1.0
