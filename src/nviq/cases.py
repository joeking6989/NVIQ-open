import json
from pathlib import Path

from jsonschema import Draft202012Validator

from .errors import CaseValidationError


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_schema(path: Path) -> dict:
    schema = _read_json(path)
    Draft202012Validator.check_schema(schema)
    return schema


def load_cases(path: Path) -> list[dict]:
    data = _read_json(path)
    if not isinstance(data, list):
        raise CaseValidationError(f"case file must contain a JSON array: {path}")
    return data


def validate_case(case: dict, schema: dict) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(case), key=lambda err: list(err.path))
    if errors:
        case_id = case.get("case_id", "<unknown>") if isinstance(case, dict) else "<unknown>"
        detail = "; ".join(error.message for error in errors[:5])
        raise CaseValidationError(f"{case_id}: {detail}")


def validate_cases(cases: list[dict], schema: dict) -> None:
    seen: set[str] = set()
    for case in cases:
        validate_case(case, schema)
        case_id = case["case_id"]
        if case_id in seen:
            raise CaseValidationError(f"{case_id}: duplicate case_id")
        seen.add(case_id)
