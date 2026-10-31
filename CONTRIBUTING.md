# Contributing to NVIQ

Thank you for helping improve NVIQ, Noct-Tech's speech-cognition evaluation research and tooling.

## Before contributing

- Read the project README and the applicable benchmark and evidence contracts.
- Open an issue describing the problem, expected behaviour, and proposed solution for substantial changes.
- Keep changes focused. Do not mix new benchmark rules, adapter changes, and unrelated refactoring in one pull request.
- Never add API keys, credentials, private customer records, protected prompts, private recordings, or unlicensed third-party data.
- Do not present fixture-based adapter contract tests as measured provider/model performance.
- Preserve the separation between raw evidence, NVIQ-derived observations, and scores; scoring changes require clear test cases and rationale.

## Development workflow

1. Fork this repository and create a topic branch.
2. Install the dependencies defined by the published project's `pyproject.toml` when the source distribution is available.
3. Add or update automated tests when changing behaviour.
4. Run the project checks documented in the README.
5. Open a pull request explaining what changed, why, and what you tested.
6. Link reproducible input cases and redact sensitive information before sharing logs.

Maintainers may request clarification or changes before merging. Contribution does not imply a paid engagement.

## Reports and benchmark claims

Give the exact model/API identifier, benchmark version, run date, environment, capture origin and known evidence gaps. Distinguish authentic runtime traces from synthetic or adapter-contract fixtures. Do not publish unreviewed customer or provider material.

## Licence

By submitting contributions, you agree that contributions are licensed under the repository's Apache License 2.0. Only submit material you have the right to license.
