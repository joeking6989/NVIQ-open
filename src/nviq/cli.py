import argparse
import json
import os
import sys
from pathlib import Path

from .adapters.openai_realtime import (
    adapt_openai_realtime_events,
    adapt_openai_realtime_trace_manifest,
    load_realtime_events,
)
from .adapters.gemini_live import adapt_gemini_live_trace_manifest
from .adapters.realtime_venus import adapt_realtime_venus_trace_manifest
from .audit.adapters import adapt_precomputed_observations
from .audit.compare import compare_audits
from .audit.manifest import load_manifest, validate_manifest
from .audit.remediations import load_remediations
from .audit.runner import run_audit, write_audit_artifacts
from .cases import load_cases, load_schema, validate_cases
from .errors import EvidenceValidationError
from .execution.evidence import load_evidence, validate_evidence
from .execution.runner import execute_audit
from .execution.target import capture_http_target
from .observations import load_observations
from . import __version__
from .errors import NVIQError
from .reporting import write_report
from .resources import (
    AUDIT_MANIFEST_SCHEMA,
    CAUSAL_LEDGER_SCHEMA,
    EVIDENCE_BUNDLE_SCHEMA,
    REMEDIATION_REGISTRY,
    TEST_CASE_SCHEMA,
)
from .realtime_venus_qualification import qualify_realtime_venus_runtime
from .runner import run_benchmark


# Process exit codes (documented in README).
EXIT_OK = 0
EXIT_ERROR = 1  # invalid input or NVIQ error; one-line message on stderr
EXIT_USAGE_OR_NOT_QUALIFIED = 2  # argparse usage error, or `qualify` receipt not qualified
EXIT_GATE_FAILED = 3  # --fail-on threshold reached
EXIT_CAPTURE_INCOMPLETE = 4  # `target run` could not capture every case

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_FAIL_ON_CHOICES = ["critical", "high", "medium", "low", "none"]

