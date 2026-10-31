import pytest

from nviq.execution.evaluators import derive_observation


def _case(family, metrics, catastrophics=(), *, floor_state=None, action_mode="clarify", entities=None, ambiguity=False):
    return {
        "case_id": "NVIQ-X-001",
        "family": family,
        "ground_truth": {
            "floor_state": floor_state,
            "entity_candidates": entities or [],
            "semantic_candidates": [],
            "message_presence_probability": 0.0 if family == "abstention_fidelity" else 1.0,
            "allowed_ambiguity": ambiguity,
        },
        "expected_policy": {"action_mode": action_mode, "must_preserve_alternatives": bool(entities)},
        "scoring": {
            "metrics": [{"name": name, "weight": 1, "higher_is_better": True, "hard_gate": False, "threshold": 0} for name in metrics],
            "catastrophic_failure_conditions": list(catastrophics),
        },
    }


def _evidence(**sections):
    record = {
        "evidence_version": "0.1",
        "case_id": "NVIQ-X-001",
        "track": "lsr_cvf",
        "provenance": {"evidence_refs": ["E-1"]},
    }
    record.update(sections)
    return record


def test_confidence_channel_metrics_are_derived_from_raw_confidence():
    case = _case(
        "confidence_channel_fidelity",
        ["confidence_inflation_error", "clarification_policy_accuracy", "alternative_preservation"],
        ["expressed_confidence_exceeds_authoritative_state"],
        entities=[{"surface": "Axiom", "resolved": "Axiom", "confidence": 0.5}, {"surface": "Argus", "resolved": "Argus", "confidence": 0.5}],
    )
    result = derive_observation(case, _evidence(confidence={"authoritative": 0.52, "expressed": 0.8, "action_mode": "act"}, alternatives={"preserved": ["Axiom"]}))
    assert result["metrics"]["confidence_inflation_error"] == pytest.approx(0.28)
    assert result["metrics"]["clarification_policy_accuracy"] == 0.0
    assert result["metrics"]["alternative_preservation"] == 0.5
    assert "expressed_confidence_exceeds_authoritative_state" in result["catastrophic_failures"]


def test_uncertainty_overcommit_is_detected():
    case = _case(
        "uncertainty_fidelity",
        ["confidence_calibration_error", "alternative_preservation", "clarification_policy_accuracy"],
        ["critical_entity_overcommit"],
        entities=[{"surface": "A", "resolved": "A", "confidence": 0.5}, {"surface": "B", "resolved": "B", "confidence": 0.5}],
        ambiguity=True,
    )
    result = derive_observation(case, _evidence(message={"presence_probability": 1, "lexical_output": "A", "abstained": False, "correct": False}, confidence={"authoritative": 0.9, "expressed": 0.9, "action_mode": "act"}, alternatives={"preserved": ["A"]}))
    assert result["metrics"]["confidence_calibration_error"] == pytest.approx(0.9)
    assert "critical_entity_overcommit" in result["catastrophic_failures"]


def test_uncertainty_without_binary_correctness_uses_annotated_candidate_confidence():
    case = _case(
        "uncertainty_fidelity",
        ["confidence_calibration_error", "alternative_preservation", "clarification_policy_accuracy"],
        entities=[{"surface": "Miller", "resolved": "Miller", "confidence": 0.55}, {"surface": "Millar", "resolved": "Millar", "confidence": 0.45}],
        ambiguity=True,
    )
    result = derive_observation(
        case,
        _evidence(
            message={"presence_probability": 1, "lexical_output": "Miller or Millar", "abstained": False, "correct": None},
            confidence={"authoritative": 0.95, "expressed": 0.95, "action_mode": "clarify"},
            alternatives={"preserved": ["Miller", "Millar"]},
        ),
    )
    assert result["metrics"]["confidence_calibration_error"] == pytest.approx(0.4)


