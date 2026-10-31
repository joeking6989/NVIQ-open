from __future__ import annotations

def evaluate_speaker_state(events: list[dict]) -> dict[str, float]:
    observed=[e for e in events if e.get("expected_speaker_id") is not None]
    if not observed:
        return {"speaker_identity_continuity":1.0,"speaker_attribution_accuracy":1.0,"overlap_ownership_accuracy":1.0,"speaker_switch_accuracy":1.0,"speaker_state_preservation":1.0}
    def ratio(key:str)->float:
        relevant=[e for e in observed if key in e]
        return round(sum(bool(e[key]) for e in relevant)/len(relevant),6) if relevant else 1.0
    identity=round(sum(e.get("speaker_id")==e.get("expected_speaker_id") for e in observed)/len(observed),6)
    metrics={"speaker_identity_continuity":identity,"speaker_attribution_accuracy":identity,"overlap_ownership_accuracy":ratio("overlap_owner_correct"),"speaker_switch_accuracy":ratio("speaker_switch_correct")}
    metrics["speaker_state_preservation"]=min(metrics.values())
    return metrics
