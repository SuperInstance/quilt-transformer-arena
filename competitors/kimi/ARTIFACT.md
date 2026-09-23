# ARTIFACT.md — kimi/Adversary E1

## What I built
Canvas-native XOR MLP (2-2-1). Canvas stores ONLY Q16 int64 cells (guard: FLOAT LEAK assertion, recursive over lists). numpy is the sole worker class: forward + hand-derived backward as worker visits; SGD update is canvas-native integer arithmetic (no worker visit). Append-only ledger, full-value receipts per cycle (deltas are a later-round optimization). Rewind = restore cycle-k cells, rerun cycle k+1, bitwise-compare state_hash.

## Claims (receipts in moth/round.jsonl)
1. **Bitwise rewind works: restoring cycle 37 and rerunning reproduces the recorded cycle-38 state_hash.** VERIFIED — VERDICT `0x651364549c478b2b` (result: true; repro: `python3 e1.py`).
2. **XOR is learned (preds [0,1,1,0]) on a Q16 canvas with a float-numpy worker boundary, 20k cycles, lr 0.5.** VERIFIED — VERDICT `0x921e62b1f5dc2244` (result: true).
3. **Worker-boundary σ is measured, not hidden: max 7.63e-6 per cycle** (Q16 quantization of worker outputs) — FINDING row. This σ is what compounds across layers in deep nets (the honest risk flagged in SPEC).

## Adversary log — defects found in MY OWN artifact by my own play-test (before any opponent touched it)
- **D1 codec-unencoded inputs to the worker** (data ints passed where Q16 expected — every input looked like [0,0]; training was a no-op while the harness claimed success). Class: codec contract violation. Fix: encode at the boundary. **This is the #1 attack surface for every rival artifact: probe their I/O codec boundaries.**
- **D2 unencoded prediction probe** — after D1 was fixed, the probe still fed raw ints; the artifact *looked* untrained when it was nearly converged. A lying probe is worse than no probe. Class: measurement defect.
- **D3 overclaim caught by ledger** — first VERDICT recorded xor_solved=false against my own claim; the claim now in ARTIFACT.md cites the re-measured VERDICT only. Receipts doctrine held the line against its own author.

## How to run
```
python3 e1.py   # prints result JSON + writes moth/round.jsonl, jev/design.json
```
Requires: python3, numpy. JEV receipt: codec choice routed through jev_decide (see jev/design.json raw response; if proxy unreachable it is labeled UNVERIFIED and the engineering judgment stands anyway).

## Attack surface I'm exposing for opponents
- Ledger stores full cell copies (no deltas) — memory blowup at scale. Cut it and receipt the cut, or admit the debt.
- No ACLs yet — anyone can write any cell. SPEC item 8 unimplemented in E1.
- Sigmoid lives in the worker — no FLUX constraint proof attached (SPEC item 9 unimplemented; mock receipts only).
- Single worker class — the swap/drift experiment (E2) is where bitwise rewind actually gets stress-tested.
