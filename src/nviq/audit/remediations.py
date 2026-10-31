import json
from pathlib import Path


def load_remediations(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("remediation registry must contain a JSON array")
    return data


def attach_remediations(findings: list[dict], registry: list[dict]) -> list[dict]:
    result = []
    for finding in findings:
        if finding.get("finding_type") == "missing_observation":
            # The case was never evaluated, so family-specific fixes would be speculative.
            keys = {"missing_observation"}
        else:
            keys = {finding.get("family"), finding.get("finding_type"), finding.get("metric_name"), finding.get("failure_id")}
        matches = [entry for entry in registry if keys.intersection(entry.get("applies_to", []))]
        enriched = dict(finding)
        enriched["remediations"] = sorted(matches, key=lambda item: item["remediation_id"])
        result.append(enriched)
    return result