_TRACKS = ["transcript_only", "transcript_metadata", "audio_native", "lsr_cvf", "oracle"]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nviq", description="Noct-Tech NVIQ benchmark and execution engine")
    parser.add_argument("--version", action="version", version=f"nviq {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate NVIQ test cases")
    validate.add_argument("--schema", type=Path, default=TEST_CASE_SCHEMA, help="test-case schema (default: bundled v0.2)")
    validate.add_argument("--cases", type=Path, required=True)

    score = sub.add_parser("score", help="score track observations")
    score.add_argument("--schema", type=Path, default=TEST_CASE_SCHEMA, help="test-case schema (default: bundled v0.2)")
    score.add_argument("--cases", type=Path, required=True)
    score.add_argument("--observations", type=Path, required=True)
    score.add_argument("--output", type=Path, required=True)

    audit = sub.add_parser("audit", help="run NVIQ commercial Reliability Audits")
    audit_sub = audit.add_subparsers(dest="audit_command", required=True)

    audit_validate = audit_sub.add_parser("validate-manifest", help="validate a commercial audit manifest")
    audit_validate.add_argument("--manifest", type=Path, required=True)
    audit_validate.add_argument("--manifest-schema", type=Path, default=AUDIT_MANIFEST_SCHEMA)

    audit_run = audit_sub.add_parser("run", help="run a commercial NVIQ Reliability Audit from precomputed observations")
    audit_run.add_argument("--manifest", type=Path, required=True)
    audit_run.add_argument("--manifest-schema", type=Path, default=AUDIT_MANIFEST_SCHEMA)
    audit_run.add_argument("--case-schema", type=Path, default=TEST_CASE_SCHEMA)
    audit_run.add_argument("--observations", type=Path, required=True)
    audit_run.add_argument("--remediations", type=Path, default=REMEDIATION_REGISTRY)
    audit_run.add_argument("--output-dir", type=Path, required=True)
    audit_run.add_argument(
        "--fail-on",
        choices=_FAIL_ON_CHOICES,
        default="none",
        help="exit 3 when any finding is at or above this severity (default: none)",
    )

    audit_compare = audit_sub.add_parser("compare", help="compare two canonical NVIQ audit reports")
    audit_compare.add_argument("--baseline", type=Path, required=True)
    audit_compare.add_argument("--candidate", type=Path, required=True)
    audit_compare.add_argument("--output-dir", type=Path, required=True)

    evidence = sub.add_parser("evidence", help="validate raw NVIQ execution evidence")
    evidence_sub = evidence.add_subparsers(dest="evidence_command", required=True)
    evidence_validate = evidence_sub.add_parser("validate", help="validate an Evidence Bundle v0.1")
    evidence_validate.add_argument("--evidence", type=Path, required=True)
    evidence_validate.add_argument("--schema", type=Path, default=EVIDENCE_BUNDLE_SCHEMA)
    evidence_validate.add_argument("--cases", type=Path)
    evidence_validate.add_argument("--case-schema", type=Path, default=TEST_CASE_SCHEMA)
    evidence_validate.add_argument("--causal-ledger-schema", type=Path, default=CAUSAL_LEDGER_SCHEMA)

    ingest = sub.add_parser("ingest", help="convert provider traces into NVIQ Evidence Bundle records")
    ingest_sub = ingest.add_subparsers(dest="ingest_command", required=True)
    openai_realtime = ingest_sub.add_parser("openai-realtime", help="ingest captured OpenAI Realtime JSON/JSONL traces")
    openai_realtime.add_argument("--cases", type=Path, required=True)
    openai_realtime.add_argument("--case-id")
    openai_realtime.add_argument("--events", type=Path)
    openai_realtime.add_argument("--trace-manifest", type=Path)
    openai_realtime.add_argument("--track", choices=_TRACKS)
    openai_realtime.add_argument("--output", type=Path, required=True)
    openai_realtime.add_argument("--model")
    openai_realtime.add_argument("--session-id")
    openai_realtime.add_argument("--audio-ref")
    openai_realtime.add_argument(
        "--capture-origin",
        help='required with --events: "runtime" for live captures, "adapter_contract_fixture" for hand-built traces',
    )
    openai_realtime.add_argument("--case-schema", type=Path, default=TEST_CASE_SCHEMA)
    openai_realtime.add_argument("--evidence-schema", type=Path, default=EVIDENCE_BUNDLE_SCHEMA)

    gemini_live = ingest_sub.add_parser("gemini-live", help="ingest instrumented Gemini Live capture manifests")
    gemini_live.add_argument("--cases", type=Path, required=True)
    gemini_live.add_argument("--trace-manifest", type=Path, required=True)
    gemini_live.add_argument("--output", type=Path, required=True)
    gemini_live.add_argument("--case-schema", type=Path, default=TEST_CASE_SCHEMA)
    gemini_live.add_argument("--evidence-schema", type=Path, default=EVIDENCE_BUNDLE_SCHEMA)

    realtime_venus = ingest_sub.add_parser("realtime-venus", help="ingest instrumented Realtime-Venus capture manifests")
    realtime_venus.add_argument("--cases", type=Path, required=True)
    realtime_venus.add_argument("--trace-manifest", type=Path, required=True)
    realtime_venus.add_argument("--output", type=Path, required=True)
    realtime_venus.add_argument("--case-schema", type=Path, default=TEST_CASE_SCHEMA)
    realtime_venus.add_argument("--evidence-schema", type=Path, default=EVIDENCE_BUNDLE_SCHEMA)
    realtime_venus.add_argument("--causal-ledger-schema", type=Path, default=CAUSAL_LEDGER_SCHEMA)

    execute = sub.add_parser("execute", help="derive NVIQ observations from raw evidence and run a Reliability Audit")
    execute.add_argument("--manifest", type=Path, required=True)
    execute.add_argument("--evidence", type=Path, required=True)
    execute.add_argument("--output-dir", type=Path, required=True)
    execute.add_argument(
        "--fail-on",
        choices=_FAIL_ON_CHOICES,
        default="none",
        help="exit 3 when any finding is at or above this severity (default: none)",
    )
    execute.add_argument("--manifest-schema", type=Path, default=AUDIT_MANIFEST_SCHEMA)
    execute.add_argument("--case-schema", type=Path, default=TEST_CASE_SCHEMA)
    execute.add_argument("--evidence-schema", type=Path, default=EVIDENCE_BUNDLE_SCHEMA)
    execute.add_argument("--causal-ledger-schema", type=Path, default=CAUSAL_LEDGER_SCHEMA)
    execute.add_argument("--remediations", type=Path, default=REMEDIATION_REGISTRY)

    target = sub.add_parser("target", help="execute benchmark cases against a live target adapter")
    target_sub = target.add_subparsers(dest="target_command", required=True)
    target_run = target_sub.add_parser("run", help="capture raw evidence from an HTTP JSON target and run NVIQ")
    target_run.add_argument("--manifest", type=Path, required=True)
    target_run.add_argument("--endpoint", required=True)
    target_run.add_argument("--output-dir", type=Path, required=True)
    target_run.add_argument(
        "--fail-on",
        choices=_FAIL_ON_CHOICES,
        default="none",
        help="exit 3 when any finding is at or above this severity (default: none)",
    )
    target_run.add_argument("--track")
    target_run.add_argument("--token-env", default="NVIQ_TARGET_BEARER_TOKEN")
    target_run.add_argument("--timeout", type=float, default=30.0)
    target_run.add_argument("--retries", type=int, default=0, help="retries per case on transport failure (default 0)")
    target_run.add_argument("--retry-delay", type=float, default=1.0, help="seconds between retries (default 1.0)")
    target_run.add_argument("--manifest-schema", type=Path, default=AUDIT_MANIFEST_SCHEMA)
    target_run.add_argument("--case-schema", type=Path, default=TEST_CASE_SCHEMA)
    target_run.add_argument("--evidence-schema", type=Path, default=EVIDENCE_BUNDLE_SCHEMA)
    target_run.add_argument("--causal-ledger-schema", type=Path, default=CAUSAL_LEDGER_SCHEMA)
    target_run.add_argument("--remediations", type=Path, default=REMEDIATION_REGISTRY)

    qualify = sub.add_parser("qualify", help="issue deterministic frontier qualification receipts")
    qualify_sub = qualify.add_subparsers(dest="qualify_command", required=True)
    venus_qualify = qualify_sub.add_parser(
        "realtime-venus",
        help="qualify authentic Realtime-Venus runtime evidence",
    )
    venus_qualify.add_argument("--cases", type=Path, required=True)
    venus_qualify.add_argument("--evidence", type=Path, required=True)
    venus_qualify.add_argument("--execution-dir", type=Path, required=True)
    venus_qualify.add_argument("--output", type=Path, required=True)
    venus_qualify.add_argument("--case-schema", type=Path, default=TEST_CASE_SCHEMA)
    venus_qualify.add_argument("--evidence-schema", type=Path, default=EVIDENCE_BUNDLE_SCHEMA)
    venus_qualify.add_argument("--causal-ledger-schema", type=Path, default=CAUSAL_LEDGER_SCHEMA)
    return parser


