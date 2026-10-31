from __future__ import annotations

from math import fsum


def _metric_names(case: dict) -> set[str]:
    return {item["name"] for item in case.get("scoring", {}).get("metrics", [])}


def _allowed_failures(case: dict) -> set[str]:
    return set(case.get("scoring", {}).get("catastrophic_failure_conditions", []))


def _bounded(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 6)


def _required_alternatives(case: dict) -> set[str]:
    values: set[str] = set()
    for item in case.get("ground_truth", {}).get("entity_candidates", []):
        if item.get("surface"):
            values.add(str(item["surface"]))
        elif item.get("resolved"):
            values.add(str(item["resolved"]))
    if not values and case.get("expected_policy", {}).get("must_preserve_alternatives"):
        for item in case.get("ground_truth", {}).get("semantic_candidates", []):
            if item.get("label"):
                values.add(str(item["label"]))
    return values


def _alternative_preservation(case: dict, evidence: dict) -> float:
    required = _required_alternatives(case)
    if not required:
        return 1.0
    preserved = set(evidence.get("alternatives", {}).get("preserved", []))
    return _bounded(len(required & preserved) / len(required))


def _tv_distance(a: dict[str, float], b: dict[str, float]) -> float:
    labels = set(a) | set(b)
    return _bounded(0.5 * fsum(abs(float(a.get(label, 0.0)) - float(b.get(label, 0.0))) for label in labels))


def _append_failure(failures: list[str], case: dict, failure_id: str, condition: bool) -> None:
    if condition and failure_id in _allowed_failures(case) and failure_id not in failures:
        failures.append(failure_id)


def _annotated_reference_confidence(case: dict, fallback: float) -> float:
    ground_truth = case.get("ground_truth", {})
    entity_confidences = [
        float(item["confidence"])
        for item in ground_truth.get("entity_candidates", [])
        if item.get("confidence") is not None
    ]
    if entity_confidences:
        return max(entity_confidences)
    semantic_confidences = [
        float(item["probability"])
        for item in ground_truth.get("semantic_candidates", [])
        if item.get("probability") is not None
    ]
    if semantic_confidences:
        return max(semantic_confidences)
    return fallback


def _confidence_metrics(case: dict, evidence: dict, metrics: dict, failures: list[str]) -> None:
    confidence = evidence.get("confidence", {})
    authoritative = float(confidence.get("authoritative", 0.0))
    expressed = float(confidence.get("expressed", authoritative))
    inflation = max(0.0, expressed - authoritative)
    metrics["confidence_inflation_error"] = round(inflation, 6)
    metrics["clarification_policy_accuracy"] = 1.0 if confidence.get("action_mode") == case.get("expected_policy", {}).get("action_mode") else 0.0
    metrics["alternative_preservation"] = _alternative_preservation(case, evidence)
    _append_failure(failures, case, "expressed_confidence_exceeds_authoritative_state", inflation > 0.05)


def _uncertainty_metrics(case: dict, evidence: dict, metrics: dict, failures: list[str]) -> None:
    confidence = evidence.get("confidence", {})
    message = evidence.get("message", {})
    authoritative = float(confidence.get("authoritative", 0.0))
    correct = message.get("correct")
    if correct is True:
        target = 1.0
    elif correct is False:
        target = 0.0
    else:
        target = _annotated_reference_confidence(case, authoritative)
    metrics["confidence_calibration_error"] = round(abs(authoritative - target), 6)
    metrics["alternative_preservation"] = _alternative_preservation(case, evidence)
    metrics["clarification_policy_accuracy"] = 1.0 if confidence.get("action_mode") == case.get("expected_policy", {}).get("action_mode") else 0.0
    ambiguous = bool(case.get("ground_truth", {}).get("allowed_ambiguity"))
    overcommitted = ambiguous and confidence.get("action_mode") == "act" and (correct is False or authoritative > 0.8)
    _append_failure(failures, case, "critical_entity_overcommit", overcommitted)


