"""run_e1.py — Experiment E1 driver for the Registrar artifact.

Runs the canvas-native XOR MLP, then verifies every claim the artifact makes by
execution, appending one MOTH row per claim to moth/round.jsonl.

  python3 run_e1.py                 # run everything, receipt all claims
  python3 run_e1.py --only REWIND   # reproduce a single claim
  python3 run_e1.py --statehash     # print a state hash (used by the hashseed test)
  python3 run_e1.py --cycles N      # override training length
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, "/tmp/lane-quiltformer/arena/harness")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import receipt_findings as _RF  # noqa: E402
import quilt as Q  # noqa: E402
from receipts import canonical, kev, moth_row  # noqa: E402

MOTH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "moth", "round.jsonl")
CYCLES = 300
LR = Q.SCALE  # learning rate 1.0 in Q16.16; converges by ~cycle 100


# --------------------------------------------------------------------------
# claims — each returns (ok: bool, detail: dict).  Every one is executable.
# --------------------------------------------------------------------------

def float_scan_json(o, path="$"):
    """Structural scan: report every float anywhere in a ledger's payload."""
    if isinstance(o, bool):
        return []
    if isinstance(o, float):
        return [f"{path}={o!r}"]
    if isinstance(o, dict):
        return [f for k, v in o.items() for f in float_scan_json(v, f"{path}.{k}")]
    if isinstance(o, (list, tuple)):
        return [f for i, v in enumerate(o) for f in float_scan_json(v, f"{path}[{i}]")]
    return []


def claim_codec() -> tuple[bool, dict]:
    """No float ever reaches the canvas or the ledger, and the canvas refuses one."""
    cv, led, eng, w = Q.train(CYCLES, LR)
    leaked = cv.float_scan()
    refused = []
    for bad in (0.5, True, 3.7):
        try:
            cv.write("NUDGER", "W", "w0[0]", bad, "weight", Q.SIGMA_EXACT)
        except Q.CodecError:
            refused.append(repr(bad))
    led_floats = float_scan_json(led.entries)
    return (not leaked and len(refused) == 3 and not led_floats,
            {"float_cells_in_canvas": leaked, "rejected_writes": refused,
             "floats_in_ledger": led_floats,
             "cells_scanned": sum(len(c) for c in cv.blocks.values()),
             "ledger_entries_scanned": len(led.entries)})


