from collections import defaultdict

from .scoring import score_case


def _summary(results: list[dict]) -> dict:
    count = len(results)
    mean_score = round(sum(item["score"] for item in results) / count, 6) if count else 0.0
    return {
        "case_count": count,
        "mean_score": mean_score,
        "hard_gate_failures": sum(not item["hard_gate_pass"] for item in results),
        "catastrophic_failures": sum(item["catastrophic_failure"] for item in results),
    }


def run_benchmark(cases: list[dict], observations: list[dict]) -> dict:
    cases_by_id = {case["case_id"]: case for case in cases}
    observed_case_ids = {observation["case_id"] for observation in observations}
    missing = [{"case_id": case["case_id"]} for case in cases if case["case_id"] not in observed_case_ids]

    results_by_track: dict[str, list[dict]] = defaultdict(list)
    for observation in observations:
        case = cases_by_id[observation["case_id"]]
        results_by_track[observation["track"]].append(score_case(case, observation))

    tracks = {}
    for track, results in sorted(results_by_track.items()):
        family_results: dict[str, list[dict]] = defaultdict(list)
        for result in results:
            family_results[result["family"]].append(result)
        track_summary = _summary(results)
        track_summary["families"] = {
            family: _summary(items) for family, items in sorted(family_results.items())
        }
        track_summary["cases"] = sorted(results, key=lambda item: item["case_id"])
        tracks[track] = track_summary

    return {
        "nviq_version": "0.2",
        "tracks": tracks,
        "missing_observations": missing,
    }
