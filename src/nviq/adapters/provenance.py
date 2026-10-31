"""Provenance rules shared by every provider adapter."""


def require_capture_origin(value: object, source: str) -> str:
    """Every evidence source must say whether it came from a live runtime or a fixture.

    There is deliberately no default: an unlabelled fixture must never be read as
    runtime evidence.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f'{source}: capture_origin is required (for example "runtime" or "adapter_contract_fixture")'
        )
    return value.strip()
