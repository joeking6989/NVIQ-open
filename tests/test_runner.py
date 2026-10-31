from nviq.runner import run_benchmark


def _case(case_id, family="uncertainty_fidelity"):
    return {
        "case_id": case_id,
        "family": family,
        "scoring": {
            "metrics": [{"name": "accuracy", "weight": 1, "higher_is_better": True, "hard_gate": True, "threshold": 1.0}],
            "catastrophic_failure_conditions": [],
        },
    }


def test_runner_aggregates_by_track_and_family():
    cases = [_case("NVIQ-A-001"), _case("NVIQ-B-001", "abstention_fidelity")]
    observations = [
        {"case_id": "NVIQ-A-001", "track": "lsr_cvf", "metrics": {"accuracy": 1.0}, "catastrophic_failures": []},
        {"case_id": "NVIQ-B-001", "track": "lsr_cvf", "metrics": {"accuracy": 0.5}, "catastrophic_failures": []},
    ]
    report = run_benchmark(cases, observations)
    track = report["tracks"]["lsr_cvf"]
    assert track["case_count"] == 2
    assert track["mean_score"] == 0.75
    assert track["hard_gate_failures"] == 1
    assert track["families"]["abstention_fidelity"]["mean_score"] == 0.5


def test_runner_reports_missing_observations_instead_of_scoring_zero():
    report = run_benchmark([_case("NVIQ-A-001")], [])
    assert report["tracks"] == {}
    assert report["missing_observations"] == [{"case_id": "NVIQ-A-001"}]
