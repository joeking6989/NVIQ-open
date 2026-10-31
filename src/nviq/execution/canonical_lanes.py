from __future__ import annotations

from nviq.execution.async_integrity import evaluate_request_boundary
from nviq.execution.continuity import evaluate_long_silence
from nviq.execution.floor_integrity import evaluate_floor_integrity
from nviq.execution.speaker_state import evaluate_speaker_state


CANONICAL_LANE_FAMILIES = {
    "conversational_floor_integrity",
    "long_silence_continuity",
    "asynchronous_cognitive_continuity_integrity",
    "speaker_state_preservation",
}

_SECTION_BY_FAMILY = {
    "conversational_floor_integrity": "floor_events",
    "long_silence_continuity": "silence_events",
    "asynchronous_cognitive_continuity_integrity": "async_tasks",
    "speaker_state_preservation": "speaker_state_events",
}

_PRIMARY_INTEGRITY_METRIC = {
    "conversational_floor_integrity": "conversational_floor_integrity",
    "long_silence_continuity": "long_silence_continuity",
    "speaker_state_preservation": "speaker_state_preservation",
}

_PRIMARY_FAILURE = {
    "conversational_floor_integrity": "conversational_floor_integrity_failure",
    "long_silence_continuity": "long_silence_continuity_failure",
    "speaker_state_preservation": "speaker_state_preservation_failure",
}


def _metric_names(case: dict) -> set[str]:
    return {item["name"] for item in case.get("scoring", {}).get("metrics", [])}


def _allowed_failures(case: dict) -> set[str]:
    return set(case.get("scoring", {}).get("catastrophic_failure_conditions", []))


def _append_failure(failures: list[str], allowed: set[str], failure_id: str, condition: bool) -> None:
    if condition and failure_id in allowed and failure_id not in failures:
        failures.append(failure_id)


_FLOOR_CLASSES = {"genuine_interruption", "backchannel", "other_directed_speech", "background_speech"}
_LONG_SILENCE_MS = 5000.0


def _scorable_events(family: str, events: object) -> list[dict]:
    """Events the lane evaluator can actually score.

    The lane evaluators return 1.0 when nothing qualifies, which is only safe once
    NVIQ has confirmed there is something to evaluate.
    """
    if not isinstance(events, list):
        return []
    rows = [event for event in events if isinstance(event, dict)]
    if family == "conversational_floor_integrity":
        return [event for event in rows if event.get("class") in _FLOOR_CLASSES]
    if family == "long_silence_continuity":
        return [event for event in rows if float(event.get("silence_ms", 0)) >= _LONG_SILENCE_MS]
    if family == "asynchronous_cognitive_continuity_integrity":
        return [event for event in rows if event.get("kind") == "async_task"]
    return [event for event in rows if event.get("expected_speaker_id") is not None]


def _metadata(case: dict, evidence: dict, section: str) -> dict:
    provenance = evidence.get("provenance", {})
    return {
        "case_id": case["case_id"],
        "track": evidence["track"],
        "trace": {
            "source": "nviq_csc_canonical_lanes_v0.1",
            "evidence_version": evidence.get("evidence_version"),
            "evidence_section": section,
        },
        "evidence_refs": sorted(provenance.get("evidence_refs", [])),
        "adapter": {
            "kind": "nviq_csc_canonical_lanes",
            "provider": provenance.get("provider"),
            "model": provenance.get("model"),
            "configuration": provenance.get("configuration", {}),
        },
    }


def run_canonical_lane_case(case: dict, evidence: dict) -> dict:
    if evidence.get("case_id") != case.get("case_id"):
        raise ValueError(f"evidence case_id {evidence.get('case_id')} does not match {case.get('case_id')}")

    family = case.get("family")
    if family not in CANONICAL_LANE_FAMILIES:
        raise ValueError(f"unsupported canonical CSC lane family: {family}")

    section = _SECTION_BY_FAMILY[family]
    metadata = _metadata(case, evidence, section)
    if section not in evidence:
        metadata["trace"]["missing_evidence_sections"] = [section]
        return {
            **metadata,
            "metrics": {},
            "catastrophic_failures": [],
            "execution": {
                "status": "failed",
                "failure_reason": f"missing required evidence sections: {section}",
            },
        }

    if not _scorable_events(family, evidence[section]):
        metadata["trace"]["insufficient_evidence"] = section
        return {
            **metadata,
            "metrics": {},
            "catastrophic_failures": [],
            "execution": {
                "status": "failed",
                "failure_reason": f"insufficient evidence: no scorable events in {section}",
            },
        }

    if family == "conversational_floor_integrity":
        metrics = evaluate_floor_integrity(evidence[section])
    elif family == "long_silence_continuity":
        metrics = evaluate_long_silence(evidence[section])
    elif family == "asynchronous_cognitive_continuity_integrity":
        metrics = evaluate_request_boundary(evidence[section])
    else:
        metrics = evaluate_speaker_state(evidence[section])

    allowed = _allowed_failures(case)
    failures: list[str] = []

    if family == "asynchronous_cognitive_continuity_integrity":
        _append_failure(
            failures,
            allowed,
            "async_future_knowledge_contamination",
            metrics["async_future_contamination_rate"] > 0.0,
        )
        _append_failure(
            failures,
            allowed,
            "result_delivery_provenance_incomplete",
            metrics["result_delivery_provenance"] < 1.0,
        )
    else:
        integrity_metric = _PRIMARY_INTEGRITY_METRIC[family]
        _append_failure(
            failures,
            allowed,
            _PRIMARY_FAILURE[family],
            metrics[integrity_metric] < 1.0,
        )

    wanted = _metric_names(case)
    return {
        **metadata,
        "metrics": {name: metrics[name] for name in sorted(wanted) if name in metrics},
        "catastrophic_failures": sorted(failures),
        "execution": {"status": "success", "failure_reason": None},
    }