def claim_converge() -> tuple[bool, dict]:
    """The canvas-native MLP solves XOR, and the ledger carries one receipt/cycle."""
    cv, led, eng, w = Q.train(CYCLES, LR)
    pred = [1 if cv.read("AUDITOR", "Y", f"y{c}") > Q.SCALE // 2 else 0
            for c in range(4)]
    outs = [cv.read("AUDITOR", "Y", f"y{c}") / Q.SCALE for c in range(4)]
    flights = [e for e in led.entries if e["kind"] == Q.FLIGHT]
    first = None
    for c in range(CYCLES):
        cvo, _, _, _ = Q.train(c + 1, LR)
        p = [1 if cvo.read("AUDITOR", "Y", f"y{i}") > Q.SCALE // 2 else 0 for i in range(4)]
        if p == [0, 1, 1, 0]:
            first = c + 1
            break
    return (pred == [0, 1, 1, 0] and len(flights) == CYCLES,
            {"prediction": pred, "target": [0, 1, 1, 0],
             "outputs_q16_to_float": [round(o, 6) for o in outs],
             "loss_q16": Q.Engine.loss(cv),
             "flights": len(flights), "receipts_per_cycle": 1,
             "first_solving_cycle": first})


def claim_rewind() -> tuple[bool, dict]:
    """Bitwise rewind to cycle k, verified by replaying the retained prefix.

    Three checks per k, all strict:
      a) replaying the prefix re-derives the state hash the original flight recorded
      b) re-running the discarded suffix lands on the original final state hash
      c) every re-derived receipt body is bitwise identical to the original
    """
    cv, led, eng, w = Q.train(CYCLES, LR)
    orig_bodies = [e["body"] for e in led.entries if e["kind"] == Q.FLIGHT]
    final_hash = cv.state_hash()
    results = []
    for k in (0, 1, 7, 75, 150, CYCLES - 1):
        fresh = copy.deepcopy(led)
        cv_k, checkpoint, bodies_k = Q.rewind_and_rerun(fresh, k, CYCLES, LR)
        a = checkpoint == orig_bodies[k]["state_hash"]
        b = cv_k.state_hash() == final_hash
        c = bodies_k == orig_bodies
        results.append({"k": k, "prefix_hash_matches_checkpoint": a,
                        "rerun_hash_matches_final": b,
                        "receipts_bitwise_identical": c,
                        "replay_body_hash": kev(canonical(bodies_k)),
                        "orig_body_hash": kev(canonical(orig_bodies)),
                        "checkpoint_hash": checkpoint})
    ok = all(r["prefix_hash_matches_checkpoint"] and r["rerun_hash_matches_final"]
             and r["receipts_bitwise_identical"] for r in results)
    return ok, {"ks_tested": [r["k"] for r in results], "results": results,
                "final_state_hash": final_hash}


def claim_chain() -> tuple[bool, dict]:
    """Tampering with any ledger entry is detected by the hash chain."""
    cv, led, eng, w = Q.train(20, LR)
    base = led.verify_chain()
    detected = []
    for mutate in ("body", "kind", "seq"):
        tam = copy.deepcopy(led)
        e = tam.entries[7]
        if mutate == "body":
            e["body"]["loss_q16"] += 1
        elif mutate == "kind":
            e["kind"] = Q.NUDGE
        else:
            e["seq"] = 99
        detected.append(not tam.verify_chain())
    # a forged entry appended with a stale prev_hash must also fail
    forged = copy.deepcopy(led)
    forged.append(Q.NUDGE, {"cycle": 99, "offsets": {"W.w0[0]": 1}})
    forged.entries[8]["prev_hash"] = "0x" + "f" * 16
    return (base and all(detected) and not forged.verify_chain(),
            {"chain_ok_before": base, "tamper_kinds": ["body", "kind", "seq"],
             "tamper_detected": detected, "forged_prev_hash_detected":
                 not forged.verify_chain()})


def claim_acl() -> tuple[bool, dict]:
    """The ACL matrix is enforced, not decorative."""
    cv = Q.Canvas()
    Q.Engine(Q.SCALE).genesis(cv, "acl/test")
    attempts = [
        ("CRITIC", "RW", "W", "w0[0]"), ("CRITIC", "RW", "W2", "v[0]"),
        ("WORKER", "RW", "W", "w0[0]"), ("WORKER", "RW", "C", "k"),
        ("AUDITOR", "RW", "T", "x0.0"), ("GHOST", "R", "W", "w0[0]"),
        ("NUDGER", "RW", "H", "a0[0]"),
    ]
    blocked = []
    for role, mode, block, key in attempts:
        try:
            cv._acl(role, block, mode.lower())
            blocked.append(False)
        except Q.ACLError:
            blocked.append(True)
    # the one write the critic IS granted, is granted
    try:
        cv.write("CRITIC", "C", "zone", 1, "constraint", Q.SIGMA_EXACT)
        critic_ok = True
    except Q.ACLError:
        critic_ok = False
    # worker CAN write its declared surfaces
    cv.set_tick(999)
    cv.write("WORKER", "H", "probe", 7, "activation", Q.SIGMA_EXACT)
    worker_ok = cv.blocks["H"]["probe"].v == 7
    return (all(blocked) and critic_ok and worker_ok,
            {"denied_attempts": [f"{r}:{m}:{b}" for (r, m, b, k), d
                                 in zip(attempts, blocked) if d],
             "critic_constraint_write_granted": critic_ok,
             "worker_declared_write_granted": worker_ok,
             "acl_hash": kev(Q.ACL)})


def claim_pauli() -> tuple[bool, dict]:
    """One writer role per cell per tick; a second distinct writer is refused.

    Uses block C, which both CRITIC and NUDGER may write, so the refusal is
    attributable to Pauli-exclusivity and not to the ACL matrix.
    """
    cv = Q.Canvas()
    Q.Engine(Q.SCALE).genesis(cv, "pauli/test")
    cv.set_tick(5)
    cv.write("CRITIC", "C", "shared", 1, "constraint", Q.SIGMA_EXACT)
    try:
        cv.write("NUDGER", "C", "shared", 2, "constraint", Q.SIGMA_EXACT)
        violated = False
    except Q.ACLError:
        violated = True
    # the SAME role may rewrite its own cell in the same tick
    cv.write("CRITIC", "C", "shared", 3, "constraint", Q.SIGMA_EXACT)
    # a different tick lifts the exclusion
    cv.set_tick(6)
    cv.write("NUDGER", "C", "shared", 4, "constraint", Q.SIGMA_EXACT)
    return (violated and cv.read("AUDITOR", "C", "shared") == 4,
            {"cross_role_write_refused": violated,
             "same_role_rewrite_ok": True,
             "next_tick_write_ok": True})


def claim_pins() -> tuple[bool, dict]:
    """A flight's input pins detect any mutation of the pinned cells."""
    cv, led, eng, w = Q.train(3, LR)
    pins = Q.pin(cv, ["W.w0[0]", "W2.v[1]", "B2.c"])
    good = Q.check_pins(cv, pins) is None
    stale = []
    for mut in ("W.w0[0]", "W2.v[1]"):
        c = copy.deepcopy(cv)
        c.blocks[mut.split(".")[0]][mut.split(".")[1]].v += 1
        try:
            Q.check_pins(c, pins)
            stale.append(False)
        except Q.StalePin:
            stale.append(True)
    return (good and all(stale),
            {"pinned_cells": sorted(pins), "intact_pins_accepted": good,
             "mutated_pins_rejected": stale})


def claim_segments() -> tuple[bool, dict]:
    """Ledger prefixes seal into dream-ready segments; a sealed entry cannot move."""
    cv, led, eng, w = Q.train(30, LR)
    led.seal_segment("segment-a/first-10-cycles")
    led2 = copy.deepcopy(led)
    for c in range(30, 45):
        led2.append(Q.FLIGHT, eng.cycle(cv, c, w))
    led2.seal_segment("segment-b/next-15-cycles")
    ok = all(led2.verify_segments())
    tam = copy.deepcopy(led2)
    tam.entries[5]["body"]["loss_q16"] += 1
    chain_detects = not tam.verify_chain()
    sealed_roots = [e["body"] for e in led2.entries if e["kind"] == Q.SEGMENT_SEAL]
    return (ok and chain_detects and len(sealed_roots) == 2,
            {"segments": sealed_roots, "segment_roots_verified": ok,
             "sealed_tamper_detected_by_chain": chain_detects})


def claim_margin() -> tuple[bool, dict]:
    """Worker quantisation is not knife-edge: report the rounding-boundary margin."""
    cv, led, eng, w = Q.train(50, LR)
    flights = [e["body"] for e in led.entries if e["kind"] == Q.FLIGHT]
    margins = [f["boundary_margin_q16"] for f in flights]
    # an independent worst case: sweep the whole sigmoid argument range
    zs = list(range(-Q.SCALE, Q.SCALE + 1, Q.SCALE // 256))
    worst = min(Q._margins(w, zs))
    return (min(margins) > 0 and worst > 0,
            {"min_flight_margin_q16": min(margins),
             "mean_flight_margin_q16": sum(margins) // len(margins),
             "worst_margin_over_sweep_q16": worst,
             "note": "margin > 0 means a small libm/float perturbation cannot "
                     "flip the quantised worker output"})


def claim_gradient() -> tuple[bool, dict]:
    """Canvas Q16 gradients agree with an independent float64 path."""
    import numpy as np
    cv0 = Q.Canvas()
    Q.Engine(Q.SCALE).genesis(cv0, "registrar/e1/xor/v1")
    cv, led, eng, w = Q.train(1, Q.SCALE)   # step == -grad exactly
    def bef(b, k): return cv0.read("AUDITOR", b, k) / Q.SCALE
    def canvg(b, k): return -(cv.read("AUDITOR", b, k) - cv0.read("AUDITOR", b, k)) / Q.SCALE
    W = np.array([[bef("W", f"w{k}[{j}]") for j in Q.HID] for k in (0, 1)])
    B = np.array([bef("B", f"b[{j}]") for j in Q.HID])
    V = np.array([bef("W2", f"v[{j}]") for j in Q.HID])
    C = np.array([bef("B2", "c")])
    X = np.array([[0., 0.], [0., 1.], [1., 0.], [1., 1.]])
    T = np.array([0., 1., 1., 0.])
    A = 1 / (1 + np.exp(-(X @ W + B)))
    Y = 1 / (1 + np.exp(-(A @ V + C)))
    dy = Y - T
    da = dy[:, None] @ V[None, :]
    dh = da * A * (1 - A)
    errs = []
    errs += [abs(canvg("W", f"w{k}[{j}]") - (X.T @ dh)[k, j])
             for k in (0, 1) for j in Q.HID]
    errs += [abs(canvg("W2", f"v[{j}]") - (A.T @ dy)[j]) for j in Q.HID]
    errs += [abs(canvg("B", f"b[{j}]") - dh.sum(0)[j]) for j in Q.HID]
    errs += [abs(canvg("B2", "c") - dy.sum())]
    yerr = max(abs(cv.read("AUDITOR", "Y", f"y{c}") / Q.SCALE - Y[c]) for c in range(4))
    return (max(errs) < 1e-3 and yerr < 1e-4,
            {"max_abs_gradient_error": round(max(errs), 9),
             "max_abs_forward_output_error": round(float(yerr), 9),
             "threshold": "1e-3 gradient, 1e-4 forward",
             "reference": "independent float64 numpy path on identical params"})


def claim_hashseed() -> tuple[bool, dict]:
    """Replay must not depend on PYTHONHASHSEED (no unsorted string iteration)."""
    here = os.path.dirname(os.path.abspath(__file__))
    hashes = []
    for seed in ("0", "1", "random", "random"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        r = subprocess.run([sys.executable, os.path.join(here, "run_e1.py"),
                            "--statehash"], capture_output=True, text=True,
                           env=env, cwd=here)
        if r.returncode != 0:
            return False, {"error": r.stderr[-400:], "seed": seed}
        hashes.append(r.stdout.strip().splitlines()[-1])
    return (len(set(hashes)) == 1, {"hashes": hashes,
                                    "all_equal": len(set(hashes)) == 1})


def claim_ownership() -> tuple[bool, dict]:
    """Every row in this lane's moth ledger is authored by this artifact.

    Rival artifacts address their receipts with a cwd-relative path, so executing
    one from this directory silently appends its rows here — and if it rewrites
    the file it truncates rows already written.  The ledger is checked for
    authorship the same way any other ledger here is.
    """
    rows = [json.loads(l) for l in open(MOTH) if l.strip()]
    foreign = []
    for i, r in enumerate(rows):
        c = r.get("content", {})
        if c.get("lane") != "claude":
            foreign.append({"seq": i, "kind": r["kind"],
                            "content_hash": r["content_hash"],
                            "claim": c.get("claim", "?")[:60],
                            "recorded": r["recorded"]})
    return (not foreign, {"rows": len(rows), "foreign_rows": foreign,
                          "required_marker": "content.lane == 'claude'"})


def statehash_main() -> None:
    cv, led, eng, w = Q.train(CYCLES, LR)
    _, bodies = Q.replay(led.rewind_prefix(CYCLES - 1), LR)
    print(kev(canonical([cv.state_hash(), bodies[-1]])))


# --------------------------------------------------------------------------
# self-attack: where does bitwise rewind actually break?  (Registrar runs its
# own adversary pass so the theorem's boundary is stated, not implied.)
# --------------------------------------------------------------------------

def claim_selfattack() -> tuple[bool, dict]:
    """Three attacks on the bitwise-rewind theorem; each must be caught."""
    found = []

    # A1: a rogue write that never enters the ledger is invisible to replay, so
    # replaying re-derives a DIFFERENT state -> detected by state-hash mismatch.
    cv, led, eng, w = Q.train(10, LR)
    true_hash = cv.state_hash()
    cv.write("NUDGER", "W", "w0[0]", cv.read("NUDGER", "W", "w0[0]") + 1,
             "weight", Q.SIGMA_EXACT)          # out-of-ledger mutation
    _, replayed = Q.replay(led.entries, LR)
    found.append({"attack": "rogue_out_of_ledger_write",
                  "detected": replayed[-1]["state_hash"] != cv.state_hash(),
                  "original_hash": true_hash,
                  "replay_hash": replayed[-1]["state_hash"]})

    # A2: a nudge recorded after cycle k changes the replayed state, and rewinding
    # to k retracts it — the ledger prefix, not the canvas, is the source of truth.
    led2 = copy.deepcopy(led)
    led2.append(Q.NUDGE, {"cycle": 11, "offsets": {"W.w0[0]": Q.SCALE // 8},
                          "role": "NUDGER", "reason": "mid-run nudge"})
    cv_n, _ = Q.replay(led2.entries, LR)
    cv_b, _ = Q.replay(led.entries, LR)
    differs = cv_n.state_hash() != cv_b.state_hash()
    prefix = led2.rewind_prefix(10)
    cv_r, _ = Q.replay(prefix, LR)
    erased = cv_r.state_hash() == cv_b.state_hash()
    found.append({"attack": "rewind_retracts_nudge",
                  "nudge_changes_state": differs, "rewind_erases_nudge": erased,
                  "nudged_hash": cv_n.state_hash(),
                  "clean_hash": cv_b.state_hash()})

    # A3: a float smuggled into a cell is refused by the codec closure, so the
    # "float in the numpy path" cannot reach the state that rewind reproduces.
    try:
        cv_b.write("NUDGER", "W", "w0[0]", 0.5, "weight", Q.SIGMA_EXACT)
        a3 = False
    except Q.CodecError:
        a3 = True
    found.append({"attack": "float_smuggled_into_canvas", "detected": a3})

    ok = (found[0]["detected"] and found[1]["nudge_changes_state"]
          and found[1]["rewind_erases_nudge"] and found[2]["detected"])
    return ok, {"attacks": found,
                "scope": "bitwise determinism is claimed for a fixed python3+numpy "
                         "build; cross-build float64 exp() drift is measured by "
                         "MARGIN, not assumed away"}


CLAIMS = [
    ("CODEC", "no float reaches the canvas; codec closure enforced", claim_codec),
    ("CONVERGE", "canvas-native MLP solves XOR, one receipt per cycle", claim_converge),
    ("REWIND", "bitwise rewind to cycle k verified by replay + rerun", claim_rewind),
    ("CHAIN", "ledger hash chain detects tampering", claim_chain),
    ("ACL", "role x block ACL matrix enforced", claim_acl),
    ("PAULI", "one writer role per cell per tick", claim_pauli),
    ("PINS", "flight input pins detect cell mutation", claim_pins),
    ("SEGMENTS", "dream-ready segment seals verify", claim_segments),
    ("MARGIN", "worker quantisation is not knife-edge", claim_margin),
    ("GRADIENT", "canvas Q16 gradients match a float64 reference", claim_gradient),
    ("HASHSEED", "replay is PYTHONHASHSEED-independent", claim_hashseed),
    ("SELFATTACK", "three attacks on the rewind theorem are caught", claim_selfattack),
    ("OWNERSHIP", "every row in this lane's moth ledger is authored here", claim_ownership),
]


def _jsonable(o):
    """Coerce numpy scalars so a receipt is always canonical-JSON serialisable."""
    import numpy as _np
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, _np.bool_):
        return bool(o)
    if isinstance(o, _np.integer):
        return int(o)
    if isinstance(o, _np.floating):
        return float(o)
    return o


def main(argv: list[str]) -> int:
    if "--statehash" in argv:
        statehash_main()
        return 0
    only = None
    if "--only" in argv:
        only = argv[argv.index("--only") + 1].upper()
    global CYCLES
    if "--cycles" in argv:
        CYCLES = int(argv[argv.index("--cycles") + 1])

    all_ok = True
    for name, statement, fn in CLAIMS:
        if only and name != only:
            continue
        t0 = time.time()
        try:
            ok, detail = fn()
            err = None
        except Exception as e:  # a claim that cannot even run is a REFUSAL
            ok, detail, err = False, {}, repr(e)
        dt = time.time() - t0
        all_ok &= ok
        repro = f"python3 run_e1.py --only {name}"
        row = moth_row(
            "VERDICT" if ok else "FINDING",
            {"claim": name, "statement": statement, "verified": bool(ok),
             "detail": _jsonable(detail), "repro": repro,
             "artifact": "claude/quilt.py", "seconds": round(dt, 2),
             "lane": "claude"},
            severity="INFO" if ok else "HIGH", path=MOTH)
        print(f"{'PASS' if ok else 'FAIL'}  {name:10s} {dt:5.1f}s  "
              f"{row['content_hash']}  {statement}")
        if err:
            print(f"      raised: {err}")
    print("\nall claims verified:", all_ok)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
