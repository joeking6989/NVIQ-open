import json
from pathlib import Path

from nviq.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_ingest_openai_realtime_writes_valid_evidence_bundle(tmp_path, capsys):
    events = tmp_path / "trace.jsonl"
    events.write_text(
        json.dumps({
            "type": "conversation.item.input_audio_transcription.completed",
            "event_id": "ev-empty",
            "item_id": "user-1",
            "transcript": "",
            "logprobs": [],
        }) + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "evidence.json"
    code = main([
        "ingest",
        "openai-realtime",
        "--cases", str(ROOT / "cases/v0.2/executable-p0.json"),
        "--case-id", "NVIQ-ABSTAIN-001",
        "--events", str(events),
        "--capture-origin", "adapter_contract_fixture",
        "--track", "audio_native",
        "--output", str(output),
    ])
    assert code == 0
    bundle = json.loads(output.read_text(encoding="utf-8"))
    assert len(bundle) == 1
    assert bundle[0]["case_id"] == "NVIQ-ABSTAIN-001"
    assert bundle[0]["message"]["abstained"] is True
    assert bundle[0]["provenance"]["provider"] == "openai"
    assert "wrote 1 evidence record" in capsys.readouterr().out


def test_ingest_openai_realtime_trace_manifest_writes_multiple_records(tmp_path, capsys):
    trace_manifest = tmp_path / "trace-manifest.json"
    trace_manifest.write_text(json.dumps({
        "trace_version": "0.1",
        "capture_origin": "adapter_contract_fixture",
        "default_track": "audio_native",
        "sessions": [
            {
                "case_id": "NVIQ-ABSTAIN-001",
                "events": [{
                    "type": "conversation.item.input_audio_transcription.completed",
                    "event_id": "ev-a",
                    "item_id": "user-a",
                    "transcript": "",
                    "logprobs": [],
                }],
            },
            {
                "case_id": "NVIQ-UNC-001",
                "events": [
                    {
                        "type": "conversation.item.input_audio_transcription.completed",
                        "event_id": "ev-u",
                        "item_id": "user-u",
                        "transcript": "Miller or Millar",
                        "logprobs": [{"token": "Miller", "logprob": -0.1, "bytes": []}],
                    },
                    {
                        "type": "nviq.evidence",
                        "event_id": "nviq-u",
                        "evidence": {"confidence": {"authoritative": 0.55, "expressed": 0.55, "action_mode": "clarify"}},
                    },
                ],
            },
        ],
    }), encoding="utf-8")
    output = tmp_path / "evidence-batch.json"
    code = main([
        "ingest",
        "openai-realtime",
        "--cases", str(ROOT / "cases/v0.2/executable-p0.json"),
        "--trace-manifest", str(trace_manifest),
        "--output", str(output),
    ])
    assert code == 0
    bundle = json.loads(output.read_text(encoding="utf-8"))
    assert [row["case_id"] for row in bundle] == ["NVIQ-ABSTAIN-001", "NVIQ-UNC-001"]
    assert bundle[1]["confidence"]["authoritative"] == 0.55
    assert "wrote 2 evidence record" in capsys.readouterr().out
