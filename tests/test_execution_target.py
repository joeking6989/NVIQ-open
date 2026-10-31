import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from nviq.execution.target import run_http_target


def _case(case_id):
    return {
        "case_id": case_id,
        "family": "abstention_fidelity",
        "ground_truth": {"message_presence_probability": 0.0},
        "expected_policy": {"action_mode": "abstain"},
        "scoring": {"metrics": [], "catastrophic_failure_conditions": []},
    }


class _Handler(BaseHTTPRequestHandler):
    requests = []

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        body = json.loads(self.rfile.read(length))
        self.__class__.requests.append((self.path, body, self.headers.get("Authorization")))
        case_id = body["case"]["case_id"]
        payload = {
            "evidence_version": "0.1",
            "case_id": case_id,
            "track": body["track"],
            "message": {"presence_probability": 0.0, "lexical_output": None, "abstained": True},
            "provenance": {"evidence_refs": [f"target-test/{case_id}"]},
        }
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_args):
        return


def test_http_target_posts_each_case_and_collects_evidence():
    _Handler.requests = []
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        rows = run_http_target(
            [_case("NVIQ-A-001"), _case("NVIQ-B-001")],
            f"http://127.0.0.1:{server.server_port}/nviq",
            "lsr_cvf",
            bearer_token="secret",
        )
    finally:
        server.shutdown()
        thread.join()
    assert [row["case_id"] for row in rows] == ["NVIQ-A-001", "NVIQ-B-001"]
    assert len(_Handler.requests) == 2
    assert _Handler.requests[0][2] == "Bearer secret"
    assert _Handler.requests[0][1]["protocol_version"] == "0.1"
    assert rows[0]["provenance"]["evidence_refs"] == ["target-test/NVIQ-A-001"]


def test_http_target_rejects_mismatched_case_identity(monkeypatch):
    from nviq.execution import target

    monkeypatch.setattr(
        target,
        "_post_json",
        lambda *_args, **_kwargs: {"evidence_version": "0.1", "case_id": "NVIQ-WRONG", "track": "lsr_cvf", "provenance": {"evidence_refs": ["target-test/wrong"]}},
    )
    with pytest.raises(ValueError, match="returned case_id"):
        run_http_target([_case("NVIQ-A-001")], "http://example.invalid", "lsr_cvf")


class _FlakyHandler(BaseHTTPRequestHandler):
    """Fails NVIQ-B-001 once with HTTP 503, always fails NVIQ-C-001, answers the rest."""

    calls = {}

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        body = json.loads(self.rfile.read(length))
        case_id = body["case"]["case_id"]
        self.__class__.calls[case_id] = self.__class__.calls.get(case_id, 0) + 1
        if case_id == "NVIQ-C-001" or (case_id == "NVIQ-B-001" and self.__class__.calls[case_id] == 1):
            self.send_response(503)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        payload = {
            "evidence_version": "0.1",
            "case_id": case_id,
            "track": body["track"],
            "message": {"presence_probability": 0.0, "lexical_output": None, "abstained": True},
            "provenance": {"evidence_refs": [f"target-test/{case_id}"]},
        }
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_args):
        return


def _serve(handler):
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_capture_keeps_partial_evidence_and_records_errors():
    from nviq.execution.target import capture_http_target

    _FlakyHandler.calls = {}
    server, thread = _serve(_FlakyHandler)
    try:
        result = capture_http_target(
            [_case("NVIQ-A-001"), _case("NVIQ-B-001"), _case("NVIQ-C-001")],
            f"http://127.0.0.1:{server.server_port}/nviq",
            "lsr_cvf",
            retries=1,
            retry_delay_s=0,
            sleep=lambda _s: None,
        )
    finally:
        server.shutdown()
        thread.join()
    assert [row["case_id"] for row in result["evidence"]] == ["NVIQ-A-001", "NVIQ-B-001"]
    assert len(result["errors"]) == 1
    assert result["errors"][0]["case_id"] == "NVIQ-C-001"
    assert result["errors"][0]["attempts"] == 2
    assert "503" in result["errors"][0]["error"]
    assert _FlakyHandler.calls["NVIQ-B-001"] == 2


