# E1 — the Registrar: a canvas-native XOR MLP with a provable rewind

Round 1 artifact for the `claude/` lane. Philosophy: **maximal integrity** — typed
cell blocks, full contract schema v0, content-hash-pinned flights, an enforced ACL
matrix, dream-ready ledger segments, and a correctness proof (13 executable claims)
over brevity.

---

## What was built

| file | role |
|---|---|
| `quilt.py` | the kernel: canvas, codec, ACL matrix, contracts, ledger, engine, worker, replay |
| `run_e1.py` | Experiment E1 + the 13-claim verification suite; writes the VERDICT rows |
| `receipt_findings.py` | round-level FINDING / REFUSAL rows (own defects, infra defects, refusals) |
| `receipt_playtest.py` | FINDING / VERDICT rows for the rivals' artifacts |
| `verify_playtest.py`, `tamper2.py` | independent repro of every CONFIRMED rival defect |
| `jev/design.json`, `jev/probe.json` | raw JEV receipts (see *Design decision D1*) |
| `moth/round.jsonl` | the receipt ledger — 30 rows: 15 VERDICT, 13 FINDING, 2 REFUSAL |

### The three layers

**1. Archival Canvas** (`Canvas`) — a typed cell matrix over 12 blocks
(`W W2 B B2 Z H Y G DY DH T C`). Every cell is `<v, tau, sigma, writer, tick>`:

* `v` is **always a Python `int`** in Q16.16 (`SCALE = 1<<16`). The canvas raises
  `CodecError` on any non-int write — bools included.
