---
name: smrt-agent-tool-code-recall-extension
description: "Use when extending the SMaRT codebase (/home/wils/Documents/Development/smart) with tool-calling/code/agentic training on top of the existing 50M-param sliding-window+Titans-memory base model — new tokenizer (tiktoken o200k_base + special tokens), 2B/4B/8B model configs, SFTConfig schema addition, glaive-function-calling-v2 / codeparrot / tool-needle data pipelines, agent-vocab batch dispatch in train.py, SFT loss-masking, and tool-call/code eval harnesses. Also covers the config.py sft:None-vs-missing dataclasses.asdict roundtrip gotcha and testing conventions for this repo."
---

## Context

This applies to the SMaRT repo at `/home/wils/Documents/Development/smart` — a
small decoder-only LM (sliding-window attention + Titans-style neural memory,
see `DESIGN.md`) with a config-driven `smrt/train.py`/`smrt/config.py`
pattern. When extending it into an agentic (tool-calling/code) model family,
these are the load-bearing gotchas and conventions actually hit while doing
so.

## Config schema gotcha: `dataclasses.asdict` + optional dataclass field

`smrt/train.py::train_loop`'s checkpoint-resume path does
`config_from_dict(dataclasses.asdict(cfg))` to round-trip a saved config.
If you add an optional nested dataclass field (e.g. `Config.sft:
SFTConfig | None = None`), `dataclasses.asdict` serializes the `None` as a
literal `"sft": None` key in the dict — NOT an absent key. So
`config_from_dict` must check `d.get("sft") is not None`, never just
`"sft" in d`:

```python
sft=_build_sft(d["sft"]) if d.get("sft") is not None else None,  # correct
sft=_build_sft(d["sft"]) if "sft" in d else None,                # WRONG — crashes on resume
```

This broke `tests/test_checkpoint_resume.py` immediately after adding
`SFTConfig` and was only caught by re-running the *existing* test suite —
always do this after any config schema change, not just for the new feature.

## Reuse patterns (read before writing new modules)

- `smrt/data/needle.py` — the canonical needle-in-haystack generator
  pattern: `NeedleExample` dataclass with `token_ids`/`needle_span`/
  `question_span`/`answer_span`, a 10-attempt collision-resample loop
  (resample the secret value if its digit string leaks into filler text,
  `RuntimeError` on the 11th failure), and `generate_*_batch` wrapping
  `generate_*_example` + `validate_batch`. Any new needle-style recall task
  (e.g. tool-call recall) should copy this shape exactly, including the
  `_sample_filler_tokens` padding helper reused from this module.
- `smrt/data/pretrain.py::load_pretrain_stream` — the canonical HF
  streaming-dataset-to-fixed-seq_len-chunks generator (buffer + slice +
  yield-until-budget). New streaming sources (code corpora, SFT data) copy
  this loop shape.
- `smrt/evaluate.py::_decode_answer` — the exact no-`torch.no_grad()`
  generation loop. `NeuralMemory.update()` always builds a differentiable
  graph via `torch.autograd.grad(..., create_graph=True)` even at
  inference, so wrapping generation in `torch.no_grad()` breaks it. Any new
  eval script's decode loop must copy this (no no_grad, detach only the
  final argmax read-out).
- `smrt/config.py::_build_train`/`TrainConfig` — the exact
  `_require`/`_check_no_extra` dataclass-builder pattern every new config
  section (e.g. `SFTConfig`) must mirror field-for-field, including naming
  the offending key in `ValueError` messages.

## Model sizing at new scale

To size a new `d_model`/`num_layers` config to a target non-embedding param
count, reuse the exact scaling ratios already used in the smallest existing
config (e.g. `window_size=2*d_model`, `chunk_size=d_model/2`,
`key_dim=value_dim=d_model/8`, `hidden_dim=d_model/2`,
`num_persistent_tokens=d_model/32`, fixed `head_dim`). Measure via:

```python
from smrt.config import load_config
from smrt.model.backbone import SMaRT
c = load_config(path); m = SMaRT(c.model)
n = sum(p.numel() for name, p in m.named_parameters() if 'embed' not in name and 'lm_head' not in name)
```

(`lm_head` is weight-tied to `embed` so it never appears as a separate
`named_parameters()` entry anyway — the filter is defensive/future-proofing,
not currently load-bearing.) Adjust `num_layers` only, keep `d_model` fixed,
iterate until within ±5% of target. Don't assume an analytically-derived
`num_layers` guess is correct without running this — but also don't assume
it's wrong; it can land within tolerance on the first try.

## Testing conventions for this repo

Every test file needs a one-line comment directly above each test stating
what bug a failure would indicate (see existing `tests/test_needle_data.py`,
`tests/test_device.py`). Prefer real inputs over mocks (e.g. actually
tokenize with `agent_tokenizer()`, actually run `subprocess` for code-eval
scoring tests — never `exec()` untrusted model-generated code in-process,
even in a test). A malformed-input test (e.g. bad JSON from a model's
generated text) is a good way to surface real un-guarded exception paths —
writing `test_extract_model_tool_call_returns_none_for_malformed_json`
caught a genuine unguarded `json.JSONDecodeError` propagating out of an
eval helper that should have degraded to `None` instead of crashing the
whole eval run on the first bad sample from an undertrained model.

## Special-token tokenizer extension via tiktoken

To add custom special tokens on top of a tiktoken base encoding (e.g.
`o200k_base`), build a new `tiktoken.Encoding` reusing the base's private
`_pat_str`/`_mergeable_ranks`/`_special_tokens`, merging in new
`{token: base.n_vocab + i}` entries. Always pass `allowed_special="all"` to
`.encode()` so text containing literal special-token substrings (e.g. from
scraped/HF source data) round-trips through the special ids instead of
raising tiktoken's default "disallowed special token" error.
