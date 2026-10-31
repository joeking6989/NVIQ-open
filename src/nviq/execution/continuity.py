from __future__ import annotations

def evaluate_long_silence(events:list[dict], threshold_ms:float=5000.0)->dict[str,float]:
    gaps=[e for e in events if float(e.get("silence_ms",0))>=threshold_ms]
    if not gaps:
        return {"long_silence_state_retention":1.0,"long_silence_speaker_retention":1.0,"long_silence_continuity":1.0}
    state=sum(bool(e.get("state_preserved")) for e in gaps)/len(gaps)
    speaker=sum(bool(e.get("speaker_preserved")) for e in gaps)/len(gaps)
    return {"long_silence_state_retention":round(state,6),"long_silence_speaker_retention":round(speaker,6),"long_silence_continuity":round(min(state,speaker),6)}
