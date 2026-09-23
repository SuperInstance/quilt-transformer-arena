# crush/ — Round 1 — the Ascetic

E1 as one source file. Fewest concepts that satisfy the round task: **9 Q16 integer cells, one opcode, one worker, one receipt per cycle, rewind = snapshot restore + rerun + bitwise compare.**

## What I built

`e1.py` (≈150 lines) — canvas-native 2-2-1 tanh MLP that learns XOR.

| Concept | Implementation |
|---|---|
| Canvas | plain dict, 9 cells, python ints only (Q16.16). Never sees a float; asserted every cycle. |
| Codec | Q16.16 int64; `mul = (a*b) >> 16` (floor semantics, exact-by-definition). |
| Worker | `numpy` is the only worker class; flies exactly one opcode: `tanh`. 8 flights/cycle (2 per XOR row). Wire is int→int; floats exist only inside the flight (σ residual reported, never stored). |
| Linear algebra | canvas-native exact int arithmetic (dot products, gradients, updates — backward is hand-derived exact arithmetic on live cells). |
| Ledger | one receipt per cycle: `{cycle, pre, post, sigma, state}` where `post = kev(canonical(state))` and `post[n] == pre[n+1]` (hash-chained snapshots; 3001 rows incl. genesis). `ledger.jsonl`. |
| Rewind | restore snapshot k → rerun cycles k+1..N → compare every cell bitwise at every cycle. |
| σ accounting | per-cycle scalar `sigma_max` = max codec rounding residual over flights; ≤ 2⁻¹⁶ observed 7.63e-06. |

## Run

```bash
python3 e1.py        # train 3000 cycles, verify, write ledger.jsonl + moth/round.jsonl
python3 e1.py jev    # route design choice through JEV, write jev/design.json
```

## Claims (each cites a VERDICT hash from `moth/round.jsonl`; repro for all: `python3 e1.py`)

1. **XOR learned**: 4/4 rows classified, min decision margin from the 0.5 boundary = 0.4728, in 3000 cycles. VERDICT `0xf564fb45ca63551f`.
2. **Bitwise rewind verified by rerunning**: restore at k ∈ {0, 1500, 2995}, rerun to N — every cycle's state bitwise-equal (`==` on ints, all 9 cells), rerun final hash `0x14bae40992f440af` == original. VERDICT `0x4f232de958be3fab`.
3. **Ledger integrity**: `kev(state) == post` and `post[n] == pre[n+1]` for all rows; tampering one cell by +1 is detected (chain check fails). VERDICT `0x94588b100786b299`.
4. **No float in canvas**: all cells python int at every cycle (in-loop assert); worker wire int→int; σ_max = 7.63e-06 ≤ 2⁻¹⁶. VERDICT `0x762f0495ec02bbe1`.
5. **numpy is the only worker class**, one opcode (`tanh` via `np.tanh`). VERDICT `0x54115f47723f94d6`.

Scope note (honesty): bitwise rewind is claimed for same-process and cross-process reruns in this sandbox (verified: two fresh `python3 e1.py` processes both end at `0x14bae40992f440af`). Cross-platform/cross-numpy-build determinism of `np.tanh` is NOT claimed — that is E2 drift territory.

## Receipts

- `jev/design.json` — routed design choice (tick semantics + codec) through `harness.jev_decide()`. Proxy answered LIVE but HTTP 400 `api_usage_error` for its own documented payload (also for models `jev`, `default`) — no score obtainable. Per anti-sycophancy doctrine (score = evidence, not approval) the choice was made by judgment: **tick = one full pass over the 4 XOR rows** (8 flights; single-pattern ticks would 4× the ledger for zero added verifiability) and **Q16.16 with floor-mul** (dyadic num/den pairs would double cell concepts for identical exactness). Raw 400 receipt kept. FINDING `0x372abb49f71b9803`.
- `moth/round.jsonl` — 17 rows: 5 VERDICT (above), 10 REFUSAL (schema cuts, below), 2 FINDING (JEV 400; `receipts.py:43` comment shows a 17-hex-digit form `kev` can never emit — value-equal, cosmetic. FINDING `0xfe9c8c42c2746a95`).

## REFUSAL ledger — schema fields cut for E1 (each a REFUSAL row with justification)

per-cell ⟨v,τ,σ⟩ provenance vectors · ACL matrix / Pauli-exclusive locks · nudge cells · flux-constraint proof field · worker capability cards · multigrid store · per-flight contract/I/O hash triples (pre/post chain pins a one-opcode worker) · ledger-to-ledger autodiff · RNG (fixed int init constants) · ledger segmentation.

Rationale: if a field isn't load-bearing for E1's claims, it is ceremony; every cut is receipted so the Registrar can re-add fields when their experiment needs them.
