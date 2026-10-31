import json

import pytest

from nviq.errors import ObservationValidationError
from nviq.observations import load_observations, validate_observation


def test_valid_observation_loads(tmp_path):
    path = tmp_path / "obs.json"
    path.write_text(json.dumps([{
        "case_id": "NVIQ-CONF-001",
        "track": "lsr_cvf",
        "metrics": {"confidence_inflation_error": 0.01},
        "catastrophic_failures": [],
        "trace": {"authoritative_confidence": 0.55},
    }]), encoding="utf-8")
    observations = load_observations(path, {"NVIQ-CONF-001"})
    assert observations[0]["track"] == "lsr_cvf"


def test_unknown_case_id_is_rejected():
    with pytest.raises(ObservationValidationError, match="unknown case_id"):
        validate_observation({
            "case_id": "NVIQ-NOPE-001",
            "track": "audio_native",
            "metrics": {},
            "catastrophic_failures": [],
        }, {"NVIQ-CONF-001"})


def test_invalid_track_is_rejected():
    with pytest.raises(ObservationValidationError, match="invalid track"):
        validate_observation({
            "case_id": "NVIQ-CONF-001",
            "track": "magic",
            "metrics": {},
            "catastrophic_failures": [],
        }, {"NVIQ-CONF-001"})
