"""Everything under cases/ must be a valid NVIQ test-case file (audit finding D8)."""

from pathlib import Path

import pytest

from nviq.cases import load_cases, load_schema, validate_cases
from nviq.resources import TEST_CASE_SCHEMA

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("path", sorted((ROOT / "cases").rglob("*.json")), ids=lambda p: p.name)
def test_every_case_file_validates(path):
    validate_cases(load_cases(path), load_schema(TEST_CASE_SCHEMA))
