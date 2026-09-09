---
name: smrt-agent-vocab-extension
description: "Use when extending the SMaRT codebase (/home/wils/Documents/Development/smart) with a new tokenizer/vocab, new model-size configs, new data pipelines, or new eval scripts that must slot into smrt/config.py, smrt/train.py, smrt/evaluate.py without breaking the existing 256-vocab (tiny_cpu) and 50257-vocab (base_50m) paths. Also covers scaling ModelConfig dimension ratios to a target non-embedding param count, and the config_from_dict sft: None-in-saved-checkpoint-dict gotcha."
---

## Context
SMaRT (`/home/wils/Documents/Development/smart`) is a small text-LM codebase with sliding-window attention + Titans-style neural memory. `smrt/config.py::Config` has `model`/`train`/`curriculum` (+ optionally `sft`) sections built via explicit `_require`/`_check_no_extra` dataclass builders — no generic dataclass-from-dict library, so bad/missing keys name the exact offending field. `smrt/train.py::_get_batch`/`_tokenizer_for` branch on `cfg.model.vocab_size` (`256` = byte tokenizer/tiny_cpu smoke path, `50257` = gpt2/base_50m real path). `smrt/data/needle.py` is the canonical pattern for synthetic recall-example generators (`NeedleExample` dataclass, collision-check-and-resample loop, `generate_*_batch` wrapping `validate_batch`).

## Adding a new vocab size / tokenizer
1. Build a `<Name>Tokenizer` class with the same two-method `encode(str)->list[int]` / `decode(list[int])->str` interface as `ByteTokenizer`/`gpt2_tokenizer()`. If using `tiktoken` with custom special tokens, extend a base encoding via `tiktoken.Encoding(name=..., pat_str=base._pat_str, mergeable_ranks=base._mergeable_ranks, special_tokens={**base._special_tokens, **your_specials})`, and pass `allowed_special="all"` in `encode()` so text containing literal special-token substrings round-trips instead of raising.
2. Cache a single module-level instance via a lazy `<name>_tokenizer()` factory (mirrors `needle.py`'s `_FILLER_TEXT` cache pattern) — never rebuild the encoding on every call.
3. Wire into `smrt/train.py`: add a new `if cfg.model.vocab_size == YOUR_VOCAB_SIZE: return ...` branch to **both** `_tokenizer_for` and `_get_batch`, placed as an early-return before the existing `256`/else logic — never touch the existing branches' bodies (regression risk to already-passing `tests/`). Prefer a `_get_<name>_batch` helper function kept separate from the two-arm `_get_batch` to keep it simple.
4. Add a load-bearing assertion right after tokenizer construction in `train_loop`: `if cfg.model.vocab_size == YOUR_VOCAB_SIZE: assert tokenizer.n_vocab == YOUR_VOCAB_SIZE` — catches a future base-encoding vocab-size bump silently corrupting embeddings.

## Scaling ModelConfig to a target non-embedding param count
`base_50m.yaml`'s dimension ratios at `d_model=512`: `window_size=2*d_model`, `chunk_size=d_model/2`, `memory.key_dim=memory.value_dim=d_model/8`, `memory.hidden_dim=d_model/2`, `num_persistent_tokens=d_model/32`, `num_heads=d_model/head_dim` with `head_dim=64` fixed. Apply the same ratios at your target `d_model`, guess `num_layers` analytically (params scale roughly as `1.057 × 12 × d² × L`), then measure directly:
```python
from smrt.config import load_config
from smrt.model.backbone import SMaRT
c = load_config('configs/your.yaml'); m = SMaRT(c.model)
n = sum(p.numel() for name, p in m.named_parameters() if 'embed' not in name and 'lm_head' not in name)
```
(Note: `lm_head` is weight-tied to `embed` in `SMaRT.__init__`, so `'lm_head' not in name` never actually excludes anything extra in `named_parameters()` — the tied weight only appears once, under the `embed` name — but keep the filter for defensiveness/clarity anyway.) Adjust `num_layers` (keep `d_model` fixed) until `n` is within ±5% of target. Measuring 8B-scale models takes ~100s on CPU — background it.

## Adding a new synthetic data generator (needle-style)
Mirror `needle.py` exactly: a frozen `@dataclass` example type (`token_ids`, `needle_span`, `question_span`, `answer_span`), a `generate_<name>_example(rng, context_len, filler_tokens, depth_bin, num_depth_bins, tokenizer)` with a `for _attempt in range(10): ... if value_str in filler_text: continue ... raise RuntimeError(...)` collision-check-and-resample loop, and a `generate_<name>_batch(...)` that stacks examples, pads/truncates to `train_cfg.seq_len`, and calls `smrt.data.batch.validate_batch(input_ids, train_cfg, needle_spans=spans)`. Verify offline (no network) by asserting `answer_span[1] > answer_span[0]` on a small example — this is the exact bug class (`needle.py` had a truncation bug that silently zeroed the answer span) worth explicitly re-checking on every new generator.

## Extending Config with a new optional section (e.g. SFTConfig)
- Add the frozen dataclass, an `allowed` field-set constant, and a `_build_<section>(d)` builder mirroring `_build_train` exactly.
- Add the field to `Config` as `<section>: <Type> | None = None` (default `None`, so every existing YAML with no `<section>:` key still parses unchanged — verify with the pre-existing configs after any change).
- Add `<section>` to `config_from_dict`'s root `allowed` set.
- **Gotcha**: `dataclasses.asdict(cfg)` on a `Config` with `sft=None` produces a dict containing the literal key `"sft": None` (not an absent key). If that dict later round-trips through `config_from_dict` (e.g. loading a saved checkpoint's `ckpt["config"]`), a naive `_build_sft(d["sft"]) if "sft" in d else None` check crashes with `AttributeError: 'NoneType' object has no attribute 'keys'` because `"sft" in d` is `True` even though `d["sft"]` is `None`. Fix: `_build_sft(d["sft"]) if d.get("sft") is not None else None`. This exact bug will resurface for any new optional `Config` section — check for it immediately when checkpoint-resume tests fail after adding one.

## Verification pattern for CPU-only smoke tests
No GPU on this machine — every claim in `RESULTS.md` must be either a real HF-network-verified pipeline (network access does work; verified via `datasets.load_dataset(..., streaming=True)` calls succeeding) or an explicitly-labeled tiny/CPU wiring-correctness smoke test, never a fabricated training curve. For eval-harness smoke tests (e.g. HumanEval pass@1, tool-call correctness), train a tiny throwaway checkpoint first with a matching vocab size (a full-size `agent_2b.yaml`-shaped config won't have a matching checkpoint at CPU scale — build a `configs/*_tiny_cpu.yaml` with the new vocab_size but `d_model=32, num_layers=1` and a couple of `max_steps` to get a real checkpoint file offline, then point the eval script at that). Running the full 164-task HumanEval loop at `max_new_tokens=512` on CPU exceeds a reasonable time budget — reduce `max_new_tokens` and/or slice the dataset to 2-3 tasks (monkeypatch `datasets.load_dataset` to return a small in-memory list) to prove the decode→subprocess-scoring pipeline end-to-end instead.
