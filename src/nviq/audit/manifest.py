import json
from pathlib import Path

from jsonschema import Draft202012Validator

from nviq.errors import AuditValidationError


def load_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AuditValidationError(f"audit manifest must contain a JSON object: {path}")
    return data


def validate_manifest(manifest: dict, schema: dict) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(manifest), key=lambda err: list(err.path))
    if errors:
        audit_id = manifest.get("audit_id", "<unknown>") if isinstance(manifest, dict) else "<unknown>"
        detail = "; ".join(error.message for error in errors[:5])
        raise AuditValidationError(f"{audit_id}: {detail}")
