---
name: smrt-chat-repl-and-undertrained-checkpoint-signal
description: "Use when interacting with a SMaRT checkpoint conversationally via smrt/chat.py (the agent-vocab chat REPL), or when a SMaRT/agent checkpoint's greedy-decoded output is just one special token (e.g. |assistant|) repeated hundreds of times until max_new_tokens — that repetition is the expected signature of an undertrained/toy checkpoint (few gradient steps, synthetic/random data), not a bug in the decode loop or chat template."
---

## smrt/chat.py — interactive REPL against a SMaRT checkpoint

`smrt/chat.py` (in the SMaRT repo, `/home/wils/Documents/Development/smart`)
provides a REPL to talk to any checkpoint trained with the agent tokenizer
(`smrt.data.tokenizer.AGENT_VOCAB_SIZE == 200027`).

```
PYTHONPATH=. python -m smrt.chat --checkpoint <path>.pt \
  [--max-new-tokens 200] [--max-context 4096] [--system-prompt "..."]
```

- Loads the checkpoint's own saved `config` dict via `config_from_dict`
  (same pattern as `smrt/evaluate.py::_load_model` /
  `smrt/eval_tools.py::_load_model`), so the model architecture always
  matches what's in the .pt file — never hand-specify model dims.
- **Hard guard**: refuses to run (raises `ValueError`) if
  `cfg.model.vocab_size != AGENT_VOCAB_SIZE`. Byte-vocab (256) or
  gpt2-vocab (50257) checkpoints were never trained with the
  `<|user|>`/`<|assistant|>`/`<|end|>` chat template, so chatting with them
  via this script is meaningless — don't bypass this guard.
- Greedy-decodes one token at a time via `model(x, mem_states=None)` with
  **no** `torch.no_grad()` — required because `NeuralMemory.update()`
  always builds a differentiable graph
  (`torch.autograd.grad(..., create_graph=True)`) even at inference; this
  mirrors `smrt/evaluate.py::_decode_answer`'s documented contract exactly.
- Maintains conversation history as one growing token sequence
  (`<|system|>...<|end|>` once, then `<|user|>...<|end|><|assistant|>` +
  reply + `<|end|>` per turn), truncated from the front once
  `--max-context` is exceeded. `reset` clears history back to just the
  system prompt; `exit` quits.
- To drive it as a real interactive session (not just canned demo prompts),
  launch it via `hub start` with `pty: true` and a `ready` regex matching
  its startup banner (`"Chatting with the checkpoint"`), then use
  `hub send`/`hub logs --follow` to type into it and read replies turn by
  turn.

## Diagnostic: repeated single-special-token output = undertrained checkpoint, not a bug

If a greedy decode loop (this REPL, `eval_tools.py`, `eval_code.py`, or any
custom script) against a SMaRT/agent checkpoint produces the **same
special token repeated over and over** until hitting the `max_new_tokens`
cap — e.g. `<|assistant|><|assistant|><|assistant|>...` two hundred times,
never emitting `<|end|>` — this is the expected output of a checkpoint that
has seen only a handful of gradient steps on synthetic/random data (a
wiring smoke-test checkpoint, not a real training run). It is **not**:

- a bug in the decode loop (argmax-of-logits greedy decoding is correct),
- a tokenizer round-trip bug (the special token is landing as one id,
  correctly, which is exactly why it repeats cleanly instead of garbling),
- a chat-template bug.

The model's argmax has simply collapsed onto whichever token had the
highest average training-time frequency/logit bias this early — with
only 1-2 optimizer steps the embedding/lm_head weights are still close to
their random init plus one or two gradient nudges, so there is no learned
"stop" signal. **Do not "fix" this by patching the decode/eval code** —
verify how many training steps and what data (synthetic vs. real) the
checkpoint actually trained on before assuming a functional bug. The
correct response is to either (a) explain to the user that no real
training happened yet (state the real checkpoint provenance: model size,
step count, dataset), or (b) run/point at a real multi-thousand-step
training run on real data before expecting coherent output.
