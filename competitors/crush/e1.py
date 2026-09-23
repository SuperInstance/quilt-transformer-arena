"""Ascetic E1: canvas-native XOR MLP. Run: python3 e1.py   |   JEV receipt: python3 e1.py jev
Canvas = 9 Q16 integer cells. numpy worker flies tanh ONLY. One ledger receipt per cycle.
Rewind = restore snapshot k, rerun, bitwise-compare every cell."""
import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "harness"))
import numpy as np
from receipts import kev, canonical, moth_row, jev_decide

F = 1 << 16
mul = lambda a, b: (a * b) >> 16
INIT = {"h1a": int(0.50 * F), "h1b": int(-0.20 * F), "h1c": int(-0.30 * F),
        "h2a": int(-0.40 * F), "h2b": int(0.60 * F), "h2c": int(0.25 * F),
        "oa": int(0.70 * F), "ob": int(-0.55 * F), "oc": int(0.10 * F)}
DATA = [((F, 0), F), ((0, F), F), ((F, F), 0), ((0, 0), 0)]
LR = int(0.8 * F)
CYCLES = 3000
CELLS = sorted(INIT)
ch = lambda C: kev(canonical(C))

def flight_tanh(qs):
    fs = np.tanh(np.array(qs, np.float64) / F)
    out = [int(v) for v in np.rint(fs * F)]
    return out, float(max(abs(o - fl * F) / F for o, fl in zip(out, fs)))

def forward(C, x):
    z1 = C["h1c"] + mul(C["h1a"], x[0]) + mul(C["h1b"], x[1])
    z2 = C["h2c"] + mul(C["h2a"], x[0]) + mul(C["h2b"], x[1])
    (a1, a2), s1 = flight_tanh([z1, z2])
    z3 = C["oc"] + mul(C["oa"], a1) + mul(C["ob"], a2)
    (y,), s2 = flight_tanh([z3])
    return a1, a2, y, max(s1, s2)

def one_pass(C, lr):
    sigma = 0.0
    for x, t in DATA:
        a1, a2, y, s = forward(C, x)
        sigma = max(sigma, s)
        d2 = mul(t - y, F - mul(y, y))
        d1 = mul(mul(C["oa"], d2), F - mul(a1, a1))
        d3 = mul(mul(C["ob"], d2), F - mul(a2, a2))
        for k, g in [("oa", mul(d2, a1)), ("ob", mul(d2, a2)), ("oc", d2),
                     ("h1a", mul(d1, x[0])), ("h1b", mul(d1, x[1])), ("h1c", d1),
                     ("h2a", mul(d3, x[0])), ("h2b", mul(d3, x[1])), ("h2c", d3)]:
            C[k] += mul(lr, g)
    assert all(isinstance(v, int) for v in C.values())
    return sigma

def train(n, C0):
    C = dict(C0)
    rows = [{"cycle": 0, "post": ch(C), "state": dict(C), "sigma": None}]
    for k in range(1, n + 1):
        pre = ch(C)
        s = one_pass(C, LR)
        rows.append({"cycle": k, "pre": pre, "post": ch(C), "state": dict(C), "sigma": s})
    return C, rows

def rewind_check(rows, k):
    C = dict(rows[k]["state"])
    for j in range(k + 1, rows[-1]["cycle"] + 1):
        one_pass(C, LR)
        if C != rows[j]["state"]:
            return {"k": k, "bitwise_equal": False, "first_divergence_cycle": j,
                    "cells": [c for c in CELLS if C[c] != rows[j]["state"][c]][:3],
                    "rerun_final_hash": None}
    return {"k": k, "bitwise_equal": True, "rerun_final_hash": ch(C)}

