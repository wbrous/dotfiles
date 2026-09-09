---
name: tied-embedding-init-loss-check
description: Diagnose absurd initial LM loss from tied embedding init scale (std 1.0 vs 0.02)
---

# Tied-Embedding Init Loss Check

When a fresh decoder-only LM with a tied `embed`/`lm_head` shows an absurd initial cross-entropy (e.g. ~350 with a 50k vocab where chance is `ln(vocab)` ≈ 10.8), check the embedding table init scale before touching anything else.

## Diagnosis

1. Compute chance loss: `math.log(vocab_size)`. If measured init CE is 10-50x higher, suspect logit scale, not data.
2. Print `model.embed.weight.std()`. `nn.Embedding` defaults to N(0, 1). With weight tying, std-1.0 rows scale every logit ~50x, which alone explains CE in the hundreds.
3. Confirm: `logits.std()` ≈ 20 and `logits.abs().max()` in the hundreds at init means the head is amplifying, not that the data pipeline is broken.
4. Rule out memory/attention first with a cheap ablation: rebuild with `memory.disabled=True` — if CE barely moves, the blowup is in embed/head, not memory.

## Fix

In-place GPT-2-convention init right after constructing the table, before tying:

```python
self.embed = nn.Embedding(cfg.vocab_size, cfg.d_model)
nn.init.normal_(self.embed.weight, mean=0.0, std=0.02)
# ... then tie: self.lm_head.weight = self.embed.weight
```

Verify: fresh-model CE should land within ~0.2 of `ln(vocab_size)`.

## Notes

- Must run in the same process that constructs the model (eval sandbox `importlib.reload` gotcha: a stale imported module hides the fix — re-instantiate after reload).
- `torch.no_grad()` forward is fine for the CE probe, but block-by-block std tracing must keep grad enabled (memory `update()` uses `torch.autograd.grad(..., create_graph=True)` and throws under `no_grad`).
- The `datasets`-library `PyGILState_Release` crash *after* "Training complete" prints is a teardown race in streaming-dataset threads, not a training failure — if `step_N.pt` and the diagnostics file are intact, the run succeeded.
