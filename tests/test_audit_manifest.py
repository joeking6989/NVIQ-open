import json
from pathlib import Path

import pytest

from nviq.audit.manifest import load_manifest, validate_manifest
from nviq.cases import load_schema
from nviq.errors import AuditValidationError

ROOT = Path(__file__).resolve().parents[1]


def _valid_manifest():
    return {
        "audit_id": "audit-demo-001",
        "customer_name": "Example Voice Co",
        "target_name": "Support Agent",
        "target_version": "2026.09.02",
        "created_at": "2026-09-02T16:00:00+10:00",
        "benchmark_version": "0.2",
        "case_set": "cases/v0.2/starter.json",
        "tracks": ["lsr_cvf"],
        "evidence_sources": [{"evidence_id": "obs-001", "kind": "precomputed_observations", "ref": "examples/observations/starter-observations.json"}],
        "retention_policy": {"raw_audio": "not_retained", "derived_artifacts_days": 90},
    }


def test_valid_manifest_loads_and_validates(tmp_path):
    schema = load_schema(ROOT / "src/nviq/schemas/audit-manifest.v0.1.schema.json")
    path = tmp_path / "audit.json"
    path.write_text(json.dumps(_valid_manifest()), encoding="utf-8")
    manifest = load_manifest(path)
    validate_manifest(manifest, schema)
    assert manifest["audit_id"] == "audit-demo-001"


def test_invalid_manifest_raises_audit_validation_error():
    schema = load_schema(ROOT / "src/nviq/schemas/audit-manifest.v0.1.schema.json")
    manifest = _valid_manifest()
    del manifest["target_name"]
    with pytest.raises(AuditValidationError, match="audit-demo-001"):
        validate_manifest(manifest, schema)