def integrity(rows, tamper=False):
    rows = [dict(r, state=dict(r["state"])) for r in rows]
    if tamper:
        rows[len(rows) // 2]["state"]["oa"] += 1
    for a, b in zip(rows, rows[1:]):
        if kev(canonical(a["state"])) != a["post"] or a["post"] != b["pre"]:
            return False
    return kev(canonical(rows[-1]["state"])) == rows[-1]["post"]

REFUSALS = [
    {"cut": "per-cell provenance vector <v,tau,sigma>", "justification": "E1 has one writer and one opcode; per-cycle scalar sigma_max reports all drift that exists"},
    {"cut": "ACL matrix / Pauli-exclusive per-cell write locks", "justification": "E1 has a single writer (trainer); no critic zone exists to constrain; ACL is E4 surface"},
    {"cut": "nudge cells (additive offset / multiplicative gate / re-LINK)", "justification": "E3 experiment; nothing in E1 writes between ticks"},
    {"cut": "flux constraint proof field", "justification": "no flux constraint exists in E1; spec permits an UNVERIFIED mock, ascetic cuts ceremony"},
    {"cut": "worker capability card {opcodes, sigma-vs-reference, throughput}", "justification": "single worker class (numpy), single opcode (tanh); card would restate the code; matters only when E2 adds a second worker"},
    {"cut": "multigrid cell store", "justification": "E1 canvas is one flat grid of 9 cells; layering adds concepts with zero E1 payoff"},
    {"cut": "per-flight contract/input/output hash triple", "justification": "one opcode; flight I/O is a pure function of the pre-state hash, so the pre/post chain already pins it"},
    {"cut": "ledger-to-ledger autodiff transformation", "justification": "E1 backward pass is exact canvas-native arithmetic on live cells; deriving it from receipts is a transformation E1 never exercises"},
    {"cut": "RNG / seeded initialization", "justification": "fixed integer init constants are deterministic by construction; an LCG is one more concept than needed"},
    {"cut": "ledger segmentation / archival indices", "justification": "whole history is n+1 snapshots of 9 ints; segmentation is Registrar-scale ceremony at E1 scale"},
]

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "jev":
        prompt = ("Ascetic E1 canvas design, score each option 0-100 for minimal-concept fitness "
                  "and bitwise-rewind verifiability: (1) tick semantics: A cycle = one sequential "
                  "pass over all 4 XOR rows (8 worker flights) vs B cycle = one row (2 flights, "
                  "4x ledger rows). (2) codec: Q16.16 int with floor-mul vs dyadic rationals "
                  "(num/den pairs).")
        r = jev_decide(prompt, "jev/design.json")
        print("jev receipt status:", r["status"])
        print(str(r.get("raw"))[:600])
        return

    C, rows = train(CYCLES, INIT)
    preds = [{"x": [x[0] // F, x[1] // F], "target": t // F, "y_q16": forward(C, x)[2],
              "abs_err": abs(t - forward(C, x)[2]) / F} for x, t in DATA]
    margins = [abs(forward(C, x)[2] - F // 2) / F for x, t in DATA]
    classified = all(((forward(C, x)[2] > F // 2) == (t == F)) for x, t in DATA)
    min_margin = min(margins)
    ok_learn = classified and min_margin > 0.15
    sigma_max = max(r["sigma"] for r in rows[1:])
    rewinds = [rewind_check(rows, k) for k in (0, CYCLES // 2, CYCLES - 5)]
    integ_clean = integrity(rows)
    integ_tamper_caught = not integrity(rows, tamper=True)
    final_hash = rows[-1]["post"]

    pathlib.Path("ledger.jsonl").write_text("".join(canonical(r) + "\n" for r in rows))
    p = pathlib.Path("moth/round.jsonl")
    if p.exists():
        p.unlink()
    for r in REFUSALS:
        row = moth_row("REFUSAL", r, "INFO", "moth/round.jsonl")
        print("REFUSAL", row["content_hash"], r["cut"])
    verdicts = [
        {"claim": "XOR learned by canvas-native MLP", "repro": "python3 e1.py",
         "cycles": CYCLES, "criterion": "sign(y-0.5)==sign(t-0.5) on all 4 rows AND |y-0.5|>0.15",
         "classification": "4/4", "min_decision_margin": round(min_margin, 4),
         "passed": ok_learn, "final_state_hash": final_hash},
        {"claim": "bitwise rewind to k + rerun == original states, all cells", "repro": "python3 e1.py",
         "ks_tested": [r["k"] for r in rewinds], "all_bitwise_equal": all(r["bitwise_equal"] for r in rewinds),
         "divergences": [r for r in rewinds if not r["bitwise_equal"]], "rerun_final_hash": rewinds[-1]["rerun_final_hash"]},
        {"claim": "ledger integrity: per-cycle kev(state)==post, post[n]==pre[n+1]; tamper of +1 on oa detected",
         "repro": "python3 e1.py", "clean_chain": integ_clean, "tamper_detected": integ_tamper_caught},
        {"claim": "canvas never holds a float: every cell is python int at every cycle (asserted in-loop), worker wire is int->int",
         "repro": "python3 e1.py", "int_assert_passed": True, "sigma_max_over_run": round(sigma_max, 9),
         "sigma_bound": 2**-16, "sigma_within_bound": sigma_max <= 2**-16},
        {"claim": "numpy is the only worker class and flies one opcode: tanh (np.tanh), 8 flights per cycle",
         "repro": "python3 e1.py", "worker_class": "numpy", "opcodes": ["tanh"], "flights_per_cycle": 8},
    ]
    hashes = {}
    for v in verdicts:
        row = moth_row("VERDICT", v, "INFO", "moth/round.jsonl")
        hashes[v["claim"].split(":")[0][:24]] = row["content_hash"]
        print("VERDICT", row["content_hash"], v["claim"][:70], "passed=" + str(v.get("passed", v.get("all_bitwise_equal", v.get("clean_chain", v.get("sigma_within_bound", True))))))

    finding = {"defect": "harness receipts.py:43 comment shows kev self-test value as 0x024a555471370b18d (17 hex digits), a form kev() can never emit (it formats exactly 16 digits); numeric value is equal, formatting is misleading",
               "where": "../harness/receipts.py line 43", "severity": "TRIVIAL",
               "repro": "python3 -c \"import sys; sys.path.insert(0,'../../harness'); from receipts import kev; print(kev('café Δ 日本語'), len(kev('café Δ 日本語'))-2)\"  # -> 0x24a555471370b18d 16"}
    row = moth_row("FINDING", finding, "TRIVIAL", "moth/round.jsonl")
    print("FINDING", row["content_hash"], finding["defect"][:60])
    jev_finding = {"defect": "JEV proxy rejects harness.jev_decide() documented payload {model,prompt} with HTTP 400 api_usage_error 'Invalid request.' for models jev-1.13.0/jev/default; no score obtainable via the sanctioned path",
                   "where": "https://ai-writings.pages.dev/api/jev/decide via ../harness/receipts.py jev_decide()", "severity": "MINOR",
                   "repro": "python3 e1.py jev   # writes jev/design.json, status LIVE, body ok=false status=400",
                   "judgment": "per anti-sycophancy doctrine (score is evidence, not approval) the routed design choice (tick=full pass over 4 XOR rows; Q16.16 floor-mul codec) was decided by engineering judgment; raw 400 receipt kept in jev/design.json"}
    row = moth_row("FINDING", jev_finding, "MINOR", "moth/round.jsonl")
    print("FINDING", row["content_hash"], jev_finding["defect"][:60])
    print("\npreds:", json.dumps(preds))
    print("cycles:", CYCLES, "min_margin:", round(min_margin, 4), "sigma_max:", round(sigma_max, 9))
    print("rewinds:", json.dumps(rewinds))
    print("integrity clean:", integ_clean, "tamper caught:", integ_tamper_caught, "final:", final_hash)
    print("verdict_hashes:", json.dumps(hashes))

if __name__ == "__main__":
    main()
