from __future__ import annotations

from nviq.execution.causal import evaluate_causal_ledger


def run_csc_case(case: dict) -> dict:
    diagnostic = evaluate_causal_ledger(case["ledger"])
    expected = case.get("expected", {})
    metrics = diagnostic.metrics
    failures = list(diagnostic.failures)
    passed = True
    if "failure_locus" in expected:
        passed = passed and diagnostic.failure_locus == expected["failure_locus"]
    for failure in expected.get("required_failures", []):
        passed = passed and failure in failures
    for failure in expected.get("forbidden_failures", []):
        passed = passed and failure not in failures
    return {
        "case_id": case["case_id"],
        "family": "causal_speech_cognition",
        "passed": passed,
        "failure_locus": diagnostic.failure_locus,
        "earliest_failure_time_ms": diagnostic.earliest_failure_time_ms,
        "belief_event_id": diagnostic.belief_event_id,
        "belief_time_ms": diagnostic.belief_time_ms,
        "decision_event_id": diagnostic.decision_event_id,
        "decision_time_ms": diagnostic.decision_time_ms,
        "catastrophic_failures": failures,
        "metrics": metrics,
        "timeline": sorted(case["ledger"]["events"], key=lambda event: float(event["event_time_ms"])),
    }


def developer_trace(result: dict) -> str:
    lines = [f"CSC {result['case_id']}: {'PASS' if result['passed'] else 'FAIL'}"]
    for event in result["timeline"]:
        lines.append(
            f"{float(event['event_time_ms']):.0f}ms | {event['kind']} | "
            f"evidence_available={float(event['evidence_available_time_ms']):.0f}ms | "
            f"id={event['event_id']}"
        )
    if result.get("belief_event_id") is not None:
        lines.append(
            f"BELIEF STATE: {result['belief_event_id']} @ {float(result['belief_time_ms']):.0f}ms"
        )
    if result.get("decision_event_id") is not None:
        lines.append(
            f"DECISION: {result['decision_event_id']} @ {float(result['decision_time_ms']):.0f}ms"
        )
    if result["failure_locus"]:
        when = result.get("earliest_failure_time_ms")
        suffix = f" @ {when:.0f}ms" if when is not None else ""
        lines.append(f"EARLIEST FAILURE LOCUS: {result['failure_locus']}{suffix}")
    if result["catastrophic_failures"]:
        lines.append("FAILURES: " + ", ".join(result["catastrophic_failures"]))
    return "\n".join(lines)
