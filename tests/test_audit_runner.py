import json

from nviq.audit.html import render_html
from nviq.audit.runner import run_audit, write_audit_artifacts
from nviq.audit.snapshot import build_snapshot
from nviq.runner import run_benchmark


def _case():
    return {"case_id":"NVIQ-COM-001","family":"confidence_channel_fidelity","scoring":{"metrics":[{"name":"accuracy","weight":1,"higher_is_better":True,"hard_gate":True,"threshold":1.0}],"catastrophic_failure_conditions":[]}}


def _observation():
    return {"case_id":"NVIQ-COM-001","track":"lsr_cvf","metrics":{"accuracy":1.0},"catastrophic_failures":[],"trace":{"claim":"grounded"},"evidence_refs":["trace-1"]}


def _manifest():
    return {"audit_id":"audit-001","customer_name":"Voice Co","target_name":"Agent","target_version":"1.0","created_at":"2026-09-02T16:00:00+10:00","benchmark_version":"0.2","case_set":"inline","tracks":["lsr_cvf"],"evidence_sources":[{"evidence_id":"trace-1","kind":"trace","ref":"trace://1"}],"retention_policy":{"raw_audio":"not_retained","derived_artifacts_days":90}}


def test_audit_preserves_core_benchmark_scores():
    core=run_benchmark([_case()],[_observation()])
    audit=run_audit(_manifest(),[_case()],[_observation()],[])
    assert audit["benchmark"]==core
    assert audit["summary"]["overall_status"]=="pass"
    assert audit["findings"]==[]


def test_html_is_self_contained_and_escaped():
    manifest=_manifest(); manifest["customer_name"]="Voice <Co>"
    audit=run_audit(manifest,[_case()],[_observation()],[])
    html=render_html(audit)
    assert "<!doctype html>" in html.lower()
    assert "Voice &lt;Co&gt;" in html
    assert "http://" not in html and "https://" not in html
    assert "<style>" in html


def test_audit_artifacts_include_json_html_and_snapshot(tmp_path):
    audit=run_audit(_manifest(),[_case()],[_observation()],[])
    paths=write_audit_artifacts(audit,tmp_path)
    assert set(paths)=={"json","html","snapshot"}
    parsed=json.loads(paths["json"].read_text(encoding="utf-8"))
    snapshot=json.loads(paths["snapshot"].read_text(encoding="utf-8"))
    assert parsed==audit
    assert snapshot==build_snapshot(audit)
    assert len(snapshot["audit_fingerprint_sha256"])==64
