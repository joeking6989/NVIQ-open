"""Public Hugging Face UI backed by the actual NVIQ v0.2 engine."""
import tempfile
from pathlib import Path

import gradio as gr

from nviq.errors import NVIQError
from nviq.space_service import audit_files, score_files


def _needed(*files):
    if any(not path for path in files):
        raise gr.Error("Upload every required JSON file before running NVIQ.")


def _score(case_file, observations_file):
    _needed(case_file, observations_file)
    output_dir = Path(tempfile.mkdtemp(prefix="nviq-score-"))
    try:
        result = score_files(
            Path(case_file), Path(observations_file), output_dir
        )
    except (NVIQError, OSError, ValueError, KeyError, TypeError) as exc:
        raise gr.Error(f"NVIQ rejected the supplied data: {exc}") from exc
    return result["summary"], result["report"], str(result["paths"]["json"])


def _audit(case_file, evidence_file, manifest_file):
    _needed(case_file, evidence_file, manifest_file)
    output_dir = Path(tempfile.mkdtemp(prefix="nviq-audit-"))
    try:
        result = audit_files(
            Path(case_file),
            Path(evidence_file),
            Path(manifest_file),
            output_dir,
        )
    except (NVIQError, OSError, ValueError, KeyError, TypeError) as exc:
        raise gr.Error(f"NVIQ rejected the supplied data: {exc}") from exc
    paths = result["paths"]
    downloads = [
        str(paths[key])
        for key in ("json", "html", "snapshot", "derived_observations", "evidence_summary")
    ]
    return result["summary"], downloads


with gr.Blocks(title="NVIQ Open | Noct-Tech") as demo:
    gr.Markdown(
        """
# NVIQ Open
### Noct-Tech · Voice Intelligence Quotient

**Real benchmark scoring and evidence-driven audits**, powered by the
[NVIQ open-source engine](https://github.com/joeking6989/NVIQ-open).

Upload your own valid NVIQ JSON input files. NVIQ does not create provider
measurements or invent observations. **This Space does not call live providers.**

**Public-service privacy:** Never upload credentials, private customer
recordings or transcripts, regulated personal information or confidential data.
        """
    )
    with gr.Tab("Benchmark observations"):
        gr.Markdown(
            "Score existing observations using NVIQ v0.2. "
            "You need a test-case JSON array and an observations JSON array."
        )
        with gr.Row():
            score_cases = gr.File(
                label="NVIQ test cases (.json)", file_types=[".json"], type="filepath"
            )
            score_observations = gr.File(
                label="Recorded observations (.json)",
                file_types=[".json"],
                type="filepath",
            )
        score_button = gr.Button("Run NVIQ benchmark", variant="primary")
        score_summary = gr.JSON(label="Benchmark summary")
        score_report = gr.JSON(label="Full benchmark result")
        score_download = gr.File(label="Download benchmark report (.json)")
        score_button.click(
            _score,
            inputs=[score_cases, score_observations],
            outputs=[score_summary, score_report, score_download],
        )

    with gr.Tab("Evidence-driven audit"):
        gr.Markdown(
            "Run the NVIQ v0.1 execution/audit path against supplied "
            "provider-neutral evidence. Upload the matching cases, evidence and "
            "manifest. The uploaded cases are used directly; the manifest's "
            "case_set field is never treated as a server-side file path."
        )
        audit_cases = gr.File(
            label="NVIQ test cases (.json)", file_types=[".json"], type="filepath"
        )
        audit_evidence = gr.File(
            label="Evidence Bundle (.json)", file_types=[".json"], type="filepath"
        )
        audit_manifest = gr.File(
            label="Audit manifest (.json)", file_types=[".json"], type="filepath"
        )
        audit_button = gr.Button("Execute NVIQ audit", variant="primary")
        audit_summary = gr.JSON(label="Audit summary and coverage")
        audit_downloads = gr.File(
            label="Download audit artifacts (JSON / HTML)", file_count="multiple"
        )
        audit_button.click(
            _audit,
            inputs=[audit_cases, audit_evidence, audit_manifest],
            outputs=[audit_summary, audit_downloads],
        )

    gr.Markdown(
        "[NVIQ source and input formats](https://github.com/joeking6989/NVIQ-open) "
        "· [Noct-Tech](https://noct-tech.com.au)"
    )


if __name__ == "__main__":
    demo.queue(default_concurrency_limit=2, max_size=8).launch(
        max_file_size="5mb",
        show_error=False,
    )
