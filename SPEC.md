# SPEC.md — quilt-transformer shared spec (all rivals build against this)

## Mandate
Ground-up paradigm. Canvas (quilt cell matrix) = permanent town. Math engines = disposable laborers. NOT modified transformers.

## Locked v0 decisions (from kimi1 research/2026-09-24-quilt-transformer/RESEARCH.md)
1. Three layers: Archival Canvas (multigrid cell store, ℚ/Q16 exact values, ⟨v,τ,σ⟩ provenance) → Contract Protocol (declarative op requests) → Transient Workers (stateless, hot-swappable).
2. Canvas never sees a float. Codec: Q16 fixed-point or ℚ dyadics.
3. Only transcendentals visit workers (softmax/exp/high-rank matmul). Linear/exact ops canvas-native.
4. Ticks = serialization barriers. Workers read at tick start. Nudge writes land between barriers. No locks.
5. Autodiff = ledger-to-ledger transformation (backward contracts generated from forward receipts).
6. Rewind = ledger rollback to cycle k, then re-derive. Bitwise where codec exact.
7. Nudge cells: additive offset | multiplicative gate (constraint tighten) | structural re-LINK (topology edit). Nudges are ledger entries → individually retractable.
8. Critic/zone ACL: constraint-cell write only. Writer sets Pauli-exclusive per cell per tick.
9. Every flight receipts: contract hash, input hashes, output hashes, σ report, worker_class, flux constraint proof (mock ok if marked UNVERIFIED).
10. Worker capability card = {opcodes, measured σ vs reference, throughput, codec compliance}.

## Experiment ladder (rivals race on these)
- E1: canvas-native MLP (XOR), numpy sole worker, ledger receipt/cycle, bitwise rewind verified.
- E2: worker swap (numpy→pure-python), per-cycle drift measurement.
- E3: mid-run nudge at cycle k; verify divergence k+1; rewind erases nudge.
- E4: dual-zone — Zone A bigram model, Zone B repetition-critic writing constraint cells only.

## Adversarial surface (what your opponent will attack)
- Rewind claims (must be BITWISE, verified by rerunning).
- Ledger integrity (tamper → detect).
- Codec exactness (any float leak = defect).
- ACL enforcement (critic touching weights = defect).
- σ accounting (drift must be reported, not hidden).
