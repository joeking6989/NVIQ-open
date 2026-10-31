"""Experimental evaluator (NVIQ audit 18 Oct 2026, finding D9).

Not reachable from the CLI or the execution runner: no benchmark family or case
set uses it yet, so it never contributes to an audit. Wire it to a family with
real cases before relying on it.
"""

from __future__ import annotations

MATERIAL_FIELDS=("uncertainty","prosody","overlap","repair","floor_state","speaker_identity","provenance")

def evaluate_temporal_windows(reference:list[dict], reconstructed:list[dict], window_ms:int=1000)->dict[str,float]:
    if not reference:
        return {"sliding_window_reconstruction_fidelity":1.0,"temporal_window_count":0.0,"worst_window_fidelity":1.0}
    end=max(float(e["time_ms"]) for e in reference)
    starts=[]; cursor=0.0
    while cursor<=end:
        starts.append(cursor); cursor+=window_ms
    scores=[]
    for start in starts:
        stop=start+window_ms
        ref=[e for e in reference if start<=float(e["time_ms"])<stop]
        rec=[e for e in reconstructed if start<=float(e["time_ms"])<stop]
        if not ref: continue
        matched=0; total=0
        rec_by_id={e["event_id"]:e for e in rec}
        for event in ref:
            candidate=rec_by_id.get(event["event_id"])
            total+=1
            if candidate is None: continue
            fields=[f for f in MATERIAL_FIELDS if f in event]
            if all(candidate.get(f)==event.get(f) for f in fields):
                matched+=1
        scores.append(matched/max(1,total))
    mean=sum(scores)/len(scores) if scores else 1.0
    return {"sliding_window_reconstruction_fidelity":round(mean,6),"temporal_window_count":float(len(scores)),"worst_window_fidelity":round(min(scores) if scores else 1.0,6)}
