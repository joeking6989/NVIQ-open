# NVIQ — Noct-Tech Voice Intelligence Quotient

**Open-source benchmark, execution and assurance tooling for speech-cognition reliability.**

**Official Noct-Tech website:** [noct-tech.com.au](https://noct-tech.com.au)  ·  **Latest NVIQ release:** [v0.2.0](https://github.com/joeking6989/NVIQ-open/releases/tag/v0.2.0)

NVIQ evaluates how a voice-enabled AI system preserves, interprets, and acts on conversational evidence. Its benchmark families cover confidence and uncertainty, clarification and abstention, state/speech consistency, shared context, turn-taking, tool/action outcomes, and causal evidence integrity.

**Current source distribution:** `noct-tech-nviq` v0.2.0 (Python 3.11+).

## Install

```bash
git clone https://github.com/joeking6989/NVIQ-open.git
cd NVIQ-open
python -m pip install -e '.[dev]'
```

The default install requires `jsonschema`; provider-specific live integration dependencies are optional (the `live` extra includes `google-genai`). Live provider calls require your own authorised account, credentials and compatible service configuration.

## Verify the software

```bash
python -m pytest -q
nviq validate --cases cases/v0.2/starter.json
nviq score \
  --cases cases/v0.2/starter.json \
  --observations examples/observations/starter-observations.json \
  --output nviq-starter-report.json
```

The included starter suite is an example input and scorer check, **not a published independent measurement of an AI provider**.

## Evaluate supplied evidence

NVIQ's execution path validates a provider-neutral Evidence Bundle, derives observations, scores them and generates an audit report.

```bash
nviq evidence validate \
  --evidence examples/evidence/p0-executable.json \
  --cases cases/v0.2/executable-p0.json

nviq execute \
  --manifest examples/audit/executable-p0-manifest.json \
  --evidence examples/evidence/p0-executable.json \
  --output-dir out/execution-p0
```

The execution output includes derived observations, an evidence summary, JSON and HTML audit reports and a regression snapshot. Runtime captures are distinguished from adapter-contract fixtures through explicit provenance fields.

## Architecture

```text
Provider / target events
        |
        v
Provider adapter / Evidence Bundle
        |
        v
Schema validation + evidence boundaries
        |
        v
Deterministic observation evaluators
        |
        v
NVIQ benchmark scorer and hard-gate findings
        |
        v
JSON / HTML reliability audit and regression comparison
```

The scorer is the single scoring authority. Adapters preserve evidence and do not generate substitute performance scores. Unsupported or uncaptured facts must not be invented to force a result.

## Integrations and technical documentation

- [Benchmark architecture](docs/NVIQ-v0.2-architecture.md)
- [Execution engine and target protocol](docs/execution-engine.md)
- [OpenAI Realtime adapter](docs/openai-realtime-adapter.md)
- [Gemini Live adapter](docs/gemini-live-adapter.md)
- [Realtime-Venus audio adapter](docs/realtime-venus-audio-adapter.md)
- [Causal speech cognition](docs/causal-speech-cognition-v0.1.md)
- [Source provenance and exclusions](docs/OPEN_SOURCE_PROVENANCE.md)

Provider adapter fixtures are contract tests, not evidence of provider performance. A named-provider benchmarking claim requires authentic captured runtime data, known versions/configuration and a reproducible methodology.

## Contribute

Contributions are welcome for new benchmark cases, correctness fixes, provider adapter compatibility, tests, docs and improvements to reproducibility.

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Pull requests should include tests and explain evidence provenance. Do not upload private customer recordings, credentials, confidential prompts or unpublished reports.

## Open source and Noct-Tech services

This repository publishes the local benchmark engine and related tooling. Noct-Tech may separately offer hosted services, managed integrations and independent Assurance audits. Those services are not part of the open-source repository.

## Licence

Apache License 2.0 — [LICENSE](LICENSE).

**Developed by [Noct-Tech](https://noct-tech.com.au)**