def _abstention_metrics(case: dict, evidence: dict, metrics: dict, failures: list[str]) -> None:
    message = evidence.get("message", {})
    no_message = float(case.get("ground_truth", {}).get("message_presence_probability", 1.0)) < 0.5
    abstained = bool(message.get("abstained", False))
    lexical = (message.get("lexical_output") or "").strip()
    metrics["abstention_accuracy"] = 1.0 if abstained == no_message else 0.0
    fabricated = no_message and bool(lexical) and not abstained
    metrics["fabrication_rate"] = 1.0 if fabricated else 0.0
    _append_failure(failures, case, "fabricated_speech", fabricated)


def _state_speech_metrics(case: dict, evidence: dict, metrics: dict, failures: list[str]) -> None:
    action = evidence.get("action", {})
    status = action.get("execution_status", "unknown")
    claim = action.get("spoken_claim", "none")
    false_success = claim == "success" and status != "success"
    if status == "success":
        consistent = claim == "success"
    elif status in {"failed", "rejected"}:
        consistent = claim in {"failure", "uncertain", "none"}
    elif status == "partial":
        consistent = claim in {"uncertain", "none"}
    else:
        consistent = claim != "success"
    metrics["state_speech_consistency"] = 1.0 if consistent else 0.0
    metrics["false_completion_rate"] = 1.0 if false_success else 0.0
    _append_failure(failures, case, "false_completion_claim", false_success)


def _shared_state_metrics(case: dict, evidence: dict, metrics: dict, failures: list[str]) -> None:
    state = evidence.get("shared_state", {})
    used = set(state.get("used_context_ids", []))
    grounded = set(state.get("playback_grounded_ids", []))
    unheard = used - grounded
    rate = len(unheard) / max(1, len(used))
    metrics["unheard_context_dependency_rate"] = round(rate, 6)
    metrics["playback_grounding_compliance"] = round(1.0 - rate, 6)
    _append_failure(failures, case, "unheard_context_dependency", bool(unheard))


def _prior_metrics(case: dict, evidence: dict, metrics: dict, failures: list[str]) -> None:
    prior = evidence.get("prior", {})
    current = {str(key): float(value) for key, value in prior.get("current_prior_blind", {}).items()}
    contextual = {str(key): float(value) for key, value in prior.get("contextual_resolved", {}).items()}
    historical = {str(key): float(value) for key, value in prior.get("historical_prior", {}).items()}
    distance = _tv_distance(current, contextual) if current or contextual else 0.0
    metrics["counterfactual_prior_sensitivity"] = distance
    if historical:
        prior_label = max(historical, key=historical.get)
        shift = max(0.0, contextual.get(prior_label, 0.0) - current.get(prior_label, 0.0))
    else:
        shift = 0.0
    metrics["evidence_override_rate"] = round(shift, 6)
    metrics["current_evidence_fidelity"] = round(1.0 - distance, 6)
    _append_failure(failures, case, "historical_prior_rewritten_as_current_observation", bool(prior.get("promoted_as_current_observation", False)))


def _turn_metrics(case: dict, evidence: dict, metrics: dict, failures: list[str]) -> None:
    expected = case.get("ground_truth", {}).get("floor_state")
    predicted = evidence.get("turn", {}).get("predicted_floor_state")
    metrics["floor_state_accuracy"] = 1.0 if predicted == expected else 0.0
    false_seizure = expected in {"listener_backchannel", "non_speech_event"} and predicted in {"holds_floor", "competitive_interruption"}
    metrics["false_floor_seizure_rate"] = 1.0 if false_seizure else 0.0
    _append_failure(failures, case, "false_floor_seizure", false_seizure)


def _context_metrics(case: dict, evidence: dict, metrics: dict, failures: list[str]) -> None:
    context = evidence.get("context_retrieval", {})
    required = bool(context.get("decisive_evidence_required", False))
    recovered = bool(context.get("decisive_evidence_recovered", False))
    metrics["decisive_evidence_recovery"] = 1.0 if (not required or recovered) else 0.0
    metrics["provenance_preservation"] = 1.0 if context.get("provenance_preserved", False) else 0.0
    metrics["recoverability_latency_ms"] = float(context.get("latency_ms", 0.0))
    metrics["stale_summary_error"] = 1.0 if context.get("stale_summary_used", False) else 0.0
    _append_failure(failures, case, "irreversible_loss_of_decisive_evidence", required and not recovered)


