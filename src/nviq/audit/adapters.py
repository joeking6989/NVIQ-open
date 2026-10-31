from copy import deepcopy


def adapt_precomputed_observations(
    observations: list[dict],
    *,
    provider: str = "precomputed",
    model: str | None = None,
    configuration: dict | None = None,
) -> list[dict]:
    """Normalize already-produced observations without assigning NVIQ scores."""
    adapted: list[dict] = []
    for observation in observations:
        item = deepcopy(observation)
        item["adapter"] = {
            "kind": "precomputed",
            "provider": provider,
            "model": model,
            "configuration": deepcopy(configuration or {}),
        }
        item["execution"] = {"status": "success", "failure_reason": None}
        adapted.append(item)
    return adapted
