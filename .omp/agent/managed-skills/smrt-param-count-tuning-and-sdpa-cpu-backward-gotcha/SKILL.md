---
name: smrt-param-count-tuning-and-sdpa-cpu-backward-gotcha
description: "Use when adding/removing parameters in the SMaRT model (/home/wils/Documents/Development/smart) — e.g. new norm layers, gated MLPs, GQA, RoPE — and needing to re-tune configs/*.yaml num_layers to hit a target param count. Also covers the discovery that torch.nn.attention.sdpa_kernel([SDPBackend.FLASH_ATTENTION, ...]) can pass an isolated forward+backward smoke test but still raise \"derivative for aten::_scaled_dot_product_flash_attention_for_cpu_backward is not implemented\" once exercised through the real train_loop (different tensor shapes/grad-accum path) on this machine's CPU-only PyTorch build — requiring fallback to sdpa_kernel(SDPBackend.MATH) only."
---

## Context
SMaRT (/home/wils/Documents/Development/smart) has several `configs/*.yaml` files (`base_50m.yaml`, `agent_2b.yaml`, `agent_4b.yaml`, `agent_8b.yaml`) each targeting a specific non-embedding param count. Any architecture change that alters per-layer param count (adding RMSNorm, switching to gated SwiGLU MLP, GQA, bias removal, etc.) shifts the actual count away from the target and requires re-tuning `num_layers`.

## Efficient param-count re-tuning procedure
Don't guess-and-check one `num_layers` value at a time. Instead, solve for the exact value:

1. Measure current count `n0` at the config's current `num_layers = L0`:
   ```python
   from smrt.config import load_config
   from smrt.model.backbone import SMaRT
   c = load_config('configs/<name>.yaml'); m = SMaRT(c.model)
   n0 = sum(p.numel() for name, p in m.named_parameters() if 'embed' not in name and 'lm_head' not in name)
   ```
2. Measure again with `num_layers = L0 + 1` (via `dataclasses.replace(c.model, num_layers=L0+1)`) to get `n1`.
3. `per_layer = n1 - n0` (exact, since per-layer cost is constant); `fixed = n0 - per_layer * L0` (the embedding-independent, layer-independent overhead — usually tiny, e.g. a few thousand params from top-level buffers).
4. `needed_layers = round((target - fixed) / per_layer)`.
5. Set `num_layers = needed_layers` in the YAML, re-measure to confirm within tolerance (this repo uses ±5%).

This is O(2) model constructions per config instead of an iterative binary search, and is exact because per-layer param count is a constant regardless of `num_layers`.

Note: constructing a full 8B-param model is CPU/memory-heavy — budget ~60-90s per construction call for the largest (`agent_8b.yaml`) config; batch multiple configs into one background bash call and `hub wait` rather than blocking synchronously per config.

## SDPA backend fallback list — CPU backward gotcha
`torch.nn.attention.sdpa_kernel([SDPBackend.FLASH_ATTENTION, SDPBackend.EFFICIENT_ATTENTION, SDPBackend.MATH])` combined with `F.scaled_dot_product_attention(..., enable_gqa=True)`:
- **Passes** an isolated smoke test: `out = sdpa(...); out.sum().backward()` with small hand-built tensors, on this machine's CPU-only PyTorch 2.14.0 build.
- **Fails** when exercised through the real training loop (`smrt.train.train_loop`, different tensor shapes and the actual grad-accumulation path) with:
  ```
  RuntimeError: derivative for aten::_scaled_dot_product_flash_attention_for_cpu_backward is not implemented
  ```
This means an isolated backward-pass smoke test is **not sufficient evidence** that a chosen SDPA backend list is safe for real training on CPU — always run the actual `python -m smrt.train --config configs/tiny_cpu.yaml` end-to-end smoke retrain before trusting a non-MATH backend choice.

**Fix**: revert to `sdpa_kernel(SDPBackend.MATH)` only (drop the list). MATH is always correct on CPU, just not the fastest backend. This is documented in this repo's own architecture-modernization plan as the expected contingency, not a bug — treat any FLASH/EFFICIENT backend choice as provisional until proven through a real train_loop run, not just a synthetic tensor test.
