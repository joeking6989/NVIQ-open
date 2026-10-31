from nviq.audit.adapters import adapt_precomputed_observations


def test_precomputed_adapter_preserves_metrics_and_adds_execution_metadata():
    observations = [{
        "case_id": "NVIQ-CONF-001",
        "track": "lsr_cvf",
        "metrics": {"confidence_inflation_error": 0.02},
        "catastrophic_failures": [],
        "trace": {"authoritative_entity_confidence": 0.52},
        "evidence_refs": ["starter-observations"],
    }]

    adapted = adapt_precomputed_observations(
        observations,
        provider="Noct-Tech",
        model="starter-fixture",
        configuration={"mode": "precomputed"},
    )

    assert adapted[0]["metrics"] == observations[0]["metrics"]
    assert "score" not in adapted[0]
    assert adapted[0]["adapter"] == {
        "kind": "precomputed",
        "provider": "Noct-Tech",
        "model": "starter-fixture",
        "configuration": {"mode": "precomputed"},
    }
    assert adapted[0]["execution"] == {"status": "success", "failure_reason": None}


def test_precomputed_adapter_does_not_mutate_input():
    observation = {
        "case_id": "NVIQ-CONF-001",
        "track": "lsr_cvf",
        "metrics": {"confidence_inflation_error": 0.02},
        "catastrophic_failures": [],
    }
    adapt_precomputed_observations([observation])
    assert "adapter" not in observation
    assert "execution" not in observation
