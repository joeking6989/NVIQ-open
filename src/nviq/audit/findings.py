from __future__ import annotations


def _observations_by_key(observations: list[dict]) -> dict[tuple[str, str], dict]:
    return {(item["case_id"], item["track"]): item for item in observations}


def _evidence(case_result: dict, observation: dict | None) -> dict:
    observation = observation or {}
    return {
        "case_id": case_result["case_id"],
        "family": case_result["family"],
        "track": case_result["track"],
        "metrics": case_result.get("metrics", []),
        "source_evidence_ids": sorted(observation.get("evidence_refs", [])),
        "trace": observation.get("trace", {}),
        "adapter": observation.get("adapter", {}),
        "execution": observation.get("execution", {}),
    }


def _finding_id(case_result: dict, suffix: str) -> str:
    safe = suffix.replace(" ", "_").replace("/", "_")
    return f"F-{case_result['track']}-{case_result['case_id']}-{safe}"


def derive_findings(benchmark_report: dict, observations: list[dict]) -> list[dict]:
    by_key = _observations_by_key(observations)
    findings: list[dict] = []
    for track_name, track in sorted(benchmark_report.get("tracks", {}).items()):
        for case in sorted(track.get("cases", []), key=lambda item: item["case_id"]):
            observation = by_key.get((case["case_id"], track_name))
            evidence = _evidence(case, observation)
            for failure_id in sorted(case.get("catastrophic_failures", [])):
                findings.append({
                    "finding_id": _finding_id(case, f"catastrophic-{failure_id}"),
                    "finding_type": "catastrophic_failure",
                    "severity": "Critical",
                    "family": case["family"],
                    "case_id": case["case_id"],
                    "track": track_name,
                    "metric_name": None,
                    "failure_id": failure_id,
                    "summary": f"Catastrophic NVIQ failure: {failure_id}",
                    "evidence": evidence,
                })
            for metric in sorted(case.get("metrics", []), key=lambda item: item["name"]):
                if metric.get("passed", True):
                    continue
                finding_type = "hard_gate_failure" if metric.get("hard_gate") else "metric_failure"
                severity = "High" if metric.get("hard_gate") else "Medium"
                findings.append({
                    "finding_id": _finding_id(case, f"metric-{metric['name']}"),
                    "finding_type": finding_type,
                    "severity": severity,
                    "family": case["family"],
                    "case_id": case["case_id"],
                    "track": track_name,
                    "metric_name": metric["name"],
                    "failure_id": None,
                    "summary": f"NVIQ metric failed: {metric['name']}",
                    "evidence": evidence,
                })
            for metric_name in sorted(case.get("missing_metrics", [])):
                findings.append({
                    "finding_id": _finding_id(case, f"missing-{metric_name}"),
                    "finding_type": "missing_metric",
                    "severity": "High",
                    "family": case["family"],
                    "case_id": case["case_id"],
                    "track": track_name,
                    "metric_name": metric_name,
                    "failure_id": None,
                    "summary": f"Required NVIQ metric missing: {metric_name}",
                    "evidence": evidence,
                })
    return sort_findings(findings)


SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


def sort_findings(findings: list[dict]) -> list[dict]:
    return sorted(findings, key=lambda item: (SEVERITY_ORDER[item["severity"]], item["finding_id"]))


def derive_coverage_findings(coverage: dict, cases: list[dict]) -> list[dict]:
    """Every expected case without a scored observation is a material finding.

    An audit must never pass by omission: a case that produced no evidence was not
    evaluated, so the result cannot claim it passed.
    """
    families = {case["case_id"]: case.get("family") for case in cases}
    findings: list[dict] = []
    for track_name, track in sorted(coverage.get("tracks", {}).items()):
        for case_id in track.get("missing_case_ids", []):
            findings.append({
                "finding_id": f"F-{track_name}-{case_id}-missing-observation",
                "finding_type": "missing_observation",
                "severity": "High",
                "family": families.get(case_id),
                "case_id": case_id,
                "track": track_name,
                "metric_name": None,
                "failure_id": None,
                "summary": "No evidence or observation was produced for this case; it was not evaluated",
                "evidence": {
                    "case_id": case_id,
                    "family": families.get(case_id),
                    "track": track_name,
                    "metrics": [],
                    "source_evidence_ids": [],
                    "trace": {},
                    "adapter": {},
                    "execution": {"status": "missing", "failure_reason": "no observation for expected case"},
                },
            })
    return findings
