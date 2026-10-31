from __future__ import annotations

def evaluate_floor_integrity(events:list[dict])->dict[str,float]:
    classes=("genuine_interruption","backchannel","other_directed_speech","background_speech")
    grouped={k:[e for e in events if e.get("class")==k] for k in classes}
    def rate(kind:str, desired:bool)->float:
        xs=grouped[kind]
        return round(sum(bool(e.get("yielded_floor"))==desired for e in xs)/len(xs),6) if xs else 1.0
    gi=rate("genuine_interruption",True)
    bc=rate("backchannel",False); od=rate("other_directed_speech",False); bg=rate("background_speech",False)
    return {"genuine_interruption_response":gi,"backchannel_non_interruption":bc,"other_directed_speech_non_interruption":od,"background_speech_non_interruption":bg,"conversational_floor_integrity":min(gi,bc,od,bg)}
