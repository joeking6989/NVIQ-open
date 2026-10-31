# Open-source source provenance — 31 October 2026

## Upstream project

The NVIQ open-source engine was transferred from Noct-Tech's NVIQ codebase at the following fixed Git revision:

- Source: `joeking6989/NVIQ` (private)
- Exact source commit: `a47894a8b88c0cdd50b318c13473d4eb93a29908`
- Public destination: `joeking6989/NVIQ-open`
- Package name and version at transfer: `noct-tech-nviq`, `0.2.0`

## Transfer scope

136 source files were transferred: `src/nviq/`, `tests/`, `cases/v0.2/`, selected `examples/`, technical files directly under `docs/`, and `pyproject.toml`.

The source files were transferred without deliberately changing their execution logic. Their public presence alone does not imply a passing test run. Actual CI logs are the runtime evidence.

## Intentionally excluded

- Commercial launch plans, customer intake and other `docs/commercial/` materials.
- Development planning notes in `docs/superpowers/`.
- Private repository CI workflows and unrelated GitLab/Bitbucket configuration.
- Original private README and change history; public README describes this distribution.
- Recorded runtime evidence/receipts under `examples/runtime/`, pending a separate disclosure and provenance review.

The CLI, provider adapters and examples must not represent contract fixtures as live provider performance measurements.

## Security review scope

Each copied file was examined using automated credential-pattern checks for common API key formats, private-key headers, and credential-bearing URLs before transfer. A clean pattern scan does not prove the absence of all sensitive information; subsequent reviews and GitHub security alerts remain relevant.

## Licence and attribution

The distribution is made available by Noct-Tech under Apache License 2.0. Third-party dependencies retain their own licences. The separate Noct-Tech hosted product and commercial Assurance services are not included in this repository.