def _read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def _resolve_case_set(manifest_path: Path, case_set: str) -> Path:
    """Resolve a manifest case_set as given, then relative to the manifest and its parent folders."""
    supplied = Path(case_set)
    if supplied.is_absolute() or supplied.exists():
        return supplied
    for base in (manifest_path.parent, *manifest_path.resolve().parent.parents):
        candidate = base / supplied
        if candidate.exists():
            return candidate
    return supplied


def _gate_exit(args: argparse.Namespace, report: dict) -> int:
    threshold = getattr(args, "fail_on", "none")
    if threshold == "none":
        return EXIT_OK
    limit = _SEVERITY_RANK[threshold]
    hits = [item for item in report.get("findings", []) if _SEVERITY_RANK[item["severity"].lower()] <= limit]
    if hits:
        print(f"nviq: gate failed: {len(hits)} finding(s) at or above {threshold}", file=sys.stderr)
        return EXIT_GATE_FAILED
    return EXIT_OK


def _load_manifest_and_cases(
    manifest_path: Path,
    manifest_schema_path: Path,
    case_schema_path: Path,
) -> tuple[dict, list[dict]]:
    manifest = load_manifest(manifest_path)
    validate_manifest(manifest, load_schema(manifest_schema_path))
    cases = load_cases(_resolve_case_set(manifest_path, manifest["case_set"]))
    validate_cases(cases, load_schema(case_schema_path))
    return manifest, cases


def _run_audit_command(args: argparse.Namespace) -> int:
    if args.audit_command == "validate-manifest":
        manifest = load_manifest(args.manifest)
        validate_manifest(manifest, load_schema(args.manifest_schema))
        print(f"NVIQ Commercial Audit v0.1: validated audit manifest {manifest['audit_id']}")
        return 0

    if args.audit_command == "compare":
        comparison = compare_audits(_read_json(args.baseline), _read_json(args.candidate))
        args.output_dir.mkdir(parents=True, exist_ok=True)
        output = args.output_dir / "audit-comparison.json"
        write_report(comparison, output)
        print(f"NVIQ Reliability Audit comparison: {comparison['recommendation']}; report={output}")
        return 0

    manifest, cases = _load_manifest_and_cases(args.manifest, args.manifest_schema, args.case_schema)
    observations = load_observations(args.observations, {case["case_id"] for case in cases})
    observations = adapt_precomputed_observations(
        observations,
        provider="precomputed",
        model=manifest["target_name"],
        configuration={"target_version": manifest["target_version"]},
    )
    registry = load_remediations(args.remediations)
    report = run_audit(manifest, cases, observations, registry)
    paths = write_audit_artifacts(report, args.output_dir)
    print(
        f"NVIQ Reliability Audit v0.1: status={report['summary']['overall_status']}; "
        f"findings={len(report['findings'])}; report={paths['json']}"
    )
    return _gate_exit(args, report)


