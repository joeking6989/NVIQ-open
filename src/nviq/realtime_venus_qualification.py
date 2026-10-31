from __future__ import annotations

import hashlib
import json
from typing import Any

from nviq.adapters.realtime_venus import (
    CAPTURE_CONTRACT,
    DEFAULT_MODEL,
    SOURCE_REPOSITORY,
)
from nviq.frontier_targets import FRONTIER_TARGETS


RECEIPT_VERSION = "0.1"
TARGET_ID = "realtime-venus-audio"

_REQUIRED_FAMILY_METRICS: dict[str, dict[str, float]] = {
    "conversational_floor_integrity": {
        "conversational_floor_integrity": 1.0,
    },
    "long_silence_continuity": {
        "long_silence_continuity": 1.0,
    },
    "asynchronous_cognitive_continuity_integrity": {
        "request_boundary_evidence_freeze": 1.0,
        "async_future_contamination_rate": 0.0,
        "result_delivery_provenance": 1.0,
    },
    "speaker_state_preservation": {
        "speaker_state_preservation": 1.0,
    },
    "causal_speech_cognition": {
        "acoustic_evidence_fabrication_rate": 0.0,
        "fabrication_consequence_rate": 0.0,
        "causal_cognition_integrity": 1.0,
    },
}


def _canonical_sha256(*values: Any) -> str:
    payload = json.dumps(
        values,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _target_source_commit() -> str:
    value = FRONTIER_TARGETS[TARGET_ID].get("source_commit")
    if not isinstance(value, str) or not value:
        raise ValueError("Realtime-Venus frontier target is missing source_commit")
    return value


def qualify_realtime_venus_runtime(
    cases: list[dict],
    evidence_records: list[dict],
    observations: list[dict],
    audit_report: dict,
) -> dict:
    """Build a deterministic runtime qualification receipt.

    Qualification is intentionally stricter than adapter validation. It requires
    authentic runtime-labelled evidence from the pinned upstream checkpoint,
    complete priority-lane coverage, and a passing NVIQ audit. Adapter fixtures
    and synthetic capture origins are rejected even when their metrics pass.
    """

    reasons: list[str] = []
    expected_source_commit = _target_source_commit()
    cases_by_id = {case.get("case_id"): case for case in cases}
    observations_by_id = {
        observation.get("case_id"): observation for observation in observations
    }

    if not cases:
        reasons.append("no benchmark cases supplied")
    if not evidence_records:
        reasons.append("no runtime evidence supplied")
    if len(evidence_records) != len(cases):
        reasons.append(
            f"evidence/case count mismatch: evidence={len(evidence_records)} cases={len(cases)}"
        )

    evidence_case_ids = [record.get("case_id") for record in evidence_records]
    if len(set(evidence_case_ids)) != len(evidence_case_ids):
        reasons.append("duplicate evidence case_id values")
    if set(evidence_case_ids) != set(cases_by_id):
        reasons.append("runtime evidence does not cover the exact qualification case set")

    family_case_ids: dict[str, list[str]] = {}
    for case in cases:
        case_id = case.get("case_id")
        family = case.get("family")
        if isinstance(case_id, str) and isinstance(family, str):
            family_case_ids.setdefault(family, []).append(case_id)

    for family in _REQUIRED_FAMILY_METRICS:
        if not family_case_ids.get(family):
            reasons.append(f"missing required qualification family: {family}")

    for record in evidence_records:
        case_id = record.get("case_id", "<unknown>")
        provenance = record.get("provenance")
        if not isinstance(provenance, dict):
            reasons.append(f"{case_id}: missing provenance")
            continue

        provider = provenance.get("provider")
        model = provenance.get("model")
        session_id = provenance.get("session_id")
        audio_ref = provenance.get("audio_ref")
        configuration = provenance.get("configuration")

        if provider != "inclusionAI":
            reasons.append(f"{case_id}: provider must be inclusionAI")
        if model != DEFAULT_MODEL:
            reasons.append(f"{case_id}: model must be {DEFAULT_MODEL}")
        if not isinstance(session_id, str) or not session_id:
            reasons.append(f"{case_id}: runtime session_id is required")
        if not isinstance(audio_ref, str) or not audio_ref:
            reasons.append(f"{case_id}: runtime audio_ref is required")
        if not isinstance(configuration, dict):
            reasons.append(f"{case_id}: missing provenance configuration")
            continue

        if configuration.get("adapter") != CAPTURE_CONTRACT:
            reasons.append(f"{case_id}: unexpected capture adapter")
        if configuration.get("source_repository") != SOURCE_REPOSITORY:
            reasons.append(f"{case_id}: unexpected source repository")
        if configuration.get("source_commit") != expected_source_commit:
            reasons.append(
                f"{case_id}: source commit must equal pinned {expected_source_commit}"
            )
        if configuration.get("capture_origin") != "runtime":
            reasons.append(f"{case_id}: capture_origin must be runtime")

    if set(observations_by_id) != set(cases_by_id):
        reasons.append("derived observations do not cover the exact qualification case set")

    for family, requirements in _REQUIRED_FAMILY_METRICS.items():
        case_ids = family_case_ids.get(family, [])
        family_observations = [
            observations_by_id[case_id]
            for case_id in case_ids
            if case_id in observations_by_id
        ]
        if not family_observations:
            continue

        for observation in family_observations:
            case_id = observation.get("case_id", "<unknown>")
            if observation.get("track") != "audio_native":
                reasons.append(f"{case_id}: qualification observation track must be audio_native")
            adapter = observation.get("adapter", {})
            if adapter.get("provider") != "inclusionAI":
                reasons.append(f"{case_id}: observation provider must be inclusionAI")
            if adapter.get("model") != DEFAULT_MODEL:
                reasons.append(f"{case_id}: observation model must be {DEFAULT_MODEL}")
            if observation.get("execution", {}).get("status") != "success":
                reasons.append(f"{case_id}: NVIQ execution did not succeed")
            failures = observation.get("catastrophic_failures", [])
            if failures:
                reasons.append(
                    f"{case_id}: catastrophic failure(s): {', '.join(map(str, failures))}"
                )
            metrics = observation.get("metrics", {})
            for name, expected in requirements.items():
                actual = metrics.get(name)
                if actual != expected:
                    reasons.append(
                        f"{case_id}: {name} expected {expected} but observed {actual!r}"
                    )

    report_manifest = audit_report.get("manifest", {})
    if report_manifest.get("deployment_environment") != "runtime":
        reasons.append("audit deployment_environment must be runtime")
    if report_manifest.get("target_name") != DEFAULT_MODEL:
        reasons.append(f"audit target_name must be {DEFAULT_MODEL}")
    if report_manifest.get("target_version") != expected_source_commit:
        reasons.append(
            f"audit target_version must equal pinned {expected_source_commit}"
        )

    summary = audit_report.get("summary", {})
    if summary.get("overall_status") != "pass":
        reasons.append(
            f"audit overall_status must be pass, got {summary.get('overall_status')!r}"
        )

    tracks = audit_report.get("benchmark", {}).get("tracks", {})
    audio_track = tracks.get("audio_native")
    if not isinstance(audio_track, dict):
        reasons.append("audit is missing audio_native benchmark track")
    else:
        if int(audio_track.get("case_count", -1)) != len(cases):
            reasons.append("audit audio_native case_count does not match qualification cases")
        if int(audio_track.get("hard_gate_failures", -1)) != 0:
            reasons.append("audit contains hard-gate failures")
        if int(audio_track.get("catastrophic_failures", -1)) != 0:
            reasons.append("audit contains catastrophic failures")

    qualified = not reasons
    bundle_sha256 = _canonical_sha256(
        cases,
        evidence_records,
        observations,
        audit_report,
    )

    return {
        "receipt_version": RECEIPT_VERSION,
        "target_id": TARGET_ID,
        "target_model": DEFAULT_MODEL,
        "source_repository": SOURCE_REPOSITORY,
        "source_commit": expected_source_commit,
        "capture_origin_required": "runtime",
        "qualified": qualified,
        "status": "qualified" if qualified else "rejected",
        "reasons": reasons,
        "case_ids": sorted(
            case_id for case_id in cases_by_id if isinstance(case_id, str)
        ),
        "required_families": sorted(_REQUIRED_FAMILY_METRICS),
        "qualification_bundle_sha256": bundle_sha256,
        "audit_status": summary.get("overall_status"),
    }
