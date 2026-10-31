from __future__ import annotations


def evaluate_request_boundary(events: list[dict]) -> dict[str, float]:
    tasks=[e for e in events if e.get("kind")=="async_task"]
    if not tasks:
        return {"request_boundary_evidence_freeze":1.0,"async_future_contamination_rate":0.0,"result_delivery_provenance":1.0}
    contaminated=0; complete=0
    required=("prepared_time_ms","returned_time_ms","committed_time_ms","spoken_time_ms")
    for task in tasks:
        authorized=float(task["authorized_time_ms"])
        dirty=any(float(t)>authorized for t in task.get("evidence_times_at_authorization",[])) or bool(task.get("later_evidence_retroactively_added"))
        contaminated += int(dirty)
        decision_count=sum(task.get(k) is not None for k in ("accepted_time_ms","rejected_time_ms"))
        complete += int(all(task.get(k) is not None for k in required) and decision_count==1)
    rate=contaminated/len(tasks)
    return {"request_boundary_evidence_freeze":round(1.0-rate,6),"async_future_contamination_rate":round(rate,6),"result_delivery_provenance":round(complete/len(tasks),6)}


def evaluate_acci(events: list[dict]) -> dict[str, float]:
    """Experimental (audit finding D9): not reachable from the CLI or execution runner; no case family uses it yet."""
    forks=[e for e in events if e.get("kind")=="reasoning_fork"]
    if not forks:
        return {"acci_integrity":1.0,"fork_provenance_completeness":1.0,"merge_temporal_integrity":1.0,"claim_supersession_integrity":1.0}
    provenance_ok=merge_ok=supersession_ok=0
    for fork in forks:
        authorized=float(fork["fork_time_ms"])
        required=("parent_state_hash","evidence_available_at_fork","background_result_time_ms","merge_time_ms","affected_claim_ids")
        provenance_ok += int(all(fork.get(k) is not None for k in required))
        result=float(fork.get("background_result_time_ms",authorized))
        merge=float(fork.get("merge_time_ms",result))
        merge_ok += int(result>=authorized and merge>=result)
        supersedes=set(fork.get("supersedes_claim_ids",[]))
        preserves=set(fork.get("does_not_supersede_claim_ids",[]))
        affected=set(fork.get("affected_claim_ids",[]))
        supersession_ok += int(not (supersedes & preserves) and (supersedes|preserves)<=affected)
    n=len(forks)
    p=provenance_ok/n; m=merge_ok/n; s=supersession_ok/n
    return {"acci_integrity":round(min(p,m,s),6),"fork_provenance_completeness":round(p,6),"merge_temporal_integrity":round(m,6),"claim_supersession_integrity":round(s,6)}
