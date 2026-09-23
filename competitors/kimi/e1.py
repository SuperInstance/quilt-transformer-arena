"""E1 — Adversary build. Canvas-native XOR MLP, numpy sole worker, Q16-exact canvas,
ledger receipt per cycle, bitwise rewind verified by rerunning. Build to break it."""
import json, pathlib, sys
sys.path.insert(0, "/tmp/lane-quiltformer/arena/harness")
from receipts import kev, canonical, moth_row, jev_decide
import numpy as np

FRAC = 16  # Q16: int64 with 16 fractional bits — canvas NEVER stores a float

def q16(v: float) -> int:  return int(round(v * (1 << FRAC)))
def f64(q: int) -> float:  return q / float(1 << FRAC)

class Canvas:
    """Archival canvas: cells -> Q16 ints only. Multigrid coords = flat names (E1)."""
    def __init__(self): self.cells = {}; self.ledger = []
    def set(self, k, q):
        def ok(v): return isinstance(v, int) or (isinstance(v, list) and all(ok(i) for i in v))
        assert ok(q), f"FLOAT LEAK into {k}"; self.cells[k] = q
    def get(self, k): return self.cells[k]
    def snapshot(self): return dict(self.cells)
    def receipt(self, cycle, note=""):
        r = {"cycle": cycle, "note": note, "state_hash": kev(canonical(self.cells)),
             "cells": dict(self.cells)}  # E1: full-value ledger (deltas+dreams are later rounds)
        self.ledger.append(r); return r

def sigmoid(z):  return 1.0 / (1.0 + np.exp(-z))          # transcendental → WORKER visit
def dsig(a):     return a * (1.0 - a)                      # via activated value

def worker_forward(x_q, p):  # numpy worker: imports Q16, exports Q16 + sigma
    x = f64(np.array(x_q, dtype=np.float64))
    W1 = f64(np.array(p["W1"], dtype=np.float64)).reshape(2, 2)
    b1 = f64(np.array(p["b1"], dtype=np.float64))
    W2 = f64(np.array(p["W2"], dtype=np.float64))
    b2 = f64(p["b2"])
    z1 = W1 @ x + b1;  a1 = sigmoid(z1)
    z2 = W2 @ a1 + b2; a2 = sigmoid(z2)
    outs = {"h": [q16(v) for v in a1], "y": q16(a2)}
    sigma = {"h": float(np.max(np.abs(f64(np.array(outs["h"])) - a1))),
             "y": float(abs(f64(outs["y"]) - a2))}          # measured quantization drift
    return outs, sigma

def worker_grads(x_q, t_q, p, fwd):
    x = f64(np.array(x_q, dtype=np.float64)); t = f64(t_q)
    W1 = f64(np.array(p["W1"], dtype=np.float64)).reshape(2, 2)
    W2 = f64(np.array(p["W2"], dtype=np.float64))
    a1 = f64(np.array(fwd["h"], dtype=np.float64)); a2 = f64(fwd["y"])
    dz2 = 2 * (a2 - t) * dsig(a2)
    dW2 = dz2 * a1; db2 = dz2
    dz1 = (W2 * dz2) * dsig(a1)
    dW1 = np.outer(dz1, x); db1 = dz1
    return {k: [q16(v) for v in np.ravel(g)] if hasattr(g, "__len__") else q16(g)
            for k, g in (("W2", dW2), ("b2", db2), ("W1", dW1), ("b1", db1))}, {}

def sgd(canvas, grads, lr_q):  # canvas-native: integer update, exact, no worker visit
    for k in ("W1", "b1", "W2", "b2"):
        cur = canvas.get(k); g = grads[k]
        g = g if isinstance(g, list) else [g]
        cur = cur if isinstance(cur, list) else [cur]
        flat = [cur[i] - ((lr_q * g[i]) >> FRAC) for i in range(len(g))]
        canvas.set(k, flat) if len(flat) > 1 else canvas.set(k, flat[0])

def run(cycles=20000, lr=0.5, seed_weights=None, rewind_to=37):
    c = Canvas()
    init = seed_weights or {"W1": [q16(0.5), q16(-0.3), q16(0.2), q16(0.8)],
                            "b1": [q16(0.0), q16(0.0)], "W2": [q16(0.4), q16(-0.6)], "b2": q16(0.1)}
    for k, v in init.items(): c.set(k, v)
    data = [([0, 0], 0), ([0, 1], 1), ([1, 0], 1), ([1, 1], 0)]
    c.receipt(0, "init")
    sigmas = []
    for k in range(1, cycles + 1):
        x, t = data[k % 4]
        xq = [q16(v) for v in x]
        fwd, s = worker_forward(xq, c.cells); sigmas.append(max(s["h"], s["y"]))
        for name, v in (("h", fwd["h"]), ("y", fwd["y"])): c.set(name, v)
        grads, _ = worker_grads(xq, q16(t), c.cells, fwd)
        sgd(c, grads, q16(lr))
        c.receipt(k, "train")
    # rewind: restore cycle `rewind_to`, rerun one step, bitwise compare
    snap = c.ledger[rewind_to]["cells"]
    saved_hash = c.ledger[rewind_to]["state_hash"]
    c2 = Canvas(); c2.cells = dict(snap)
    x, t = data[(rewind_to + 1) % 4]
    xq = [q16(v) for v in x]
    fwd2, _ = worker_forward(xq, c2.cells)
    for name, v in (("h", fwd2["h"]), ("y", fwd2["y"])): c2.set(name, v)
    grads2, _ = worker_grads(xq, q16(t), c2.cells, fwd2)
    sgd(c2, grads2, q16(lr))
    rerun_hash = kev(canonical(c2.cells))
    actual_next = c.ledger[rewind_to + 1]["state_hash"]
    ok = rerun_hash == actual_next
    # convergence check
    preds = [round(f64(worker_forward([q16(v) for v in x], c.cells)[0]["y"])) for x, _ in data]
    acc = sum(p == t for p, (_, t) in zip(preds, data))
    return {"rewind_bitwise": ok, "rewind_to": rewind_to, "xor_solved": acc == 4,
            "preds": preds, "max_sigma": max(sigmas), "final_y_q16": c.get("y")}

if __name__ == "__main__":
    res = run()
    print(canonical(res))
    out = pathlib.Path("/tmp/lane-quiltformer/arena/competitors/kimi")
    out.mkdir(parents=True, exist_ok=True)
    v1 = moth_row("VERDICT", {"claim": "bitwise rewind to cycle 37 reproduces cycle 38 state_hash",
                   "repro": "python3 e1.py | check rewind_bitwise==true", "result": res["rewind_bitwise"]},
                  severity="CRITICAL", path=str(out / "moth/round.jsonl"))
    v2 = moth_row("VERDICT", {"claim": "XOR learned (4/4) with Q16 canvas + float worker boundary",
                   "repro": "python3 e1.py | check xor_solved==true", "result": res["xor_solved"]},
                  severity="MAJOR", path=str(out / "moth/round.jsonl"))
    moth_row("FINDING", {"where": "worker boundary", "what": "float worker -> Q16 quantization sigma",
             "max_sigma_q16_units": res["max_sigma"], "note": "sigma measured per cycle, reported not hidden"},
             severity="INFO", path=str(out / "moth/round.jsonl"))
    jev_decide("E1 codec choice: Q16 fixed-point (int64, 16 frac bits) vs raw dyadic export for canvas cells — which bounds rewind determinism better for a float-numpy worker boundary?",
               str(out / "jev/design.json"))
    (out / "result.json").write_text(canonical(res))
    print("VERDICT hashes:", v1["content_hash"], v2["content_hash"])
