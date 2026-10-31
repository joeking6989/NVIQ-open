# NVIQ Open Source

**NVIQ — Noct-Tech Voice Intelligence Quotient**

NVIQ is Noct-Tech's research and engineering project for evaluating speech-cognition reliability. It is designed to assess what an AI voice system preserves, understands and uses beyond its transcript, including uncertainty, conversational state, turn taking, evidence provenance and action outcomes.

**Repository status (31 October 2026):** public collaboration foundation in preparation. This repository does not yet contain the executable NVIQ benchmark engine. No runtime benchmark or provider performance claim is made by this repository's current contents.

## Project direction

The intended open-source distribution will support:

- Versioned benchmark cases and machine-readable evidence contracts.
- Explicit distinction between authentic runtime evidence and adapter-contract fixtures.
- Deterministic scoring and meaningful failure findings.
- Provider-neutral evidence ingestion and documented provider adapters.
- Reproducible local CLI usage, tests and example reports.
- Community improvements to benchmark coverage, adapter support and engineering quality.

Features will be documented as available only after source, tests and release checks are published.

## Getting involved

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request, and [SECURITY.md](SECURITY.md) for vulnerability reporting. Issues should contain reproducible, sanitised information; never publish provider credentials, customer conversations or personal data.

## Roadmap for the first usable release

1. Review the existing NVIQ source, its dependencies, configuration and example datasets for public-release suitability.
2. Select and import the releasable engine, tests, schemas and benchmark cases with attribution.
3. Document installation, supported Python versions and reproducible CLI commands.
4. Enable and pass continuous integration checks on the public code.
5. Publish the first versioned release with an accurate feature list and limitations.

The original NVIQ implementation remains under its existing repository until the code transfer and review are completed.

## Open source and commercial services

The community code and its contributions can be used under [Apache License 2.0](LICENSE). Noct-Tech may separately offer hosted evaluation, managed integrations and independent Assurance audits as commercial services. The licence applies to material published in this repository, not unpublished private services or code.

## Maintainer

Noct-Tech — https://noct-tech.com.au

## Licence

Apache License 2.0. See [LICENSE](LICENSE).