def _run_evidence_command(args: argparse.Namespace) -> int:
    records = load_evidence(args.evidence)
    known_case_ids = None
    if args.cases:
        cases = load_cases(args.cases)
        validate_cases(cases, load_schema(args.case_schema))
        known_case_ids = {case["case_id"] for case in cases}
    validate_evidence(
        records,
        load_schema(args.schema),
        known_case_ids,
        load_schema(args.causal_ledger_schema),
    )
    print(f"NVIQ Execution Engine v0.1: validated {len(records)} evidence records")
    return 0


def _run_ingest_command(args: argparse.Namespace) -> int:
    cases = load_cases(args.cases)
    validate_cases(cases, load_schema(args.case_schema))
    known_case_ids = {case["case_id"] for case in cases}

    if args.ingest_command == "openai-realtime":
        if args.trace_manifest:
            if args.case_id or args.events:
                raise ValueError("--trace-manifest cannot be combined with --case-id or --events")
            evidence_records = adapt_openai_realtime_trace_manifest(cases, args.trace_manifest)
        else:
            if not args.case_id or not args.events:
                raise ValueError("single-trace ingestion requires --case-id and --events")
            case = next((item for item in cases if item["case_id"] == args.case_id), None)
            if case is None:
                raise ValueError(f"unknown case_id: {args.case_id}")
            events = load_realtime_events(args.events)
            evidence_records = [adapt_openai_realtime_events(
                case,
                events,
                track=args.track or "audio_native",
                model=args.model,
                session_id=args.session_id,
                audio_ref=args.audio_ref,
                capture_origin=args.capture_origin,
            )]
        causal_schema = None
        label = "OpenAI Realtime adapter v0.1"
    elif args.ingest_command == "gemini-live":
        evidence_records = adapt_gemini_live_trace_manifest(cases, args.trace_manifest)
        causal_schema = None
        label = "Gemini Live adapter v0.1"
    elif args.ingest_command == "realtime-venus":
        evidence_records = adapt_realtime_venus_trace_manifest(cases, args.trace_manifest)
        causal_schema = load_schema(args.causal_ledger_schema)
        label = "Realtime-Venus adapter v0.1"
    else:
        raise ValueError(f"unsupported ingest command: {args.ingest_command}")

    validate_evidence(
        evidence_records,
        load_schema(args.evidence_schema),
        known_case_ids,
        causal_schema,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence_records, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"NVIQ {label}: wrote {len(evidence_records)} evidence record(s); output={args.output}")
    return 0


def _run_execute_command(args: argparse.Namespace) -> int:
    manifest, cases = _load_manifest_and_cases(args.manifest, args.manifest_schema, args.case_schema)
    evidence = load_evidence(args.evidence)
    validate_evidence(
        evidence,
        load_schema(args.evidence_schema),
        {case["case_id"] for case in cases},
        load_schema(args.causal_ledger_schema),
    )
    registry = load_remediations(args.remediations)
    result = execute_audit(manifest, cases, evidence, registry, args.output_dir)
    report = result["report"]
    print(
        f"NVIQ Execution Engine v0.1: derived={len(result['observations'])}; "
        f"status={report['summary']['overall_status']}; report={result['paths']['json']}"
    )
    return _gate_exit(args, report)


