import json
from pathlib import Path

import pytest

from nviq.cases import load_cases, load_schema, validate_cases
from nviq.errors import CaseValidationError

ROOT = Path(__file__).resolve().parents[1]


def test_starter_cases_validate_against_v02_schema():
    schema = load_schema(ROOT / "src/nviq/schemas/test-case.v0.2.schema.json")
    cases = load_cases(ROOT / "cases/v0.2/starter.json")
    validate_cases(cases, schema)
    assert {case["case_id"] for case in cases} == {
        "NVIQ-CONF-001",
        "NVIQ-CTX-001",
        "NVIQ-PRIOR-001",
    }


def test_invalid_version_raises_case_validation_error(tmp_path):
    schema = load_schema(ROOT / "src/nviq/schemas/test-case.v0.2.schema.json")
    cases = load_cases(ROOT / "cases/v0.2/starter.json")
    cases[0]["version"] = "0.3"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(cases), encoding="utf-8")

    with pytest.raises(CaseValidationError, match="NVIQ-CONF-001"):
        validate_cases(load_cases(path), schema)
