---
name: smrt-sft-pipeline-truncate-empties-assistant-span
description: "Use when writing or debugging an SFT data pipeline in the SMaRT codebase (/home/wils/Documents/Development/smart, smrt/data/*.py) that builds (token_ids, loss_mask) trajectories and pads/truncates them to a fixed seq_len — especially when smrt/sft.py's diagnostics show loss: NaN on some steps. Also covers the shared smrt/data/sft_common.py::pad_or_truncate helper all 4 SFT loaders (toolcalls.py, web_search_bias.py, code_repair.py, general_instruction.py) now use."
---

## Symptom

`python -m smrt.sft`'s `sft_diagnostics.jsonl` shows `"loss": NaN` on some steps but not others, with training recovering cleanly on later steps (no permanent corruption).

## Root cause

Every SMaRT SFT data pipeline builds a trajectory as `(token_ids, loss_mask)` where `loss_mask` is 1 only on the assistant span. When a trajectory is longer than `seq_len`, the shared contract truncates from the end. If the assistant span sits near/at the end of a long trajectory (common for sources like `code_repair.py` where the corrupted+original Python source can be long), truncation can remove the ENTIRE assistant span, leaving `loss_mask` all zeros for that row. `smrt/sft.py`'s `cross_entropy(..., ignore_index=-100)` reduction then has zero unmasked positions → `0/0` → `NaN`.

## Fix (already applied)

`smrt/data/sft_common.py::pad_or_truncate(ids, mask, seq_len, end_id) -> tuple[list,list] | None`:
- Pads short trajectories with `end_id` at mask 0 (unchanged behavior).
- Truncates long trajectories from the end, but returns `None` if the truncated mask has no `1`s left.
- Callers (`toolcalls.py`, `web_search_bias.py`, `code_repair.py`, `general_instruction.py`) `continue`/redraw on `None` instead of yielding a target-less row.

## When adding a NEW SFT data pipeline in this repo

Always call `smrt.data.sft_common.pad_or_truncate` instead of hand-rolling pad/truncate logic — do not reintroduce the duplicated inline block. Skip (or redraw, for infinite generators) the row when it returns `None`.

## Verification pattern

`tests/test_sft_common.py` covers: short-trajectory padding, safe truncation (assistant span survives), the NaN-producing case (mask empties out → `None`), and exact-length passthrough. After touching any SFT loader, re-run the smoke pipeline and grep `sft_diagnostics.jsonl` for `NaN`:

```bash
PYTHONPATH=. python -m smrt.sft --config configs/agent_tiny_cpu.yaml
grep -c NaN /tmp/agent_tiny_sft_ckpt/sft_diagnostics.jsonl   # should be 0
```
