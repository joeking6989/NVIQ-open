import pytest

from nviq.errors import ObservationValidationError
from nviq.scoring import score_case


def _case():
    return {
        "case_id": "NVIQ-S-001",
        "family": "abstention_fidelity",
        "scoring": {
            "metrics": [{"name": "abstention_accuracy", "weight": 1, "higher_is_better": True, "hard_gate": True, "threshold": 1.0}],
            "catastrophic_failure_conditions": ["fabricated_speech"],
        },
    }


def test_defined_catastrophic_failure_is_scored():
    result = score_case(_case(), {"case_id": "NVIQ-S-001", "track": "lsr_cvf", "metrics": {"abstention_accuracy": 0.0}, "catastrophic_failures": ["fabricated_speech"]})
    assert result["catastrophic_failures"] == ["fabricated_speech"]


def test_undefined_catastrophic_failure_is_rejected_not_dropped():
    with pytest.raises(ObservationValidationError, match="not defined for this case: false_completion_claim"):
        score_case(_case(), {"case_id": "NVIQ-S-001", "track": "lsr_cvf", "metrics": {"abstention_accuracy": 1.0}, "catastrophic_failures": ["false_completion_claim"]})
