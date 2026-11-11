# PyTorch gotchas

General PyTorch / LM-training facts that are not tied to any one repository.

## Absurd initial loss with tied embeddings

**Symptom:** Fresh decoder-only LM with tied `embed`/`lm_head` shows initial cross-entropy ~350 with a 50k vocab, where chance is `ln(vocab)` ≈ 10.8.

**Cause:** `nn.Embedding` defaults to N(0, 1). With weight tying, std-1.0 rows scale every logit ~50x (`logits.std()` ≈ 20, `|max|` in the hundreds). This is a logit-scale problem, not a data bug. Rule out other components first (e.g. rebuild with the memory/attention block disabled); if CE barely moves, the blowup is in embed/head.

**Fix:** In-place GPT-2-convention init right after constructing the table, before tying:

```python
self.embed = nn.Embedding(cfg.vocab_size, cfg.d_model)
nn.init.normal_(self.embed.weight, mean=0.0, std=0.02)
# ... then tie: self.lm_head.weight = self.embed.weight
```

Verify: fresh-model CE lands within ~0.2 of `ln(vocab_size)`. Must run in the same process that constructs the model (an `importlib.reload`'d stale module hides the fix; re-instantiate after reload). A `torch.no_grad()` forward is fine for the CE probe, but block-by-block std tracing must keep grad enabled if any block calls `torch.autograd.grad(..., create_graph=True)` internally.

_Migrated from: tied-embedding-init-loss-check_
