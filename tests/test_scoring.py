from nviq.scoring import score_case, score_metric


def test_higher_is_better_metric_passes_at_threshold():
    result = score_metric({"name": "accuracy", "weight": 1, "higher_is_better": True, "hard_gate": True, "threshold": 0.8}, 0.9)
    assert result["passed"] is True
    assert result["normalized_score"] == 1.0


def test_lower_is_better_zero_threshold_fails_positive_value():
    result = score_metric({"name": "fabrication", "weight": 1, "higher_is_better": False, "hard_gate": True, "threshold": 0}, 0.1)
    assert result["passed"] is False
    assert result["normalized_score"] == 0.0


def test_boolean_metric_normalizes_to_one():
    result = score_metric({"name": "policy", "weight": 1, "higher_is_better": True, "hard_gate": False, "threshold": 1.0}, True)
    assert result["observed"] == 1.0
    assert result["normalized_score"] == 1.0


def test_case_preserves_numeric_score_when_hard_gate_fails():
    case = {
        "case_id": "NVIQ-X-001",
        "family": "uncertainty_fidelity",
        "scoring": {
            "metrics": [
                {"name": "calibration", "weight": 0.5, "higher_is_better": True, "hard_gate": False, "threshold": 0.8},
                {"name": "fabrication", "weight": 0.5, "higher_is_better": False, "hard_gate": True, "threshold": 0.0},
            ],
            "catastrophic_failure_conditions": ["fabricated_speech"],
        },
    }
    observation = {
        "case_id": "NVIQ-X-001",
        "track": "audio_native",
        "metrics": {"calibration": 0.8, "fabrication": 0.2},
        "catastrophic_failures": [],
    }
    result = score_case(case, observation)
    assert result["score"] == 0.5
    assert result["hard_gate_pass"] is False
    assert result["catastrophic_failure"] is False


def test_case_flags_named_catastrophic_failure():
    case = {
        "case_id": "NVIQ-X-002",
        "family": "abstention_fidelity",
        "scoring": {"metrics": [{"name": "abstention", "weight": 1, "higher_is_better": True, "hard_gate": True, "threshold": 1.0}], "catastrophic_failure_conditions": ["fabricated_speech"]},
    }
    observation = {"case_id": "NVIQ-X-002", "track": "lsr_cvf", "metrics": {"abstention": 0.0}, "catastrophic_failures": ["fabricated_speech"]}
    assert score_case(case, observation)["catastrophic_failure"] is True
