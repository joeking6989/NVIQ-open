# NVIQ Hugging Face Space

The source of truth is this GitHub repository. The Hugging Face Space
`Noct-Tech/NVIQ` is a deployment target, not a second independent source tree.

## Contents and responsibilities

- `src/nviq/space_service.py`: validates uploaded files and invokes the existing
  NVIQ scorer and evidence-driven audit engine. It never calls a model provider.
- `space/app.py`: minimal Gradio UI. No benchmark calculations in this layer.
- `space/README.md`: actual Space YAML metadata, including Gradio SDK.
- `.github/workflows/publish-huggingface.yml`: tests and stages the package
  plus UI, then publishes to the existing Space.

## Activate deployment

1. In GitHub, open the repository's Settings → Secrets and variables → Actions.
2. Add the repository secret `HF_TOKEN`, using a fine-grained Hugging Face token
   with write permission **only** to `Noct-Tech/NVIQ`. Never commit a token.
3. Merge the NVIQ Space pull request after the repository CI checks pass.
4. Watch the `Publish NVIQ Space` action. The action runs the existing tests
   before synchronising the Space from GitHub.
5. Verify the Space's application tab and test with privately reviewed
   non-sensitive evidence. The included repository reference files are
   engineering fixtures, not provider benchmark results.

The sync action mirrors the staged directory: files previously created directly
in the Space (including the static placeholder HTML) will be removed when the
first successful sync completes. This is deliberate: GitHub is the authoritative
deployment source.

## Local validation

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
python -m pip install gradio==6.31.0
python space/app.py
```

The UI accepts only uploaded JSON files, with a 5 MiB per-file limit. Do not
upload sensitive transcripts, credentials or other private data to a public
Space. Report output files are generated in server temporary storage and may
persist for a period; this is not an approved storage destination for
confidential material.

This initial interface provides deterministic scoring and analysis of uploaded
observations/evidence. Live provider API execution is outside its scope. Add
a separate authenticated, rate-limited capture service before enabling live
customer or provider tests.