def test_capture_records_identity_mismatch_instead_of_aborting(monkeypatch):
    from nviq.execution import target

    monkeypatch.setattr(
        target,
        "_post_json",
        lambda *_args, **_kwargs: {"evidence_version": "0.1", "case_id": "NVIQ-WRONG", "track": "lsr_cvf", "provenance": {"evidence_refs": ["x"]}},
    )
    result = target.capture_http_target([_case("NVIQ-A-001"), _case("NVIQ-B-001")], "http://example.invalid", "lsr_cvf")
    assert result["evidence"] == []
    assert [row["case_id"] for row in result["errors"]] == ["NVIQ-A-001", "NVIQ-B-001"]


def test_target_cli_writes_partial_evidence_and_flags_incomplete_capture(tmp_path):
    from pathlib import Path

    from nviq.cli import EXIT_CAPTURE_INCOMPLETE, main

    root = Path(__file__).resolve().parents[1]
    cases = [
        {
            "case_id": case_id,
            "version": "0.2",
            "family": "abstention_fidelity",
            "title": "Abstain on message-free audio",
            "input": {"audio_ref": "fixture://none"},
            "ground_truth": {"message_presence_probability": 0.0},
            "context": {},
            "expected_policy": {"action_mode": "abstain"},
            "scoring": {
                "metrics": [{"name": "abstention_accuracy", "weight": 1, "higher_is_better": True, "hard_gate": True, "threshold": 1.0}],
                "catastrophic_failure_conditions": ["fabricated_speech"],
            },
        }
        for case_id in ("NVIQ-A-001", "NVIQ-B-001", "NVIQ-C-001")
    ]
    case_path = tmp_path / "cases.json"
    case_path.write_text(json.dumps(cases), encoding="utf-8")
    manifest = json.loads((root / "examples/audit/executable-p0-manifest.json").read_text(encoding="utf-8"))
    manifest["case_set"] = str(case_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    _FlakyHandler.calls = {}
    server, thread = _serve(_FlakyHandler)
    try:
        code = main([
            "target", "run",
            "--manifest", str(manifest_path),
            "--endpoint", f"http://127.0.0.1:{server.server_port}/nviq",
            "--output-dir", str(tmp_path / "out"),
            "--retries", "1",
            "--retry-delay", "0",
            "--manifest-schema", str(root / "src/nviq/schemas/audit-manifest.v0.1.schema.json"),
            "--case-schema", str(root / "src/nviq/schemas/test-case.v0.2.schema.json"),
            "--evidence-schema", str(root / "src/nviq/schemas/evidence-bundle.v0.1.schema.json"),
            "--causal-ledger-schema", str(root / "src/nviq/schemas/causal-speech-ledger.v0.1.schema.json"),
            "--remediations", str(root / "src/nviq/data/remediations.v0.1.json"),
        ])
    finally:
        server.shutdown()
        thread.join()
    out = tmp_path / "out"
    assert code == EXIT_CAPTURE_INCOMPLETE
    captured = json.loads((out / "captured-evidence.json").read_text(encoding="utf-8"))
    errors = json.loads((out / "capture-errors.json").read_text(encoding="utf-8"))
    report = json.loads((out / "audit-report.json").read_text(encoding="utf-8"))
    assert [row["case_id"] for row in captured] == ["NVIQ-A-001", "NVIQ-B-001"]
    assert [row["case_id"] for row in errors] == ["NVIQ-C-001"]
    assert report["coverage"]["tracks"]["lsr_cvf"]["missing_case_ids"] == ["NVIQ-C-001"]
    assert report["summary"]["overall_status"] == "action_required"
