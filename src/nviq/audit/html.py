from html import escape


def _finding_rows(findings: list[dict]) -> str:
    if not findings:
        return '<tr><td colspan="5">No material findings.</td></tr>'
    rows = []
    for finding in findings:
        remediations = ", ".join(item["title"] for item in finding.get("remediations", [])) or "—"
        rows.append("<tr>" f"<td>{escape(finding['severity'])}</td>" f"<td>{escape(finding['family'])}</td>" f"<td>{escape(finding['case_id'])}</td>" f"<td>{escape(finding['summary'])}</td>" f"<td>{escape(remediations)}</td>" "</tr>")
    return "".join(rows)


def _track_rows(benchmark: dict) -> str:
    rows = []
    for name, track in sorted(benchmark.get("tracks", {}).items()):
        rows.append("<tr>" f"<td>{escape(name)}</td>" f"<td>{track['case_count']}</td>" f"<td>{track['mean_score']:.3f}</td>" f"<td>{track['hard_gate_failures']}</td>" f"<td>{track['catastrophic_failures']}</td>" "</tr>")
    return "".join(rows) or '<tr><td colspan="5">No scored tracks.</td></tr>'


def _coverage_rows(audit_report: dict) -> str:
    coverage = audit_report.get("coverage")
    if not coverage:
        return '<tr><td colspan="3">Coverage not recorded.</td></tr>'
    rows = []
    for name, track in sorted(coverage.get("tracks", {}).items()):
        missing = ", ".join(track["missing_case_ids"]) or "—"
        rows.append("<tr>" f"<td>{escape(name)}</td>" f"<td>{track['observed_case_count']} of {track['expected_case_count']}</td>" f"<td>{escape(missing)}</td>" "</tr>")
    return "".join(rows) or '<tr><td colspan="3">No enabled tracks.</td></tr>'


def render_html(audit_report: dict) -> str:
    manifest = audit_report["manifest"]
    summary = audit_report["summary"]
    findings = audit_report.get("findings", [])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NVIQ Reliability Audit — {escape(manifest['target_name'])}</title>
<style>body{{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#0b1020;color:#e8eef7}}main{{max-width:1100px;margin:0 auto;padding:40px 24px}}h1,h2{{color:#fff}}.brand{{color:#4dd7ff;font-weight:700;letter-spacing:.08em}}.card{{background:#141b2d;border:1px solid #28334b;border-radius:14px;padding:20px;margin:18px 0}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #28334b;vertical-align:top}}th{{color:#9ddfff}}.status{{font-size:1.15rem;font-weight:700}}.muted{{color:#aab7ca}}</style>
</head><body><main><div class="brand">NOCT-TECH / NVIQ</div><h1>NVIQ Reliability Audit</h1>
<div class="card"><div class="status">Status: {escape(summary['overall_status'])}</div><p><strong>Customer:</strong> {escape(manifest['customer_name'])}</p><p><strong>Target:</strong> {escape(manifest['target_name'])} / {escape(manifest['target_version'])}</p><p class="muted">Audit {escape(manifest['audit_id'])} · Benchmark {escape(manifest['benchmark_version'])}</p><p>{escape(summary['executive_summary'])}</p></div>
<h2>Capability scorecard</h2><div class="card"><table><thead><tr><th>Track</th><th>Cases</th><th>Mean score</th><th>Hard gates</th><th>Catastrophic</th></tr></thead><tbody>{_track_rows(audit_report['benchmark'])}</tbody></table></div>
<h2>Coverage</h2><div class="card"><table><thead><tr><th>Track</th><th>Cases evaluated</th><th>Not evaluated</th></tr></thead><tbody>{_coverage_rows(audit_report)}</tbody></table></div>
<h2>Material findings</h2><div class="card"><table><thead><tr><th>Severity</th><th>Family</th><th>Case</th><th>Finding</th><th>Remediation</th></tr></thead><tbody>{_finding_rows(findings)}</tbody></table></div>
<h2>Methodology</h2><div class="card"><p>NVIQ preserves numeric benchmark scores separately from hard-gate and catastrophic failures. Commercial findings are deterministically derived from benchmark evidence; report presentation does not rewrite the underlying score.</p></div>
</main></body></html>"""
