---
name: smrt-codeparrot-github-code-clean-parquet-loader
description: "Use when load_dataset(\"codeparrot/github-code-clean\", config_name, split=\"train\", streaming=True) (or any config_name variant) fails with \"RuntimeError: Dataset scripts are no longer supported, but found github-code-clean.py\" in the SMaRT repo (or any repo using this HF dataset) — the fix is loading the same data via the parquet builder against an explicit hf://datasets/name/data/train-*.parquet glob instead of the dataset-name+config_name form."
---

## Symptom

Any of these fail identically, regardless of `config_name` ("all-all", "Python-all", etc.):

```python
load_dataset("codeparrot/github-code-clean", "all-all", split="train", streaming=True)
load_dataset("codeparrot/github-code-clean", "Python-all", split="train", streaming=True)
load_dataset("codeparrot/github-code-clean", data_files="data/train-00000-of-00880.parquet", split="train", streaming=True)
```

with:

```
RuntimeError: Dataset scripts are no longer supported, but found github-code-clean.py
```

This is a `datasets` library version incompatibility: the repo ships a `.py` loading script (`github-code-clean.py`) alongside real parquet shards (`data/train-NNNNN-of-00880.parquet`), and modern `datasets` refuses to execute the script — but any `load_dataset(dataset_name, ...)` call still resolves through the script path first regardless of `config_name`/`data_files` overrides.

## Fix

Bypass the script entirely by loading through the generic `parquet` builder with an explicit `hf://` glob covering all shards:

```python
from datasets import load_dataset

ds = load_dataset(
    "parquet",
    data_files="hf://datasets/codeparrot/github-code-clean/data/train-*.parquet",
    split="train",
    streaming=True,
)
```

Verified working (in `~/Documents/Development/smart`, `datasets` as pinned in `.venv`): pulled a real row and confirmed the schema is `{"code", "repo_name", "path", "language", "size", "license"}` — filter by `example["language"] == "Python"` (or any other `CODE_LANGUAGES` set) exactly as before; no other pipeline logic needs to change.

`config_name` becomes irrelevant to loading (every language lives in the same parquet shards) — keep it as an accepted-but-unused parameter only if backward-compatible function signatures matter to callers.

## Gotcha: benign fatal-shutdown noise

A one-off standalone `python -c "..."` script that streams this dataset and exits immediately after `next(iter(ds))` may print:

```
Fatal Python error: PyGILState_Release: thread state ... must be current when releasing
```

This is an interpreter-shutdown race in pyarrow/pandas extension module teardown, **not** a data-loading failure — it happens after the real work (row printed, assertions passed) already completed. Don't mistake it for the fix not working; check the actual printed output/exit evidence above the traceback, not just the presence of a fatal-error block.

## Where this was applied

- `smrt/data/code.py::load_code_stream` — pre-existing (never previously smoke-tested against live HF per this repo's RESULTS.md).
- `smrt/data/code_repair.py::load_code_repair_stream` — new file, same fix applied at creation time after discovering the failure during an SFT end-to-end smoke run.

Both now load via the `parquet`+`hf://` glob form described above instead of the direct `dataset_name`/`config_name` form.
