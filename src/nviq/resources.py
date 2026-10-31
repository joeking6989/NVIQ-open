"""Locations of the contracts and registries that ship inside the nviq package.

Schemas and the remediation registry live in the package so the CLI and SDK work
from any directory and from an installed wheel, not only from a repository checkout.
"""

from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent

SCHEMA_DIR = _PACKAGE_DIR / "schemas"
DATA_DIR = _PACKAGE_DIR / "data"

TEST_CASE_SCHEMA = SCHEMA_DIR / "test-case.v0.2.schema.json"
EVIDENCE_BUNDLE_SCHEMA = SCHEMA_DIR / "evidence-bundle.v0.1.schema.json"
CAUSAL_LEDGER_SCHEMA = SCHEMA_DIR / "causal-speech-ledger.v0.1.schema.json"
AUDIT_MANIFEST_SCHEMA = SCHEMA_DIR / "audit-manifest.v0.1.schema.json"
LOSSLESS_INTERACTION_RECORD_SCHEMA = SCHEMA_DIR / "lossless-interaction-record.v0.1.schema.json"
REMEDIATION_REGISTRY = DATA_DIR / "remediations.v0.1.json"
