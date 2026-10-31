"""Experimental evaluator (NVIQ audit 18 Oct 2026, finding D9).

Not reachable from the CLI or the execution runner: no benchmark family or case
set uses it yet, so it never contributes to an audit. Wire it to a family with
real cases before relying on it.
"""

from __future__ import annotations

MATERIAL_CHANNELS=("lexical","uncertainty","prosody","overlap","repair","floor_state","speaker_identity","provenance")

def evaluate_lossless_optimization(reference:dict, candidate:dict)->dict[str,float]:
    preserved=[]
    for channel in MATERIAL_CHANNELS:
        expected=reference.get(channel)
        actual=candidate.get(channel)
        if expected in (None,[],{}):
            continue
        preserved.append(1.0 if actual==expected else 0.0)
    fidelity=sum(preserved)/len(preserved) if preserved else 1.0
    compression=float(candidate.get("compression_ratio",1.0))
    utility=float(candidate.get("task_utility",1.0))
    material_loss=1.0-fidelity
    qualifies=1.0 if material_loss==0.0 else 0.0
    return {"lossless_representation_fidelity":round(fidelity,6),"optimization_induced_information_loss":round(material_loss,6),"compression_ratio":round(compression,6),"task_utility":round(utility,6),"lossless_optimization_qualification":qualifies}

def compression_boundary(reference:dict,candidates:list[dict])->dict:
    results=[evaluate_lossless_optimization(reference,c) for c in candidates]
    safe=[(i,r) for i,r in enumerate(results) if r["lossless_optimization_qualification"]==1.0]
    if not safe:
        return {"max_safe_compression_ratio":0.0,"safe_candidate_index":-1,"results":results}
    index,result=max(safe,key=lambda pair:pair[1]["compression_ratio"])
    return {"max_safe_compression_ratio":result["compression_ratio"],"safe_candidate_index":index,"results":results}