def test_abstention_detects_fabricated_speech():
    case = _case("abstention_fidelity", ["abstention_accuracy", "fabrication_rate"], ["fabricated_speech"], action_mode="abstain")
    result = derive_observation(case, _evidence(message={"presence_probability": 0.01, "lexical_output": "hello there", "abstained": False}))
    assert result["metrics"] == {"abstention_accuracy": 0.0, "fabrication_rate": 1.0}
    assert result["catastrophic_failures"] == ["fabricated_speech"]


def test_state_speech_detects_false_completion():
    case = _case("state_speech_consistency", ["state_speech_consistency", "false_completion_rate"], ["false_completion_claim"], action_mode="act")
    result = derive_observation(case, _evidence(action={"requested": True, "execution_status": "failed", "spoken_claim": "success"}))
    assert result["metrics"]["state_speech_consistency"] == 0.0
    assert result["metrics"]["false_completion_rate"] == 1.0
    assert result["catastrophic_failures"] == ["false_completion_claim"]


def test_shared_state_detects_unheard_dependency():
    case = _case("shared_state_integrity", ["playback_grounding_compliance", "unheard_context_dependency_rate"], ["unheard_context_dependency"])
    result = derive_observation(case, _evidence(shared_state={"used_context_ids": ["g1", "g2"], "playback_grounded_ids": ["g1"], "generated_ids": ["g1", "g2"]}))
    assert result["metrics"]["playback_grounding_compliance"] == 0.5
    assert result["metrics"]["unheard_context_dependency_rate"] == 0.5
    assert result["catastrophic_failures"] == ["unheard_context_dependency"]


def test_prior_contamination_uses_distribution_shift():
    case = _case("prior_contamination_resistance", ["counterfactual_prior_sensitivity", "evidence_override_rate", "current_evidence_fidelity"], ["historical_prior_rewritten_as_current_observation"])
    result = derive_observation(case, _evidence(prior={"current_prior_blind": {"neutral": 0.9, "angry": 0.1}, "contextual_resolved": {"neutral": 0.4, "angry": 0.6}, "historical_prior": {"angry": 0.95}, "promoted_as_current_observation": True}))
    assert result["metrics"]["counterfactual_prior_sensitivity"] == pytest.approx(0.5)
    assert result["metrics"]["evidence_override_rate"] == pytest.approx(0.5)
    assert result["metrics"]["current_evidence_fidelity"] == pytest.approx(0.5)
    assert result["catastrophic_failures"] == ["historical_prior_rewritten_as_current_observation"]


def test_turn_state_detects_false_floor_seizure():
    case = _case("turn_state_floor_state_cognition", ["floor_state_accuracy", "false_floor_seizure_rate"], floor_state="listener_backchannel")
    result = derive_observation(case, _evidence(turn={"predicted_floor_state": "holds_floor"}))
    assert result["metrics"]["floor_state_accuracy"] == 0.0
    assert result["metrics"]["false_floor_seizure_rate"] == 1.0


def test_context_transform_metrics_are_derived_from_retrieval_evidence():
    case = _case("context_transformation_integrity", ["decisive_evidence_recovery", "provenance_preservation", "recoverability_latency_ms", "stale_summary_error"], ["irreversible_loss_of_decisive_evidence"], action_mode="act")
    result = derive_observation(case, _evidence(context_retrieval={"decisive_evidence_required": True, "decisive_evidence_recovered": False, "provenance_preserved": False, "latency_ms": 900, "stale_summary_used": True}))
    assert result["metrics"] == {"decisive_evidence_recovery": 0.0, "provenance_preservation": 0.0, "recoverability_latency_ms": 900.0, "stale_summary_error": 1.0}
    assert result["catastrophic_failures"] == ["irreversible_loss_of_decisive_evidence"]


def test_missing_required_family_section_becomes_failed_execution():
    case = _case("state_speech_consistency", ["state_speech_consistency", "false_completion_rate"], action_mode="act")
    result = derive_observation(case, _evidence())
    assert result["metrics"] == {}
    assert result["execution"]["status"] == "failed"
    assert "action" in result["execution"]["failure_reason"]