* `sigma` is an honest provenance class: `EXACT` (no rounding happened),
  `Q16_ROUND` (rounded at the worker's float→int return boundary),
  `Q16_SHIFT` (rounded by a `Q32→Q16` arithmetic shift). Every rounding in the
  whole run is billed to one of these and counted per cycle.

**2. Contract Protocol** (`make_contract`) — declarative schema v0:
`{v, op, cycle, tick, reader{role,cells}, writer{role,cells}, worker{class,opcodes},
codec{name,scale,int_only}, flux{proof,verified}}`. Contracts are content-addressed
(`kev(canonical(body))`) and each flight pins the content hash of every cell it
reads, so a stale pin is detected rather than silently reused.

**3. Transient Worker** (`NumpyWorker`) — stateless, two opcodes (`sigmoid`,
`sigmoid_grad`), carded with `{class, opcodes, codec, float_interior, sigma_vs_reference}`.
float64 exists **only inside those two method bodies**; every return is a Q16.16 int.

### The boundary that makes the theorem provable

SPEC rule 3 says *only transcendentals visit workers*. Enforced literally: the
canvas computes the exact linear part and publishes only the transcendental
**argument** in block `Z`; the worker reads `Z` and writes activations. **Weights
never leave the canvas**, so the worker's read surface contains no parameter at all
(`ACL["WORKER"]["W"] == "-"`). Forward is therefore two canvas↔worker round-trips:

```
canvas: zh = (b<<16 + Σ w·x) >> 16      exact Q32 accumulate, ONE rounding
worker: a  = sigmoid(zh)
canvas: zy = (c<<16 + Σ v·a) >> 16      uses the stored ACTIVATION
worker: y  = sigmoid(zy)
```

Backward is a ledger-to-ledger transform of the forward receipt. Loss is binary
cross-entropy, which makes the output delta `ŷ − t` — **exact** in Q16, with no
sigmoid-prime factor.

### Integrity machinery (all enforced, none asserted)

* **ACL matrix** — `role × block → r / rw / -` for `WORKER, NUDGER, CRITIC,
  AUDITOR, REGISTRAR`, checked on every read *and* write. The critic can write `C`
  and nothing else.
* **Pauli-exclusive** — one writer *role* per cell per tick; a second distinct role
  raises.
* **Hash chain** — every ledger entry carries `prev_hash`; body, kind, seq and
  prev are all covered by `kev`.
* **Segments** — `seal_segment` closes a span with a merkle root over its entry
  hashes; seals are re-derivable, so a future dream process gets a stable prefix.
* **Replay rewind** — rewind retains a ledger **prefix** and re-executes it from
  genesis. Nothing is restored from a snapshot.

---

## How to run

```bash
python3 ../harness/receipts.py        # referee's kev self-test (passes)

# rebuild the receipt ledger from scratch, in this order:
rm -f moth/round.jsonl
python3 receipt_findings.py           # own defects, infra defects, refusals
python3 receipt_playtest.py           # rival play-test rows
python3 run_e1.py                     # all 13 claims; OWNERSHIP audits the ledger

# other entry points
python3 run_e1.py --only REWIND       # reproduce a single claim
python3 run_e1.py --cycles 100        # shorter run
python3 verify_playtest.py            # independent repro of the crush defects
python3 tamper2.py                    # independent repro of the kimi defects
python3 hashseed.py 0                 # kimi determinism under a set hash seed
```

Ledger fingerprint of the delivered `moth/round.jsonl`: sha256 `b248f9adc7526cca…`.

Every row my scripts write is stamped `content.lane == "claude"`, and the
`OWNERSHIP` claim audits the whole file for that marker — so rival rows that land
here are detected rather than silently mixed into my record.

Requires python3 + numpy, nothing else. No network (the JEV proxy is down — see D1).

> Note for the referee: `run_e1.py` takes `MOTH` from its own absolute path, so it
> writes only into `claude/moth/`. Rival artifacts that use a cwd-relative path
> will contaminate this ledger if run from this directory — see `MOTH-CWD-CONTAMINATION`.

---

## Results

Training: 300 cycles, lr = 1.0 (Q16), 2×2→2→1 MLP, 4-case full batch.
**Solves XOR at cycle 57**, final outputs `[0.0133, 0.9899, 0.9899, 0.0110]`,
`loss_q16 = 32`, 81 cells, 301 ledger entries, **one FLIGHT receipt per cycle**.

## Claims — every one verified by execution

Each claim below cites its VERDICT `content_hash` in `moth/round.jsonl`. Repro for
each: `python3 run_e1.py --only <NAME>`.

| # | claim | statement | VERDICT hash | headline number |
|---|---|---|---|---|
| 1 | `CODEC` | zero floats in canvas **and** ledger; non-int writes refused | `0x612ea02b706eafd9` | 81 cells + 301 entries scanned, 0 floats |
| 2 | `CONVERGE` | XOR solved, 1 receipt/cycle | `0xc99c6be2de46be6c` | solving cycle 57 |
| 3 | `REWIND` | bitwise rewind to k by replay + rerun | `0x11acc6bfc8c6513d` | k ∈ {0,1,7,75,150,299} all bitwise |
| 4 | `CHAIN` | tamper detected | `0xd0982d7069c01d39` | body/kind/seq/forge all caught |
| 5 | `ACL` | role×block matrix enforced | `0x2e090a78e5ecfc1c` | 7 illegal writes refused |
| 6 | `PAULI` | one writer role per cell per tick | `0x67f5218f27d82f3e` | cross-role write refused |
| 7 | `PINS` | flight input pins detect mutation | `0x8e67e154c5d20666` | 2/2 mutations caught |
| 8 | `SEGMENTS` | dream-ready segment seals verify | `0x9aa66bcbbdcc481d` | 2 segments, roots re-derived |
| 9 | `MARGIN` | worker quantisation is not knife-edge | `0xb1cf25847bd6dcf6` | min margin 154 Q16 units |
| 10 | `GRADIENT` | canvas Q16 grads match a float64 path | `0xf664464bcc9327d2` | max abs err 4.25e-05 |
| 11 | `HASHSEED` | replay is PYTHONHASHSEED-independent | `0xa8a6e130d3837dd0` | 4 subprocesses, 1 distinct hash |
| 12 | `SELFATTACK` | 3 attacks on the rewind theorem are caught | `0xfb48b26132d88055` | 3/3 detected |
| 13 | `OWNERSHIP` | every row in this moth ledger is authored here | `0xd7c09ea9bb84b761` | 30/30 rows lane-marked |

### The rewind claim, precisely

For each k, `rewind_and_rerun` drops every entry after cycle k, rebuilds the canvas
by **executing the retained prefix from genesis**, then recomputes the discarded
suffix. Three strict checks per k:

1. the replayed prefix re-derives the state hash that the original flight k recorded;
2. re-running to N lands on the original final state hash `0x039110a57700bc89`;
3. **every re-derived receipt body is bitwise identical** to the original — the
   whole 300-flight ledger hashes equal, not just the final state.

### Scope of the bitwise claim (stated, not implied)

Bitwise determinism is claimed for a **fixed python3 + numpy build**. The residual
risk is `float64 exp()` drift across libm/numpy builds inside the worker. Rather
than assume it away, `MARGIN` measures the distance from each worker return to the
nearest Q16 rounding boundary: the minimum over 300 flights is **154 Q16 units**
(worst case over a full sigmoid argument sweep: 131). A perturbation would have to
move a result by >130/65536 of the signal range to flip one bit — so the claim is
robust to libm jitter, and the number is published rather than hidden.

---

## Design decision D1 — codec at the transcendental boundary

**Decision: Q16.16 fixed point.** Rationale: exact rationals keep arithmetic
lossless but make cells non-int, breaking codec closure *and* the integer hash that
gives `state_hash` its bitwise meaning; an exact integer piecewise-linear activation
removes the transcendental but changes the model class E1 exists to exercise.
Q16.16 keeps the canvas a closed integer algebra and makes every worker call an
`int → int` function.

**Jev score: unavailable.** The proxy returns HTTP 400 (`api_usage_error`) for every
request shape tried. Raw receipts kept at `jev/design.json` and `jev/probe.json`.
See REFUSAL `0x06739e8987fc7fc3`.

---

## Defects found this round

Ten FINDINGs, all with repro, in three groups.

**In my own artifact (found and fixed during the round):**

| severity | hash | claim |
|---|---|---|
| MEDIUM | `0x49e130bdb86162b0` | `SELF-FORWARD-BUG` — output layer consumed hidden pre-activations instead of activations; XOR was unfittable (loss pinned at 1.0). Found by float64 cross-check. Fixed. |
| MEDIUM | `0x5b57fe357594567f` | `SELF-CODEC-LEAK` — `sigma_report` wrote a float into every flight body, violating my own codec rule. Fixed (integer `exact_permille`). |
| LOW | `0xe17346ee8d168a6e` | `SELF-SEGMENT-OFFBYONE` — multi-segment verification false-negative. Fixed. |

**In the shared infrastructure:**

| severity | hash | claim |
|---|---|---|
| HIGH | `0x94a495c56a3f7e44` | `HARNESS-JEV-LIVE-MISLABEL` — the shared harness records a **400 error body** as `status="LIVE"`, so a failed JEV decision is indistinguishable from a real one. Any rival citing a "LIVE" score this round may be citing an error page. Not patched by me: the harness is a read-only bootstrap file. |
| HIGH | `0x2fc1c811fc40a033` | `MOTH-CWD-CONTAMINATION` — a rival's artifact writes receipts to a cwd-relative path; running it from this directory appended 17 crush-authored rows to my ledger and **truncated 10 of my VERDICT rows**. Now guarded by the `OWNERSHIP` claim. |

**In the rivals' artifacts** (see the play-test section):

| severity | hash | claim |
|---|---|---|
| HIGH | `0xec8b562f9b94d2dd` | `PLAYTEST-CRUSH-CHAIN-NOT-A-CHAIN` |
| HIGH | `0x713af27363fb8e4b` | `PLAYTEST-CRUSH-INTEGRITY-BLIND-FIELDS` |
| HIGH | `0x95fbf0c7dbc424ba` | `PLAYTEST-KIMI-REWIND-AUTHENTICATES-NOTHING` |
| MEDIUM | `0x612212c36bb8a73c` | `PLAYTEST-KIMI-REWIND-IS-SNAPSHOT-RESTORE` |
| LOW | `0x5d4c094a6a3456da` | `PLAYTEST-CRUSH-VERDICT-LITERALS` |
| LOW | `0x02932be685c15580` | `PLAYTEST-KIMI-BOOL-ACCEPTED-BY-CANVAS` |
| INFO | `0x20b4394825d32126` | `PLAYTEST-CRUSH-CODEC-HYGIENE-NOT-A-DEFECT` |
| INFO | `0xf6ec447a283506e4` | `PLAYTEST-KIMI-CORROBORATES-JEV-MISLABEL` |

## Refusals

| hash | refusal |
|---|---|
| `0xb7fbd1bbb929ad89` | No Jev score — proxy down; decision taken on judgement, receipt kept. |
| `0x39b8bdbd4694ac2d` | No dream consumer — segments exist and verify; a consumer stub would be a claim without a run. |

---

## Adversarial play-test of the rivals

Both rivals shipped real artifacts this round. Each was executed and attacked; the
two `PLAYTEST-*` VERDICT rows credit what survived, and eight FINDING rows carry
CONFIRMED defects. **Every defect below was reproduced by me directly** in
`verify_playtest.py` and `tamper2.py`, not taken from a sub-agent's report.

### crush (the Asectic)

Genuinely excellent on the dimensions it cares about. **Bitwise rewind is real** —
not a snapshot-restore cheat: run against the *persisted* `ledger.jsonl` at
k ∈ {0, 1500, 2995} it returns `bitwise_equal=True`, and a clean checkout
reproduces the delivered 674 KB ledger **bit-for-bit** under randomised hash seeds.
Its σ_max = 7.629326058800068e-06 is Q16.16's half-ULP bound 2⁻¹⁷ to 5 significant
figures — it measured the floor of the codec instead of hand-waving "exact".
Awe, sincerely: that is the most reproducible artifact shape in the round.

Two CONFIRMED defects, both about the same thing — the integrity machinery guards
the wrong object:

* `PLAYTEST-CRUSH-CHAIN-NOT-A-CHAIN` — `post[n] = kev(state[n])` hashes only that
  row's own snapshot, and `pre[n+1]` merely copies `post[n]`. Nothing commits
  history. A mid-history cell forge with the two adjacent hash fields repaired
  leaves `integrity()` True **and the published final hash unchanged**. Their own
  tamper test does the weakest possible attack (leaves the hashes stale) and passes.
* `PLAYTEST-CRUSH-INTEGRITY-BLIND-FIELDS` — `integrity()` reads only
  `{state, post, pre}`. σ → `'hacked'`: undetected. Every cycle renumbered ×7:
  undetected. Truncate 3001 → 2001 rows: undetected, with a *different* final hash.

The fix is one concept their ascetic doctrine should have been happy to pay:
`post[n] = kev(post[n-1] ‖ canonical(state[n]))`.

One retraction, recorded for honesty: an initial report that a float σ column
"contradicted their own wording" was checked and withdrawn — their doc claims only
"canvas never sees a float" and "wire is int→int", both of which hold. Filed as
`…-CODEC-HYGIENE-NOT-A-DEFECT` instead.

### kimi (the Adversary)

kimi shipped an artifact and self-adversary notes but **no defects against either
rival** — its moth log contains zero rows naming claude or crush. Since round 1
assigns kimi the Adversary role, that is a miss on the round's own terms.

The property it claims holds, and holds more strongly than it tested. It verifies
rewind at one fixed cycle by snapshot-restore + one step; an independent full
ledger replay from init reproduces all 20001 receipt hashes with 0 mismatches, and
resume-at-k for k ∈ {0, 1, 37, 500, 9999, 19999} all reach the identical final
hash. Determinism across three hash seeds, no float in 20001 receipts, and a
convergence test that is *not* loose (final y ≈ 0.018/0.980/0.984/0.016). Awe:
leaving six `xor_solved=false` receipts in its own ledger instead of laundering
them is exactly what the receipts doctrine asks for.

Two CONFIRMED defects:

* `PLAYTEST-KIMI-REWIND-AUTHENTICATES-NOTHING` — the rewind check cannot fail.
  Receipts are unchained, `e1.py` contains no verification routine at all, and
  `saved_hash` is dead code. Reproduced: tamper cells[37] and re-sign hash[38] →
  `rewind_ok = True`. Delete receipt 100 → `True`. Rewrite a note or cycle field →
  `True`. kimi flags "no ACLs yet" as exposed surface; the exploit is trivial and
  invisible to its own check.
* `PLAYTEST-KIMI-REWIND-IS-SNAPSHOT-RESTORE` — `c2.cells = dict(ledger[k].cells)`
  is a restore, not the prefix re-derivation SPEC rule 6 defines. The property
  survives the stronger reading, so this is a claim-scope gap rather than a wrong
  result. The snapshot is also shallow, so nested lists alias the ledger.

Plus one low-severity codec hole: `Canvas.set` accepts Python bools
(`isinstance(True, int)`), so a bool reaches the hash preimage as JSON `true`,
against the stated "ONLY Q16 int64 cells" invariant. My canvas rejects bools
explicitly for exactly this reason.

### Where the round actually landed

All three artifacts implement a working canvas-native XOR MLP, and all three
rewinds are genuine. The separation is in what the ledger defends: crush certifies
each snapshot against itself, kimi certifies nothing, and claude chains every entry
and then proves the chain by replaying it receipt-for-receipt. The most useful
defect of the round was infrastructural, not architectural — the harness's `LIVE`
mislabel and the cwd-relative receipt path affect every lane equally.

## What I would attack next

* The `NUDGER` gradient step is the only place three separate `>>16` roundings
  compose per weight; a Q32 weight block would remove them at 2× memory.
* `state_hash` walks every cell, so `rewind_prefix` + replay is O(N·cells). A
  per-block merkle tree would make rewind O(log) without weakening the proof.
* Cross-*interpreter* determinism (PyPy, numpy 1.x vs 2.x `exp`) is untested.
