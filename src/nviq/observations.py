import json
import math
from pathlib import Path

from .errors import ObservationValidationError

TRACKS = {
    "transcript_only",
    "transcript_metadata",
    "audio_native",
    "lsr_cvf",
    "oracle",
}


def validate_observation(observation: dict, known_case_ids: set[str]) -> None:
    if not isinstance(observation, dict):
        raise ObservationValidationError("observation must be an object")
    case_id = observation.get("case_id")
    if case_id not in known_case_ids:
        raise ObservationValidationError(f"unknown case_id: {case_id}")
    track = observation.get("track")
    if track not in TRACKS:
        raise ObservationValidationError(f"invalid track: {track}")
    metrics = observation.get("metrics")
    if not isinstance(metrics, dict):
        raise ObservationValidationError("metrics must be an object")
    for name, value in metrics.items():
        if isinstance(value, bool):
            continue
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ObservationValidationError(f"metric {name} must be a finite number or boolean")
    failures = observation.get("catastrophic_failures", [])
    if not isinstance(failures, list) or not all(isinstance(item, str) for item in failures):
        raise ObservationValidationError("catastrophic_failures must be a list of strings")


def load_observations(path: Path, known_case_ids: set[str]) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ObservationValidationError(f"observation file must contain a JSON array: {path}")
    seen: set[tuple[str, str]] = set()
    for observation in data:
        validate_observation(observation, known_case_ids)
        key = (observation["case_id"], observation["track"])
        if key in seen:
            raise ObservationValidationError(f"duplicate observation for {key[0]} on {key[1]}")
        seen.add(key)
    return data
