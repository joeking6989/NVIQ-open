import json
from pathlib import Path

import pytest

from nviq.cases import load_schema
from nviq.errors import EvidenceValidationError
from nviq.execution.evidence import load_evidence, validate_evidence

ROOT = Path(__file__).resolve().parents[1]


def _record(case_id="NVIQ-CONF-001", track="lsr_cvf"):
    return {
        "evidence_version": "0.1",
        "case_id": case_id,
        "track": track,
        "confidence": {"authoritative": 0.5, "expressed": 0.5, "action_mode": "clarify"},
        "provenance": {"evidence_refs": ["EV-TEST-001"]},
    }


def test_valid_evidence_loads_and_validates(tmp_path):
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps([_record()]), encoding="utf-8")
    records = load_evidence(path)
    validate_evidence(records, load_schema(ROOT / "src/nviq/schemas/evidence-bundle.v0.1.schema.json"), {"NVIQ-CONF-001"})
    assert records[0]["evidence_version"] == "0.1"


def test_duplicate_case_track_is_rejected():
    with pytest.raises(EvidenceValidationError, match="duplicate evidence"):
        validate_evidence(
            [_record(), _record()],
            load_schema(ROOT / "src/nviq/schemas/evidence-bundle.v0.1.schema.json"),
            {"NVIQ-CONF-001"},
        )


def test_unknown_case_id_is_rejected():
    with pytest.raises(EvidenceValidationError, match="unknown case_id"):
        validate_evidence(
            [_record("NVIQ-NOPE-001")],
            load_schema(ROOT / "src/nviq/schemas/evidence-bundle.v0.1.schema.json"),
            {"NVIQ-CONF-001"},
        )


def test_invalid_version_is_rejected():
    record = _record()
    record["evidence_version"] = "0.2"
    with pytest.raises(EvidenceValidationError, match="NVIQ-CONF-001"):
        validate_evidence(
            [record],
            load_schema(ROOT / "src/nviq/schemas/evidence-bundle.v0.1.schema.json"),
            {"NVIQ-CONF-001"},
        )


def test_missing_provenance_is_rejected():
    record = _record()
    del record["provenance"]
    with pytest.raises(EvidenceValidationError, match="NVIQ-CONF-001"):
        validate_evidence(
            [record],
            load_schema(ROOT / "src/nviq/schemas/evidence-bundle.v0.1.schema.json"),
            {"NVIQ-CONF-001"},
        )


def _ledger_record(case_id="NVIQ-CSC-LEDGER-TEST-001"):
    return {
        "evidence_version": "0.1",
        "case_id": case_id,
        "track": "lsr_cvf",
        "ledger": {
            "ledger_version": "0.1",
            "case_id": case_id,
            "events": [
                {
                    "event_id": "heard",
                    "kind": "acoustic_evidence",
                    "event_time_ms": 100,
                    "evidence_available_time_ms": 100,
                    "append_sequence": 0,
                    "provenance_refs": ["audio:test"],
                }
            ],
        },
        "provenance": {"evidence_refs": ["EV-CSC-LEDGER-TEST-001"]},
    }


def test_causal_ledger_evidence_requires_and_passes_versioned_ledger_schema():
    record = _ledger_record()
    validate_evidence(
        [record],
        load_schema(ROOT / "src/nviq/schemas/evidence-bundle.v0.1.schema.json"),
        {record["case_id"]},
        load_schema(ROOT / "src/nviq/schemas/causal-speech-ledger.v0.1.schema.json"),
    )


def test_causal_ledger_case_id_must_match_evidence_record():
    record = _ledger_record()
    record["ledger"]["case_id"] = "NVIQ-CSC-OTHER-001"
    with pytest.raises(EvidenceValidationError, match="does not match evidence case_id"):
        validate_evidence(
            [record],
            load_schema(ROOT / "src/nviq/schemas/evidence-bundle.v0.1.schema.json"),
            {record["case_id"]},
            load_schema(ROOT / "src/nviq/schemas/causal-speech-ledger.v0.1.schema.json"),
        )


def test_causal_ledger_evidence_fails_closed_without_ledger_schema():
    record = _ledger_record()
    with pytest.raises(EvidenceValidationError, match="causal ledger schema is required"):
        validate_evidence(
            [record],
            load_schema(ROOT / "src/nviq/schemas/evidence-bundle.v0.1.schema.json"),
            {record["case_id"]},
        )
