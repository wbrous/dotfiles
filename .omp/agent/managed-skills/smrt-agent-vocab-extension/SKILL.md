---
name: smrt-agent-vocab-extension
description: "Use when extending the SMaRT codebase (/home/wils/Documents/Development/smart) with a new tokenizer/vocab, new model-size configs, new data pipelines, or new eval scripts that must slot into smrt/config.py, smrt/train.py, smrt/evaluate.py without breaking the existing 256-vocab (tiny_cpu) and 50257-vocab (base_50m) paths. Also covers scaling ModelConfig dimension ratios to a target non-embedding param count, the config_from_dict sft: None-in-saved-checkpoint-dict gotcha, and the pretraining-loop overhaul: pick_batch_schedule grad-accumulation wiring, the persistent-per-run streams dict (fixes the \"fresh HF streaming iterator per _get_batch call, never advances\" bug), and the config-driven TrainConfig.batch_source_schedule field (validated against {\"needle\",\"tool_needle\",\"code\",\"text\"}, falls back to the AGENT_BATCH_SOURCE_SCHEDULE module constant when omitted) used to bias smaller agent models toward code (agent_1b 65% code, agent_2b 55%, agent_4b 40%, agent_8b 25%)."
---

## Param-count sizing for new agent_*.yaml configs

To hit a non-embedding param-count target, scale `num_layers` primarily (keep
`num_heads`/`head_dim`/`num_kv_heads` ratios clean — e.g. `head_dim: 64`
fixed, `num_kv_heads = num_heads / 4`). Verify by actually instantiating the
model, never trust the estimate alone:

```python
from smrt.config import load_config
from smrt.model.backbone import SMaRT
cfg = load_config('configs/agent_1b.yaml')
m = SMaRT(cfg.model)
n = sum(p.numel() for name, p in m.named_parameters() if 'embed' not in name and 'lm_head' not in name)
print(f'{n:,}')
```

Confirmed working point: `d_model=1536, num_layers=28, num_heads=24,
num_kv_heads=6, mlp_hidden_dim=4088` (all attention/memory sub-fields
otherwise copied verbatim from `agent_2b.yaml`) → 754,358,356 non-embedding
params, inside a 500M–1B target range.

## Pretraining loop: grad accumulation + persistent streams (train.py)

`smrt/device.py::pick_batch_schedule(total_memory_bytes, base_micro_batch,
base_grad_accum)` returns `(micro_batch, grad_accum)` for the detected
memory tier. It must be called once at the top of `train_loop` (right after
`resolve_device`) and its result threaded through: an inner
`for _ in range(grad_accum):` loop does `grad_accum` forward/backward passes
(each loss scaled by `1/grad_accum`), then ONE `clip_grad_norm_` +
`optimizer.step()` pair. `checkpoint_every`/LR-schedule/diagnostics-file
writes still happen exactly once per OUTER step — never move them inside
the accumulation loop.

Batch-source streams (`load_pretrain_stream`, `load_nemotron_cc_stream`,
`load_starcoder_stream`, formerly `load_code_stream`) are `streaming=True`
HF dataset generators. **Never construct one inside `_get_batch`/
`_get_agent_batch` — those are called every step.** A stream created there
restarts from the front of the corpus every call and never advances. Build
a `streams: dict` ONCE before the step loop in `train_loop`
(`streams["code"]`, `streams["text"]`) and pass it down; `_get_batch`/
`_get_agent_batch` only ever do `next(streams["code"])` etc.

`TrainConfig.batch_source_schedule: list[str] | None = None` lets each
config declare its own needle/tool_needle/code/text mixture ratio instead
of the hardcoded `AGENT_BATCH_SOURCE_SCHEDULE` module constant in
`train.py`. Validated in `smrt/config.py::_build_batch_source_schedule`
(non-empty, every entry in `{"needle","tool_needle","code","text"}`).
Omitting the key in YAML → `None` → falls back to the module constant
(used by `agent_tiny_cpu.yaml` and non-agent-vocab configs, which never
read it at all).

Real Nemotron datasets with actual streamable text content are almost all
HF-gated (`manual` review, company email required) or gated:false but
metadata-only (e.g. `nvidia/Nemotron-Pretraining-Code-v3` has no file
content, only `commit_id`/`rel_path`/`language`). For a code corpus, prefer
`bigcode/starcoderdata` (gated:`auto`, one-click accept, confirmed `content`
field, load via the `parquet` + explicit `hf://datasets/.../<lang>/*.parquet`
glob technique — NOT `load_dataset(name, config_name)` directly, which hits
"Dataset scripts are no longer supported" for some of these repos).

## sft field gotcha (unchanged)

`Config.sft: SFTConfig | None = None` — a checkpoint saved via
`dataclasses.asdict(cfg)` before `sft` existed round-trips as `sft: None`,
which `config_from_dict` must treat as "no SFT config," not a missing key.
