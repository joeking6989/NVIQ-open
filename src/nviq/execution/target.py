import json
import time
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _post_json(endpoint: str, payload: dict, *, bearer_token: str | None, timeout_s: float) -> dict:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Noct-Tech-NVIQ/0.1",
    }
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    request = Request(endpoint, data=data, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout_s) as response:
            raw = response.read()
    except HTTPError as exc:
        raise RuntimeError(f"NVIQ target HTTP {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"NVIQ target connection failed: {exc.reason}") from exc

    try:
        result = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError("NVIQ target returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("NVIQ target must return one evidence object per case")
    return result


def capture_http_target(
    cases: list[dict],
    endpoint: str,
    track: str,
    *,
    bearer_token: str | None = None,
    timeout_s: float = 30.0,
    retries: int = 0,
    retry_delay_s: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Capture evidence case by case without letting one failure lose the run.

    Transport failures (HTTP errors, connection errors, invalid JSON) are retried up
    to ``retries`` times. A case that still fails, or that returns the wrong case or
    track identity, is recorded in ``errors`` and capture continues. NVIQ then scores
    only what was captured; missing cases surface as coverage findings.
    """
    if retries < 0:
        raise ValueError("retries must be non-negative")
    evidence: list[dict] = []
    errors: list[dict] = []
    for case in sorted(cases, key=lambda item: item["case_id"]):
        payload = {"protocol_version": "0.1", "track": track, "case": case}
        attempts = 0
        row = None
        last_error = None
        while attempts <= retries:
            attempts += 1
            try:
                row = _post_json(endpoint, payload, bearer_token=bearer_token, timeout_s=timeout_s)
                break
            except RuntimeError as exc:
                last_error = str(exc)
                if attempts <= retries:
                    sleep(retry_delay_s)
        if row is None:
            errors.append({"case_id": case["case_id"], "track": track, "attempts": attempts, "error": last_error})
            continue
        if row.get("case_id") != case["case_id"] or row.get("track") != track:
            errors.append({
                "case_id": case["case_id"],
                "track": track,
                "attempts": attempts,
                "error": f"target returned case_id={row.get('case_id')!r} track={row.get('track')!r}",
            })
            continue
        evidence.append(row)
    return {"evidence": evidence, "errors": errors}


def run_http_target(
    cases: list[dict],
    endpoint: str,
    track: str,
    *,
    bearer_token: str | None = None,
    timeout_s: float = 30.0,
) -> list[dict]:
    evidence = []
    for case in sorted(cases, key=lambda item: item["case_id"]):
        payload = {"protocol_version": "0.1", "track": track, "case": case}
        row = _post_json(endpoint, payload, bearer_token=bearer_token, timeout_s=timeout_s)
        if row.get("case_id") != case["case_id"]:
            raise ValueError(f"target returned case_id {row.get('case_id')} for {case['case_id']}")
        if row.get("track") != track:
            raise ValueError(f"target returned track {row.get('track')} for requested {track}")
        evidence.append(row)
    return evidence
