from __future__ import annotations

from .errors import ObservationValidationError


def _as_float(value: float | bool) -> float:
    return 1.0 if value is True else 0.0 if value is False else float(value)


def score_metric(metric_spec: dict, observed_value: float | bool) -> dict:
    observed = _as_float(observed_value)
    threshold = metric_spec.get("threshold")
    higher = metric_spec.get("higher_is_better", True)
    if threshold is None:
        passed = True
        normalized = 1.0
    elif higher:
        passed = observed >= threshold
        normalized = 1.0 if threshold <= 0 else max(0.0, min(1.0, observed / threshold))
    else:
        passed = observed <= threshold
        if threshold == 0:
            normalized = 1.0 if observed <= 0 else 0.0
        elif observed <= threshold:
            normalized = 1.0
        elif observed > 0:
            normalized = max(0.0, min(1.0, threshold / observed))
        else:
            normalized = 1.0
    return {
        "name": metric_spec["name"],
        "observed": observed,
        "threshold": threshold,
        "higher_is_better": higher,
        "hard_gate": metric_spec.get("hard_gate", False),
        "weight": float(metric_spec["weight"]),
        "passed": passed,
        "normalized_score": round(normalized, 6),
    }


def score_case(case: dict, observation: dict) -> dict:
    metric_results = []
    weighted = 0.0
    total_weight = 0.0
    missing_metrics = []
    for spec in case["scoring"]["metrics"]:
        name = spec["name"]
        if name not in observation["metrics"]:
            missing_metrics.append(name)
            continue
        result = score_metric(spec, observation["metrics"][name])
        metric_results.append(result)
        weighted += result["normalized_score"] * result["weight"]
        total_weight += result["weight"]
    score = round(weighted / total_weight, 6) if total_weight else 0.0
    hard_gate_pass = not missing_metrics and all(
        result["passed"] for result in metric_results if result["hard_gate"]
    )
    allowed = set(case["scoring"].get("catastrophic_failure_conditions", []))
    reported = observation.get("catastrophic_failures", [])
    unknown = sorted(set(reported) - allowed)
    if unknown:
        # Never silently discard a reported catastrophic failure.
        raise ObservationValidationError(
            f"{case['case_id']}: catastrophic failure(s) not defined for this case: {', '.join(unknown)}"
        )
    observed_failures = [failure for failure in reported if failure in allowed]
    return {
        "case_id": case["case_id"],
        "family": case["family"],
        "track": observation["track"],
        "score": score,
        "hard_gate_pass": hard_gate_pass,
        "catastrophic_failure": bool(observed_failures),
        "catastrophic_failures": observed_failures,
        "missing_metrics": missing_metrics,
        "metrics": metric_results,
    }
