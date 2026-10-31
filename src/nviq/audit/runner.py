import json
from pathlib import Path

from nviq.runner import run_benchmark

from .findings import derive_coverage_findings, derive_findings, sort_findings
from .html import render_html
from .remediations import attach_remediations
from .snapshot import build_snapshot


def _overall_status(findings: list[dict]) -> str:
    severities = {item["severity"] for item in findings}
    if "Critical" in severities:
        return "critical"
    if "High" in severities:
        return "action_required"
    if "Medium" in severities:
        return "review"
    return "pass"


def _unique_remediations(findings: list[dict]) -> list[dict]:
    unique = {}
    for finding in findings:
        for remediation in finding.get("remediations", []):
            unique[remediation["remediation_id"]] = remediation
    return [unique[key] for key in sorted(unique)]


def build_coverage(manifest: dict, cases: list[dict], benchmark: dict) -> dict:
    """Expected-versus-observed case coverage for every track the manifest enables."""
    expected = sorted(case["case_id"] for case in cases)
    tracks = {}
    for track in sorted(set(manifest["tracks"])):
        observed = sorted({item["case_id"] for item in benchmark.get("tracks", {}).get(track, {}).get("cases", [])})
        missing = sorted(set(expected) - set(observed))
        tracks[track] = {
            "expected_case_count": len(expected),
            "observed_case_count": len(observed),
            "missing_case_ids": missing,
            "complete": not missing,
        }
    return {
        "case_set": manifest["case_set"],
        "expected_case_ids": expected,
        "tracks": tracks,
        "complete": all(item["complete"] for item in tracks.values()),
    }


def _coverage_sentence(coverage: dict) -> str:
    observed = sum(item["observed_case_count"] for item in coverage["tracks"].values())
    expected = sum(item["expected_case_count"] for item in coverage["tracks"].values())
    if coverage["complete"]:
        return f" Coverage: {observed} of {expected} expected case observation(s)."
    return f" Coverage incomplete: {observed} of {expected} expected case observation(s); unevaluated cases are reported as findings."


def run_audit(manifest: dict, cases: list[dict], observations: list[dict], remediation_registry: list[dict]) -> dict:
    selected_observations = [item for item in observations if item["track"] in set(manifest["tracks"])]
    benchmark = run_benchmark(cases, selected_observations)
    coverage = build_coverage(manifest, cases, benchmark)
    findings = sort_findings(derive_findings(benchmark, selected_observations) + derive_coverage_findings(coverage, cases))
    findings = attach_remediations(findings, remediation_registry)
    critical = sum(item["severity"] == "Critical" for item in findings)
    high = sum(item["severity"] == "High" for item in findings)
    medium = sum(item["severity"] == "Medium" for item in findings)
    status = _overall_status(findings)
    executive = (
        f"NVIQ evaluated {sum(t['case_count'] for t in benchmark['tracks'].values())} scored observations "
        f"across {len(benchmark['tracks'])} track(s): {critical} Critical, {high} High and {medium} Medium finding(s)."
        + _coverage_sentence(coverage)
    )
    return {
        "audit_version": "0.1",
        "manifest": manifest,
        "summary": {"overall_status": status, "critical_findings": critical, "high_findings": high, "medium_findings": medium, "executive_summary": executive},
        "coverage": coverage,
        "benchmark": benchmark,
        "findings": findings,
        "remediations": _unique_remediations(findings),
    }


def write_audit_artifacts(audit_report: dict, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "audit-report.json"
    html_path = output_dir / "audit-report.html"
    snapshot_path = output_dir / "regression-snapshot.json"
    json_path.write_text(json.dumps(audit_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    html_path.write_text(render_html(audit_report), encoding="utf-8")
    snapshot_path.write_text(json.dumps(build_snapshot(audit_report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"json": json_path, "html": html_path, "snapshot": snapshot_path}
