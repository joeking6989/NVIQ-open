import json
from pathlib import Path

from jsonschema import Draft202012Validator

from nviq.errors import EvidenceValidationError


def load_evidence(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise EvidenceValidationError(f"evidence file must contain a JSON array: {path}")
    return data


def _validation_detail(errors: list) -> str:
    return "; ".join(error.message for error in errors[:5])


def validate_evidence(
    records: list[dict],
    schema: dict,
    known_case_ids: set[str] | None = None,
    causal_ledger_schema: dict | None = None,
) -> None:
    validator = Draft202012Validator(schema)
    ledger_validator = Draft202012Validator(causal_ledger_schema) if causal_ledger_schema is not None else None
    seen: set[tuple[str, str]] = set()

    for record in records:
        errors = sorted(validator.iter_errors(record), key=lambda error: list(error.path))
        if errors:
            case_id = record.get("case_id", "<unknown>") if isinstance(record, dict) else "<unknown>"
            raise EvidenceValidationError(f"{case_id}: {_validation_detail(errors)}")

        case_id = record["case_id"]
        track = record["track"]

        if known_case_ids is not None and case_id not in known_case_ids:
            raise EvidenceValidationError(f"unknown case_id: {case_id}")

        if "ledger" in record:
            if ledger_validator is None:
                raise EvidenceValidationError(f"{case_id}: causal ledger schema is required for ledger evidence")
            ledger_errors = sorted(
                ledger_validator.iter_errors(record["ledger"]),
                key=lambda error: list(error.path),
            )
            if ledger_errors:
                raise EvidenceValidationError(f"{case_id}: causal ledger: {_validation_detail(ledger_errors)}")
            ledger_case_id = record["ledger"].get("case_id")
            if ledger_case_id != case_id:
                raise EvidenceValidationError(
                    f"{case_id}: causal ledger case_id {ledger_case_id!r} does not match evidence case_id"
                )

        key = (case_id, track)
        if key in seen:
            raise EvidenceValidationError(f"duplicate evidence for {case_id} on {track}")
        seen.add(key)
