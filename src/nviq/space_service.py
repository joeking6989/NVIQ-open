"""File-based entrypoints for the public NVIQ Hugging Face interface.

The service calls the published NVIQ validators, scorer and audit executor.
A supplied manifest's case_set is metadata only: the separately uploaded cases
file is authoritative. No uploaded path or URL is interpreted as a fetch target.
"""
from pathlib import Path

from .audit.manifest import load_manifest, validate_manifest
from .audit.remediations import load_remediations
from .cases import load_cases, load_schema, validate_cases
from .execution.evidence import load_evidence, validate_evidence
from .execution.runner import execute_audit
from .observations import load_observations
from .reporting import write_report
from .resources import (
    AUDIT_MANIFEST_SCHEMA,
    CAUSAL_LEDGER_SCHEMA,
    EVIDENCE_BUNDLE_SCHEMA,
    REMEDIATION_REGISTRY,
    TEST_CASE_SCHEMA,
)
from .runner import run_benchmark


def _validated_cases(path: Path) -> list[dict]:
    cases = load_cases(Path(path))
    validate_cases(cases, load_schema(TEST_CASE_SCHEMA))
    if not cases:
        raise ValueError("The uploaded case set is empty.")
    return cases


def score_files(case_path: Path, observations_path: Path, output_dir: Path) -> dict:
    """Score uploaded observations with NVIQ's existing deterministic scorer."""
    cases = _validated_cases(case_path)
    observations = load_observations(
        Path(observations_path), {case["case_id"] for case in cases}
    )
    if not observations:
        raise ValueError("The uploaded observations list is empty.")
    report = run_benchmark(cases, observations)
    output = Path(output_dir) / "nviq-benchmark-report.json"
    write_report(report, output)
    return {
        "report": report,
        "summary": {
            "benchmark_version": report["nviq_version"],
            "case_count": len(cases),
            "observation_count": len(observations),
            "tracks": {
                name: {
                    "scored_cases": data["case_count"],
                    "mean_score": data["mean_score"],
                    "hard_gate_failures": data["hard_gate_failures"],
                    "catastrophic_failures": data["catastrophic_failures"],
                }
                for name, data in report["tracks"].items()
            },
            "unobserved_case_ids": [
                item["case_id"] for item in report["missing_observations"]
            ],
        },
        "paths": {"json": output},
    }


def audit_files(
    case_path: Path,
    evidence_path: Path,
    manifest_path: Path,
    output_dir: Path,
) -> dict:
    """Validate supplied evidence and produce real NVIQ audit artifacts.

    The manifest's case_set is not resolved on the server, to prevent untrusted
    manifests from reading arbitrary local files.
    """
    cases = _validated_cases(case_path)
    manifest = load_manifest(Path(manifest_path))
    validate_manifest(manifest, load_schema(AUDIT_MANIFEST_SCHEMA))
    evidence = load_evidence(Path(evidence_path))
    if not evidence:
        raise ValueError("The uploaded evidence bundle is empty.")
    validate_evidence(
        evidence,
        load_schema(EVIDENCE_BUNDLE_SCHEMA),
        {case["case_id"] for case in cases},
        load_schema(CAUSAL_LEDGER_SCHEMA),
    )
    unsupported_tracks = sorted(
        {row["track"] for row in evidence} - set(manifest["tracks"])
    )
    if unsupported_tracks:
        raise ValueError(
            "Evidence contains tracks not enabled by the manifest: "
            + ", ".join(unsupported_tracks)
        )
    registry = load_remediations(REMEDIATION_REGISTRY)
    result = execute_audit(
        manifest, cases, evidence, registry, Path(output_dir)
    )
    result["summary"] = {
        **result["report"]["summary"],
        "evidence_records": len(evidence),
        "derived_observations": len(result["observations"]),
        "coverage_complete": result["report"]["coverage"]["complete"],
        "case_set_source": "uploaded JSON (not a server path)",
    }
    return result
