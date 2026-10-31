---
title: NVIQ Open
emoji: 🦉
colorFrom: blue
colorTo: gray
sdk: gradio
sdk_version: 6.31.0
app_file: app.py
short_description: "AI voice benchmarking toolkit"
pinned: false
---

# NVIQ Open — Noct-Tech Voice Intelligence Quotient

This application uses the **real NVIQ v0.2.0 Python scoring and audit engine** from
[Noct-Tech's open-source repository](https://github.com/joeking6989/NVIQ-open).

Upload NVIQ test cases and either precomputed observations or provider-neutral
Evidence Bundle records plus an audit manifest. The application validates your
inputs, executes the existing deterministic evaluation pipeline and generates
downloadable reports.

**Important:** This interface does not make live API calls to voice providers,
record audio, or claim to independently measure named providers. Reference files
in the source repository are engineering fixtures, not published provider tests.

**Privacy:** Do not upload credentials, confidential customer transcripts,
private audio, regulated personal data or unpublished commercial evidence to
this public Space.

[Official Noct-Tech website](https://noct-tech.com.au) ·
[GitHub source](https://github.com/joeking6989/NVIQ-open)
