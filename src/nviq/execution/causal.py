from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json


@dataclass(frozen=True)
class CausalDiagnostic:
    metrics: dict[str, float]
    failures: tuple[str, ...]
    failure_locus: str | None
    earliest_failure_time_ms: float | None = None
    belief_event_id: str | None = None
    belief_time_ms: float | None = None
    decision_event_id: str | None = None
    decision_time_ms: float | None = None


def _time(event: dict, field: str) -> float:
    value = event.get(field)
    return float(event["event_time_ms"] if value is None else value)


def canonical_state_hash(event: dict) -> str:
    payload = {k: v for k, v in event.items() if k != "state_hash"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def evaluate_causal_ledger(ledger: dict) -> CausalDiagnostic:
    events = ledger.get("events", [])
    by_id: dict[str, dict] = {}
    failures: set[str] = set()
    failure_points: list[tuple[float, str, str]] = []
    decision_candidates: list[tuple[float, str]] = []

    for event in events:
        eid = event["event_id"]
        if eid in by_id:
            failure_points.append((_time(event, "event_time_ms"), "provenance", "duplicate_event_id"))
        else:
            by_id[eid] = event

    def ancestors(event: dict) -> set[str]:
        seen: set[str] = set()
        stack = list(event.get("parent_event_ids", []))
        while stack:
            eid = stack.pop()
            if eid in seen:
                continue
            seen.add(eid)
            parent = by_id.get(eid)
            if parent:
                stack.extend(parent.get("parent_event_ids", []))
        return seen

    checked_edges = invalid_edges = 0
    last_append_sequence: int | None = None
    consequential_kinds = {"commitment", "shared_state_write", "tool_action", "spoken_consequence"}

    for event in events:
        eid = event["event_id"]
        et = _time(event, "event_time_ms")
        append_sequence = event.get("append_sequence")
        if append_sequence is not None:
            sequence = int(append_sequence)
            if last_append_sequence is not None and sequence <= last_append_sequence:
                failure_points.append((et, "provenance", "non_append_only_history"))
            last_append_sequence = sequence

        if event.get("state_hash") and event["state_hash"] != canonical_state_hash(event):
            failure_points.append((et, "provenance", "state_hash_mismatch"))

        for parent_id in event.get("parent_event_ids", []):
            checked_edges += 1
            parent = by_id.get(parent_id)
            if parent is None:
                invalid_edges += 1
                failure_points.append((et, "provenance", "invalid_causal_parent"))
            elif float(parent["evidence_available_time_ms"]) > et:
                invalid_edges += 1
                failure_points.append((et, "context/prior_contamination", "future_knowledge_contamination"))
                if event.get("kind") in consequential_kinds:
                    decision_candidates.append((et, eid))

        for old_id in event.get("supersedes_event_ids", []):
            old = by_id.get(old_id)
            if old is None:
                failure_points.append((et, "provenance", "invalid_supersession_target"))
            elif event.get("kind") != "revision" or et <= _time(old, "event_time_ms"):
                failure_points.append((et, "provenance", "invalid_supersession_order"))

    fabricated_evidence = [
        event
        for event in events
        if event.get("kind") == "acoustic_evidence" and event.get("fabricated") is True
    ]
    fabricated_ids = {event["event_id"] for event in fabricated_evidence}

    consequential = [event for event in events if event["kind"] in consequential_kinds]
    fabrication_consequences = 0
    for event in consequential:
        if ancestors(event) & fabricated_ids:
            fabrication_consequences += 1
            et = _time(event, "event_time_ms")
            failure_points.append((et, "perception", "fabricated_acoustic_evidence"))
            decision_candidates.append((et, event["event_id"]))

    commitments = [event for event in events if event["kind"] == "commitment"]
    revisions = [event for event in events if event["kind"] == "revision"]
    confidences = [event for event in events if event["kind"] == "confidence"]
    actions = [event for event in events if event["kind"] == "tool_action"]
    evidence_to_commit: list[float] = []
    confidence_to_commit: list[float] = []
    commit_to_action: list[float] = []
    revision_costs: list[float] = []
    premature_ids: set[str] = set()

    for commitment in commitments:
        cid = commitment["event_id"]
        ct = _time(commitment, "commitment_time_ms")
        evidence_to_commit.append(ct - float(commitment["evidence_available_time_ms"]))

        prior_conf = [event for event in confidences if float(event["event_time_ms"]) <= ct]
        if prior_conf:
            latest = max(prior_conf, key=lambda event: float(event["event_time_ms"]))
            confidence_to_commit.append(ct - _time(latest, "confidence_time_ms"))
            if latest.get("confidence") is not None and float(latest["confidence"]) < 0.5:
                premature_ids.add(cid)

        superseding = [
            event
            for event in revisions
            if cid in event.get("supersedes_event_ids", []) and float(event["event_time_ms"]) > ct
        ]
        if superseding:
            first = min(superseding, key=lambda event: float(event["event_time_ms"]))
            premature_ids.add(cid)
            revision_costs.append(_time(first, "revision_time_ms") - ct)

        later = [event for event in actions if float(event["event_time_ms"]) >= ct]
        if later:
            first = min(later, key=lambda event: float(event["event_time_ms"]))
            commit_to_action.append(_time(first, "action_authorized_time_ms") - ct)

    for cid in premature_ids:
        ct = _time(by_id[cid], "commitment_time_ms")
        failure_points.append((ct, "commitment_routing", "premature_commitment"))
        decision_candidates.append((ct, cid))

    for _, _, failure in failure_points:
        failures.add(failure)

    earliest = min(failure_points, key=lambda point: point[0]) if failure_points else None

    decision_event_id = decision_time_ms = None
    belief_event_id = belief_time_ms = None
    if decision_candidates:
        decision_time_ms, decision_event_id = min(decision_candidates, key=lambda item: item[0])
        decision_event = by_id.get(decision_event_id)
        if decision_event is not None:
            belief_candidates = [
                by_id[eid]
                for eid in ancestors(decision_event)
                if eid in by_id
                and by_id[eid].get("kind") in {"hypothesis", "confidence"}
                and _time(by_id[eid], "event_time_ms") <= decision_time_ms
            ]
            if belief_candidates:
                belief = max(belief_candidates, key=lambda event: _time(event, "event_time_ms"))
                belief_event_id = belief["event_id"]
                belief_time_ms = _time(belief, "event_time_ms")

    invalid_rate = invalid_edges / checked_edges if checked_edges else 0.0
    parent_validity = 1.0 - invalid_rate
    historical_failures = {
        "future_knowledge_contamination",
        "non_append_only_history",
        "state_hash_mismatch",
        "invalid_supersession_target",
        "invalid_supersession_order",
        "duplicate_event_id",
    }
    historical_integrity = 0.0 if failures & historical_failures else 1.0
    premature_rate = len(premature_ids) / max(1, len(commitments))
    acoustic_evidence_count = len([event for event in events if event["kind"] == "acoustic_evidence"])
    aefr = len(fabricated_evidence) / max(1, acoustic_evidence_count)
    fabrication_integrity = 0.0 if fabrication_consequences else 1.0
    tbrf = min(parent_validity, historical_integrity)
    cci = min(
        historical_integrity,
        parent_validity,
        fabrication_integrity,
        1.0 if not premature_ids else 0.0,
    )

    def mean(values: list[float]) -> float:
        return round(sum(values) / len(values), 6) if values else 0.0

    metrics = {
        "evidence_to_commit_delay_ms": mean(evidence_to_commit),
        "confidence_to_commit_delay_ms": mean(confidence_to_commit),
        "commit_to_action_delay_ms": mean(commit_to_action),
        "premature_commitment_rate": round(premature_rate, 6),
        "revision_cost_ms": mean(revision_costs),
        "acoustic_evidence_fabrication_rate": round(aefr, 6),
        "fabrication_consequence_rate": round(fabrication_consequences / max(1, len(consequential)), 6),
        "future_knowledge_contamination_rate": round(
            sum(1 for _, _, failure in failure_points if failure == "future_knowledge_contamination")
            / max(1, checked_edges),
            6,
        ),
        "causal_parent_validity": round(parent_validity, 6),
        "historical_integrity": historical_integrity,
        "time_bounded_reconstruction_fidelity": round(tbrf, 6),
        "causal_cognition_integrity": round(cci, 6),
        "earliest_divergence_time_ms": earliest[0] if earliest else -1.0,
    }

    return CausalDiagnostic(
        metrics=metrics,
        failures=tuple(sorted(failures)),
        failure_locus=earliest[1] if earliest else None,
        earliest_failure_time_ms=earliest[0] if earliest else None,
        belief_event_id=belief_event_id,
        belief_time_ms=belief_time_ms,
        decision_event_id=decision_event_id,
        decision_time_ms=decision_time_ms,
    )
