"""Release Guard: compare two canonical NVIQ audit reports.

A candidate is only ever recommended when it was evaluated on the same benchmark
version and case set as the baseline, kept every case the baseline evaluated, and
introduced no new hard-gate, missing-evidence or catastrophic failure. Score deltas
are computed only over cases both audits evaluated, so dropping a failing case can
never raise a score.
"""

from __future__ import annotations

_GATE_FINDING_TYPES = ("hard_gate_failure", "missing_metric", "missing_observation")


def _case_scores(audit: dict) -> dict[tuple[str, str], dict]:
    result = {}
    for track_name, track in audit.get("benchmark", {}).get("tracks", {}).items():
        for case in track.get("cases", []):
            result[(track_name, case["case_id"])] = case
    return result


def _expected_cases(audit: dict) -> dict[str, list[str]]:
    """Expected case ids per track, from recorded coverage or reconstructed for older reports."""
    coverage = audit.get("coverage")
    if coverage:
        expected = sorted(coverage.get("expected_case_ids", []))
        return {track: expected for track in sorted(coverage.get("tracks", {}))}
    benchmark = audit.get("benchmark", {})
    missing = {item["case_id"] for item in benchmark.get("missing_observations", [])}
    tracks = benchmark.get("tracks", {})
    return {
        track: sorted({case["case_id"] for case in data.get("cases", [])} | missing)
        for track, data in sorted(tracks.items())
    }


def _finding_ids(audit: dict, *finding_types: str) -> set[str]:
    return {item["finding_id"] for item in audit.get("findings", []) if item.get("finding_type") in finding_types}


def _finding_locations(audit: dict) -> dict[str, tuple[str, str]]:
    return {item["finding_id"]: (item.get("track"), item.get("case_id")) for item in audit.get("findings", [])}


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def _comparability_issues(baseline: dict, candidate: dict) -> list[str]:
    issues = []
    base_version = baseline.get("manifest", {}).get("benchmark_version")
    cand_version = candidate.get("manifest", {}).get("benchmark_version")
    if base_version != cand_version:
        issues.append(f"benchmark_version differs: baseline={base_version} candidate={cand_version}")
    base_expected = _expected_cases(baseline)
    cand_expected = _expected_cases(candidate)
    if base_expected != cand_expected:
        if set(base_expected) != set(cand_expected):
            issues.append(f"tracks differ: baseline={sorted(base_expected)} candidate={sorted(cand_expected)}")
        else:
            issues.append("expected case sets differ")
    return issues


def compare_audits(baseline: dict, candidate: dict) -> dict:
    issues = _comparability_issues(baseline, candidate)
    base_cases = _case_scores(baseline)
    cand_cases = _case_scores(candidate)
    common = sorted(set(base_cases) & set(cand_cases))
    lost = sorted(set(base_cases) - set(cand_cases))
    gained = sorted(set(cand_cases) - set(base_cases))

    baseline_score = _mean([base_cases[key]["score"] for key in common])
    candidate_score = _mean([cand_cases[key]["score"] for key in common])
    overall_delta = round(candidate_score - baseline_score, 6)

    family_keys = sorted({f"{key[0]}/{base_cases[key]['family']}" for key in common})
    family_deltas = {}
    for family_key in family_keys:
        keys = [key for key in common if f"{key[0]}/{base_cases[key]['family']}" == family_key]
        family_deltas[family_key] = round(
            _mean([cand_cases[key]["score"] for key in keys]) - _mean([base_cases[key]["score"] for key in keys]), 6
        )

    case_deltas = []
    for key in common:
        base_case = base_cases[key]
        cand_case = cand_cases[key]
        case_deltas.append({"track": key[0], "case_id": key[1], "family": cand_case.get("family", base_case.get("family")), "baseline_score": base_case["score"], "candidate_score": cand_case["score"], "delta": round(cand_case["score"] - base_case["score"], 6)})

    base_gates = _finding_ids(baseline, *_GATE_FINDING_TYPES)
    cand_gates = _finding_ids(candidate, *_GATE_FINDING_TYPES)
    base_cat = _finding_ids(baseline, "catastrophic_failure")
    cand_cat = _finding_ids(candidate, "catastrophic_failure")
    cat_new = sorted(cand_cat - base_cat)
    gates_new = sorted(cand_gates - base_gates)

    locations = _finding_locations(baseline)
    lost_keys = set(lost)

    if issues:
        recommendation = "not_comparable"
    elif cat_new:
        recommendation = "candidate_rejected_new_catastrophic_failure"
    elif lost:
        recommendation = "candidate_coverage_reduced"
    elif gates_new:
        recommendation = "candidate_regressed_hard_gate"
    elif overall_delta > 0:
        recommendation = "candidate_better"
    elif overall_delta < 0:
        recommendation = "baseline_better"
    else:
        recommendation = "no_material_change"

    return {
        "comparison_version": "0.2",
        "baseline_audit_id": baseline.get("manifest", {}).get("audit_id"),
        "candidate_audit_id": candidate.get("manifest", {}).get("audit_id"),
        "comparable": not issues,
        "comparability_issues": issues,
        "coverage": {
            "baseline_case_count": len(base_cases),
            "candidate_case_count": len(cand_cases),
            "common_case_count": len(common),
            "lost_cases": [{"track": track, "case_id": case_id} for track, case_id in lost],
            "gained_cases": [{"track": track, "case_id": case_id} for track, case_id in gained],
        },
        "baseline_score": baseline_score,
        "candidate_score": candidate_score,
        "overall_score_delta": overall_delta,
        "family_deltas": family_deltas,
        "case_deltas": case_deltas,
        # A failure on a case the candidate no longer evaluates is not "fixed".
        "gates_fixed": sorted(fid for fid in base_gates - cand_gates if locations.get(fid) not in lost_keys),
        "gates_newly_failed": gates_new,
        "catastrophic_failures_fixed": sorted(fid for fid in base_cat - cand_cat if locations.get(fid) not in lost_keys),
        "catastrophic_failures_new": cat_new,
        "missing_observations_baseline": baseline.get("benchmark", {}).get("missing_observations", []),
        "missing_observations_candidate": candidate.get("benchmark", {}).get("missing_observations", []),
        "recommendation": recommendation,
    }