def _run_target_command(args: argparse.Namespace) -> int:
    manifest, cases = _load_manifest_and_cases(args.manifest, args.manifest_schema, args.case_schema)
    track = args.track
    if track is None:
        if len(manifest["tracks"]) != 1:
            raise ValueError("--track is required when the manifest contains multiple tracks")
        track = manifest["tracks"][0]
    if track not in manifest["tracks"]:
        raise ValueError(f"target track {track} is not enabled by the manifest")

    token = os.environ.get(args.token_env) if args.token_env else None
    capture = capture_http_target(
        cases,
        args.endpoint,
        track,
        bearer_token=token,
        timeout_s=args.timeout,
        retries=args.retries,
        retry_delay_s=args.retry_delay,
    )
    evidence_schema = load_schema(args.evidence_schema)
    ledger_schema = load_schema(args.causal_ledger_schema)
    known_case_ids = {case["case_id"] for case in cases}
    evidence: list[dict] = []
    errors = list(capture["errors"])
    for row in capture["evidence"]:
        try:
            validate_evidence([row], evidence_schema, known_case_ids, ledger_schema)
        except EvidenceValidationError as exc:
            errors.append({"case_id": row.get("case_id"), "track": track, "attempts": None, "error": f"invalid evidence: {exc}"})
            continue
        evidence.append(row)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    captured_path = args.output_dir / "captured-evidence.json"
    errors_path = args.output_dir / "capture-errors.json"
    captured_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    errors_path.write_text(json.dumps(sorted(errors, key=lambda item: str(item["case_id"])), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    registry = load_remediations(args.remediations)
    result = execute_audit(manifest, cases, evidence, registry, args.output_dir)
    print(
        f"NVIQ target execution v0.1: captured={len(evidence)}; capture_errors={len(errors)}; derived={len(result['observations'])}; "
        f"status={result['report']['summary']['overall_status']}; evidence={captured_path}; report={result['paths']['json']}"
    )
    if errors:
        print(f"nviq: warning: {len(errors)} case(s) were not captured; see {errors_path}", file=sys.stderr)
        return EXIT_CAPTURE_INCOMPLETE
    return _gate_exit(args, result["report"])


def _run_qualify_command(args: argparse.Namespace) -> int:
    if args.qualify_command != "realtime-venus":
        raise ValueError(f"unsupported qualification command: {args.qualify_command}")

    cases = load_cases(args.cases)
    validate_cases(cases, load_schema(args.case_schema))
    known_case_ids = {case["case_id"] for case in cases}

    evidence = load_evidence(args.evidence)
    validate_evidence(
        evidence,
        load_schema(args.evidence_schema),
        known_case_ids,
        load_schema(args.causal_ledger_schema),
    )

    observations = load_observations(
        args.execution_dir / "derived-observations.json",
        known_case_ids,
    )
    audit_report = _read_json(args.execution_dir / "audit-report.json")
    receipt = qualify_realtime_venus_runtime(
        cases,
        evidence,
        observations,
        audit_report,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"NVIQ Realtime-Venus runtime qualification: status={receipt['status']}; "
        f"receipt={args.output}"
    )
    return 0 if receipt["qualified"] else 2


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "audit":
        return _run_audit_command(args)
    if args.command == "evidence":
        return _run_evidence_command(args)
    if args.command == "ingest":
        return _run_ingest_command(args)
    if args.command == "execute":
        return _run_execute_command(args)
    if args.command == "target":
        return _run_target_command(args)
    if args.command == "qualify":
        return _run_qualify_command(args)

    schema = load_schema(args.schema)
    cases = load_cases(args.cases)
    validate_cases(cases, schema)
    if args.command == "validate":
        print(f"NVIQ v0.2: validated {len(cases)} cases")
        return 0

    known_case_ids = {case["case_id"] for case in cases}
    observations = load_observations(args.observations, known_case_ids)
    report = run_benchmark(cases, observations)
    write_report(report, args.output)
    hard_gate_failures = sum(track["hard_gate_failures"] for track in report["tracks"].values())
    catastrophic_failures = sum(track["catastrophic_failures"] for track in report["tracks"].values())
    print(
        f"NVIQ v0.2: scored {len(observations)} observations; "
        f"hard-gate failures={hard_gate_failures}; catastrophic failures={catastrophic_failures}; "
        f"report={args.output}"
    )
    return 0


def run(argv: list[str] | None = None) -> int:
    """Console entry point: like main(), but prints one-line errors instead of tracebacks."""
    try:
        return main(argv)
    except KeyboardInterrupt:
        print("nviq: interrupted", file=sys.stderr)
        return 130
    except (NVIQError, ValueError, RuntimeError, OSError, KeyError) as exc:
        detail = str(exc) or exc.__class__.__name__
        if isinstance(exc, KeyError):
            detail = f"missing required field {detail}"
        elif isinstance(exc, json.JSONDecodeError):
            detail = f"invalid JSON input: {detail}"
        print(f"nviq: error: {detail}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(run())
