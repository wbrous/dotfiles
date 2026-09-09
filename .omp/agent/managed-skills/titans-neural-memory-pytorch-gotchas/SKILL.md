---
name: titans-neural-memory-pytorch-gotchas
description: "Use when implementing or debugging a Titans-style (\"Memory as Context\") neural long-term memory module in PyTorch — a small MLP whose weights (theta) are updated online via torch.autograd.grad(..., create_graph=True) inside the forward pass — combined with sliding-window causal attention via scaled_dot_product_attention. Also applies to any project in ~/Documents/Development/smart (SMaRT model)."
---

## Context

Built SMaRT (Sliding-window Memory and Recall Transformer, ~50M params) at
`~/Documents/Development/smart`: sliding-window local attention + Titans-style
MAC neural memory (per-example evolving MLP weights via momentum-decayed,
meta-learned gradient descent). Five non-obvious bugs surfaced only by
actually running the code, not from reading the design doc.

## Gotchas

1. **Memory-read feature-dim mismatch with attention's extra_kv.** If the
   memory module's `read()` returns `(B, T, value_dim)` and attention's
   `qkv_proj` expects `d_model`-dim inputs for both `x` and `extra_kv`
   (concatenated persistent tokens + memory read), `value_dim != d_model`
   breaks the `torch.cat` along the feature dim. Don't project inside the
   memory module if a test pins `read()`'s output shape to `value_dim` —
   add the `Linear(value_dim, d_model)` projection in the *block* that
   consumes the read, not in the memory module itself.

2. **CPU SDPA flash-attention has no backward for additive masks.**
   `F.scaled_dot_product_attention(q, k, v, attn_mask=mask)` on CPU (at
   least PyTorch 2.14+cpu) raises `RuntimeError: derivative for
   aten::_scaled_dot_product_flash_attention_for_cpu_backward is not
   implemented` on `.backward()`. Fix: wrap the call in
   `with torch.nn.attention.sdpa_kernel(torch.nn.attention.SDPBackend.MATH):`.
   This is backend-portable (works identically on CPU/CUDA/ROCm) at the
   cost of losing flash/mem-efficient kernel speed on GPU — document this
   as a follow-up perf tuning item for whoever runs the real GPU training.

3. **`torch.no_grad()` breaks any module that does an internal
   `torch.autograd.grad(..., create_graph=True)` inside its forward pass.**
   A Titans-style memory's `update()` computes its own inner gradient as
   part of the *forward* computation (not just the outer training loss).
   Wrapping the whole model call in `torch.no_grad()` during eval/inference
   (e.g. greedy decoding) makes every tensor lack `requires_grad`, so the
   inner `autograd.grad` call fails with "element 0 of tensors does not
   require grad and does not have a grad_fn". Fix: never wrap such a
   model's forward pass in `no_grad()`; only `.item()`/`.detach()` the
   final output you read out. This applies during eval too, not just
   training — memory-as-context style models never run "true" inference
   mode.

4. **Checkpoint resume needs RNG state, not just model/optimizer state.**
   If training data order depends on `random.Random(seed)` (or `torch`'s
   global RNG) advancing over the course of a run, resuming from a
   checkpoint without restoring that RNG's exact state causes the resumed
   run to diverge from a straight-through run at the same step (different
   batch is drawn). Save `rng.getstate()` / `torch.random.get_rng_state()`
   in the checkpoint dict; restore both on `--resume`. A
   resume-vs-straight-through-loss-matches test will otherwise fail with a
   confusing "close but not equal" loss discrepancy that looks like a
   numerical-precision issue but is actually a data-order issue.

5. **Post-hoc context-length truncation of synthetic needle-in-haystack
   examples can silently zero out the answer span.** If you build
   `filler_before + needle + filler_after + question + answer` first and
   *then* trim to `context_len`, a too-long example gets its `answer_span`
   clipped to zero length (`(N, N)`), making the eval scoring loop compare
   an empty predicted list to an empty true list — which trivially
   "matches", producing a misleadingly perfect (e.g. 100%) accuracy on an
   untrained model instead of the expected near-random accuracy. Fix:
   reserve token budget for the fixed-overhead parts (needle sentence +
   question + answer, measured via `tokenizer.encode` on a placeholder)
   *before* computing how much filler to generate, so the answer is never
   truncated away. Symptom to watch for: eval accuracy of exactly 1.0 (or
   suspiciously round numbers) on a barely-trained model — check for
   zero-length answer spans before trusting the eval pipeline.

## Also useful

- `~40M-60M` non-embedding param target for a "~50M param" transformer:
  don't hand-estimate layer count — measure via
  `sum(p.numel() for n,p in model.named_parameters() if 'embed' not in n and 'lm_head' not in n)`
  and binary-search `num_layers` (params scale ~linearly with layer count
  at fixed `d_model`). In this project, 8 layers @ d_model=512 gave only
  26.6M; 15 layers gave 49.9M.
- Python 3.14 (the system default here) doesn't have prebuilt PyTorch
  wheels yet; use a `python3.11` interpreter (via mise/`.local/bin`) for
  the venv when torch install fails with `ModuleNotFoundError` after a
  seemingly-successful `pip install torch`.
