# ROUND 1 — divergent artifacts

Read ../ARENA.md and ../SPEC.md first. Build YOUR OWN implementation of Experiment E1 in this directory:
**canvas-native MLP (XOR), numpy as the ONLY worker class, one ledger receipt per cycle, bitwise rewind to cycle k verified by rerunning.**

Philosophy assignments (diverge HARD — sameness loses):
- claude/ → **the Registrar**: maximal integrity. Typed cell blocks, full contract schema v0, content-hash-pinned flights, ACL matrix enforced, dream-ready ledger segments. Favor correctness proof over brevity.
- crush/ → **the Asectic**: radically minimal. Fewest possible concepts; if a schema field isn't needed for E1, cut it and receipt the cut as a REFUSAL row with justification. Favor lines-of-code clarity over features.
- kimi/ → **the Adversary**: build E1, then attack both theorems: where does bitwise rewind actually break (codec leak, float in numpy path, non-determinism)? Your deliverable includes CONFIRMED defects in the other two artifacts (or a VERDICT that you found none — say which, with repro).

## Mandatory receipts (missing = round forfeit)
1. `jev/design.json` — at least 1 design choice routed through harness.jev_decide() (e.g. codec choice, tick semantics). Record the score; decide by judgment; keep the raw receipt.
2. `moth/round.jsonl` — your run results: VERDICT rows for claims you VERIFIED by execution (with repro command), FINDING rows for defects found, REFUSAL rows for anything you refused/cut.
3. `ARTIFACT.md` — what you built, how to run it, what you claim (every claim must cite a VERDICT hash from your moth log).

## Rules
- python3 + numpy only. No network except the JEV proxy (via harness).
- Verify before claiming: `python3 -c` repro commands in your VERDICT rows.
- Timebox: 60 min. Deliver partials with REFUSAL rows over silence.
- Run `python3 ../harness/receipts.py` self-test before starting.
