import hashlib
import json


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def build_snapshot(audit_report: dict) -> dict:
    manifest = audit_report["manifest"]
    benchmark = audit_report["benchmark"]
    target_config = {
        "target_name": manifest["target_name"],
        "target_version": manifest["target_version"],
        "tracks": manifest["tracks"],
        "benchmark_version": manifest["benchmark_version"],
        "case_set": manifest["case_set"],
    }
    track_scores = {name: data["mean_score"] for name, data in sorted(benchmark.get("tracks", {}).items())}
    failures = {
        "finding_ids": [item["finding_id"] for item in audit_report.get("findings", [])],
        "critical": sum(item["severity"] == "Critical" for item in audit_report.get("findings", [])),
        "high": sum(item["severity"] == "High" for item in audit_report.get("findings", [])),
    }
    fingerprint_input = {"manifest": manifest, "benchmark": benchmark, "findings": audit_report.get("findings", [])}
    snapshot = {
        "snapshot_version": "0.1",
        "audit_id": manifest["audit_id"],
        "benchmark_version": manifest["benchmark_version"],
        "target_fingerprint_sha256": _sha256(target_config),
        "audit_fingerprint_sha256": _sha256(fingerprint_input),
        "track_scores": track_scores,
        "failures": failures,
        "missing_observations": benchmark.get("missing_observations", []),
    }
    coverage = audit_report.get("coverage")
    if coverage is not None:
        snapshot["coverage"] = {
            track: {
                "expected": data["expected_case_count"],
                "observed": data["observed_case_count"],
                "missing_case_ids": data["missing_case_ids"],
            }
            for track, data in sorted(coverage.get("tracks", {}).items())
        }
    return snapshot