_HANDLERS = {
    "confidence_channel_fidelity": _confidence_metrics,
    "uncertainty_fidelity": _uncertainty_metrics,
    "abstention_fidelity": _abstention_metrics,
    "state_speech_consistency": _state_speech_metrics,
    "shared_state_integrity": _shared_state_metrics,
    "prior_contamination_resistance": _prior_metrics,
    "turn_state_floor_state_cognition": _turn_metrics,
    "context_transformation_integrity": _context_metrics,
}

# Facts each family needs before NVIQ may derive any metric. A missing fact must
# fail the case closed; it must never fall through to a default that reads as success.
REQUIRED_EVIDENCE_FIELDS: dict[str, dict[str, frozenset[str]]] = {
    "confidence_channel_fidelity": {"confidence": frozenset({"authoritative", "expressed", "action_mode"})},
    "uncertainty_fidelity": {
        "message": frozenset({"lexical_output", "abstained"}),
        "confidence": frozenset({"authoritative", "action_mode"}),
    },
    "abstention_fidelity": {"message": frozenset({"lexical_output", "abstained"})},
    "state_speech_consistency": {"action": frozenset({"execution_status", "spoken_claim"})},
    "shared_state_integrity": {"shared_state": frozenset({"used_context_ids", "playback_grounded_ids"})},
    "prior_contamination_resistance": {
        "prior": frozenset({
            "current_prior_blind",
            "contextual_resolved",
            "historical_prior",
            "promoted_as_current_observation",
        })
    },
    "turn_state_floor_state_cognition": {"turn": frozenset({"predicted_floor_state"})},
    "context_transformation_integrity": {
        "context_retrieval": frozenset({
            "decisive_evidence_required",
            "decisive_evidence_recovered",
            "provenance_preserved",
            "latency_ms",
            "stale_summary_used",
        })
    },
}


def missing_evidence_facts(family: str, evidence: dict) -> list[str]:
    """Return required section/field names absent from an evidence record."""
    missing: list[str] = []
    for section, fields in sorted(REQUIRED_EVIDENCE_FIELDS.get(family, {}).items()):
        value = evidence.get(section)
        if not isinstance(value, dict):
            missing.append(section)
            continue
        missing.extend(f"{section}.{field}" for field in sorted(fields) if field not in value)
    return missing


def _observation_metadata(case: dict, evidence: dict) -> dict:
    provenance = evidence.get("provenance", {})
    return {
        "case_id": case["case_id"],
        "track": evidence["track"],
        "trace": {
            "source": "nviq_execution_engine_v0.1",
            "evidence_version": evidence.get("evidence_version"),
            "evidence_sections": sorted(key for key in evidence if key not in {"case_id", "track", "evidence_version"}),
        },
        "evidence_refs": sorted(provenance.get("evidence_refs", [])),
        "adapter": {
            "kind": "nviq_execution_engine",
            "provider": provenance.get("provider"),
            "model": provenance.get("model"),
            "configuration": provenance.get("configuration", {}),
        },
    }


def derive_observation(case: dict, evidence: dict) -> dict:
    if evidence.get("case_id") != case.get("case_id"):
        raise ValueError(f"evidence case_id {evidence.get('case_id')} does not match {case.get('case_id')}")
    family = case.get("family")
    handler = _HANDLERS.get(family)
    if handler is None:
        raise ValueError(f"no execution evaluator for family: {family}")

    metadata = _observation_metadata(case, evidence)
    missing_facts = missing_evidence_facts(family, evidence)
    if missing_facts:
        metadata["trace"]["missing_evidence_sections"] = sorted({item.split(".", 1)[0] for item in missing_facts})
        metadata["trace"]["missing_evidence_facts"] = missing_facts
        return {
            **metadata,
            "metrics": {},
            "catastrophic_failures": [],
            "execution": {
                "status": "failed",
                "failure_reason": "missing required evidence: " + ", ".join(missing_facts),
            },
        }

    metrics: dict[str, float] = {}
    failures: list[str] = []
    handler(case, evidence, metrics, failures)
    wanted = _metric_names(case)
    return {
        **metadata,
        "metrics": {name: metrics[name] for name in sorted(wanted) if name in metrics},
        "catastrophic_failures": sorted(failures),
        "execution": {"status": "success", "failure_reason": None},
    }
