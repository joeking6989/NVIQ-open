import json
from pathlib import Path

from nviq.cli import main

ROOT = Path(__file__).resolve().parents[1]


def _write_fixture(tmp_path):
    cases=[{"case_id":"NVIQ-AUD-001","version":"0.2","family":"confidence_channel_fidelity","title":"Commercial audit fixture","input":{"audio_ref":"none.wav"},"ground_truth":{},"context":{},"expected_policy":{"action_mode":"observe_only"},"scoring":{"metrics":[{"name":"accuracy","weight":1,"higher_is_better":True,"hard_gate":True,"threshold":1.0}],"catastrophic_failure_conditions":["false_claim"]}}]
    case_schema={"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object","required":["case_id","family","scoring"]}
    case_path=tmp_path/"cases.json"; case_path.write_text(json.dumps(cases),encoding="utf-8")
    schema_path=tmp_path/"case-schema.json"; schema_path.write_text(json.dumps(case_schema),encoding="utf-8")
    observations=[{"case_id":"NVIQ-AUD-001","track":"lsr_cvf","metrics":{"accuracy":1.0},"catastrophic_failures":[],"trace":{"ok":True},"evidence_refs":["trace-1"]}]
    obs_path=tmp_path/"observations.json"; obs_path.write_text(json.dumps(observations),encoding="utf-8")
    manifest={"audit_id":"audit-cli-001","customer_name":"Voice Co","target_name":"Agent","target_version":"1","created_at":"2026-09-02T16:00:00+10:00","benchmark_version":"0.2","case_set":str(case_path),"tracks":["lsr_cvf"],"evidence_sources":[{"evidence_id":"trace-1","kind":"trace","ref":"trace://1"}],"retention_policy":{"raw_audio":"not_retained","derived_artifacts_days":90}}
    manifest_path=tmp_path/"manifest.json"; manifest_path.write_text(json.dumps(manifest),encoding="utf-8")
    return manifest_path,obs_path,schema_path


def test_audit_validate_manifest_command(tmp_path,capsys):
    manifest_path,_,_=_write_fixture(tmp_path)
    code=main(["audit","validate-manifest","--manifest",str(manifest_path),"--manifest-schema",str(ROOT/"src/nviq/schemas/audit-manifest.v0.1.schema.json")])
    assert code==0
    assert "validated audit manifest" in capsys.readouterr().out


def test_audit_run_command_writes_commercial_artifacts(tmp_path,capsys):
    manifest_path,obs_path,case_schema=_write_fixture(tmp_path)
    output=tmp_path/"out"
    code=main(["audit","run","--manifest",str(manifest_path),"--manifest-schema",str(ROOT/"src/nviq/schemas/audit-manifest.v0.1.schema.json"),"--case-schema",str(case_schema),"--observations",str(obs_path),"--remediations",str(ROOT/"src/nviq/data/remediations.v0.1.json"),"--output-dir",str(output)])
    assert code==0
    assert (output/"audit-report.json").exists()
    assert (output/"audit-report.html").exists()
    assert (output/"regression-snapshot.json").exists()
    assert "NVIQ Reliability Audit" in capsys.readouterr().out


def test_audit_compare_command_vetoes_new_catastrophic_failure(tmp_path):
    base={"manifest":{"audit_id":"base"},"benchmark":{"tracks":{},"missing_observations":[]},"findings":[]}
    cand={"manifest":{"audit_id":"cand"},"benchmark":{"tracks":{},"missing_observations":[]},"findings":[{"finding_id":"F-cat","finding_type":"catastrophic_failure","severity":"Critical"}]}
    base_path=tmp_path/"base.json"; base_path.write_text(json.dumps(base),encoding="utf-8")
    cand_path=tmp_path/"cand.json"; cand_path.write_text(json.dumps(cand),encoding="utf-8")
    out=tmp_path/"compare"
    code=main(["audit","compare","--baseline",str(base_path),"--candidate",str(cand_path),"--output-dir",str(out)])
    assert code==0
    result=json.loads((out/"audit-comparison.json").read_text(encoding="utf-8"))
    assert result["recommendation"]=="candidate_rejected_new_catastrophic_failure"
