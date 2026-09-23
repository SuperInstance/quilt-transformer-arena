"""Adversarial probe of kimi's E1. Read-only on kimi's dir: imports e1 as a module,
never runs its __main__ (which would write into kimi/)."""
import importlib.util, json, time, copy, sys

KIMI = "/tmp/lane-quiltformer/arena/competitors/kimi/e1.py"
spec = importlib.util.spec_from_file_location("kimi_e1", KIMI)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# ---- spy: capture the Canvas objects run() creates, without touching kimi ----
created = []
_Orig = m.Canvas
class Spy(_Orig):
    def __init__(self):
        super().__init__()
        created.append(self)
m.Canvas = Spy

t0 = time.time()
res = m.run()
dt = time.time() - t0
train, c2 = created[0], created[1]
led = train.ledger
print("RUN TIME %.1fs for 20000 cycles" % dt)
print("RESULT:", json.dumps(res, sort_keys=True))
print("ledger entries:", len(led))
print("ledger[37].state_hash:", led[37]["state_hash"])
print("ledger[38].state_hash:", led[38]["state_hash"])
print("cycle fields ok:", all(r["cycle"] == i for i, r in enumerate(led)))
print("final cells:", json.dumps(m.canonical(train.cells)))
print("cells at 37:", json.dumps(m.canonical(led[37]["cells"])))
print("cells at 38:", json.dumps(m.canonical(led[38]["cells"])))

# ---- scan the whole ledger for ANY float (codec exactness) ----
def floats(o, path=""):
    if isinstance(o, float):
        yield path
    elif isinstance(o, dict):
        for k, v in o.items():
            yield from floats(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from floats(v, path + f"[{i}]")
leaks = []
for i, r in enumerate(led):
    for p in floats(r["cells"], f"ledger[{i}].cells"):
        leaks.append(p)
print("FLOATS IN LEDGER CELLS:", leaks[:5], "count=", len(leaks))
for p in floats(res, "result"): print("FLOAT IN RESULT:", p)

# ---- convergence margin: how close is y to 0/1 really? ----
data = [([0, 0], 0), ([0, 1], 1), ([1, 0], 1), ([1, 1], 0)]
print("\n--- convergence margin at final weights ---")
for x, t in data:
    outs, s = m.worker_forward([m.q16(v) for v in x], train.cells)
    y = m.f64(outs["y"])
    print(f"  input {x} target {t}  y={y:.6f}  rounded={round(y)}  margin={'OK' if abs(y-t)>0.4 else 'THIN'}")

# ---- tamper tests: does ANY ledger tampering get detected? ----
def rewind_check(ledger, rewind_to=37, lr=0.5):
    """Faithful copy of e1.run()'s rewind block."""
    snap = ledger[rewind_to]["cells"]
    saved_hash = ledger[rewind_to]["state_hash"]   # dead code in e1.py
    cc = _Orig(); cc.cells = dict(snap)
    x, t = data[(rewind_to + 1) % 4]
    xq = [m.q16(v) for v in x]
    fwd, _ = m.worker_forward(xq, cc.cells)
    for name, v in (("h", fwd["h"]), ("y", fwd["y"])): cc.set(name, v)
    grads, _ = m.worker_grads(xq, m.q16(t), cc.cells, fwd)
    m.sgd(cc, grads, m.q16(lr))
    return m.kev(m.canonical(cc.cells)) == ledger[rewind_to + 1]["state_hash"], saved_hash

base, sh = rewind_check(led)
print("\n--- TAMPER TESTS (baseline rewind_ok=%s) ---" % base)
# A: forge the snapshot's own state_hash (exactly what saved_hash SHOULD have caught)
L = copy.deepcopy(led); L[37]["state_hash"] = "0xdeadbeefdeadbeef"
print("A forged ledger[37].state_hash          -> rewind_ok =", rewind_check(L)[0], "(undetected)" )
# B: forge the *next* receipt hash so the check passes against tampered state
L = copy.deepcopy(led); L[37]["cells"]["W1"][0] = 999999; L[38]["state_hash"] = rewind_check(L)[0]
L2 = copy.deepcopy(L); ok, _ = rewind_check(L2)
print("B tamper cells[37] + re-sign hash[38]   -> rewind_ok =", ok, "(undetected)")
# C: delete a middle receipt (no chaining -> renumber and everything looks fine)
L = copy.deepcopy(led); del L[10]
for i, r in enumerate(L): r["cycle"] = i
ok, _ = rewind_check(L)
print("C delete receipt 10 + renumber cycles   -> rewind_ok =", ok)
# D: append a forged future receipt
L = copy.deepcopy(led)
L.append({"cycle": 20001, "note": "FORGED", "state_hash": "0x" + "0" * 16, "cells": L[-1]["cells"]})
ok, _ = rewind_check(L, rewind_to=37)
print("D append forged receipt 20001           -> rewind_ok =", ok, "(undetected)")
# E: swap two receipts' cells/hashes (reorder history)
L = copy.deepcopy(led); L[5]["cells"], L[6]["cells"] = L[6]["cells"], L[5]["cells"]
ok, _ = rewind_check(L)
print("E swap receipt 5<->6 cells              -> rewind_ok =", ok)

# ---- FLOAT LEAK guard probes ----
print("\n--- Canvas.set guard probes ---")
for label, val in [("python float", 0.5), ("nested float", [1, [2, 0.5]]),
                   ("bool", True), ("np.int64", __import__("numpy").int64(7)),
                   ("np.float64", __import__("numpy").float64(0.5))]:
    cc = _Orig()
    try:
        cc.set("k", val); print(f"  {label:14s} -> ACCEPTED  cells={cc.cells!r}")
    except AssertionError as e:
        print(f"  {label:14s} -> rejected ({e})")

# ---- aliasing: is the ledger deep-copied on rewind? ----
snap = led[37]["cells"]
print("\naliasing: rewind snapshot shares nested lists with ledger:",
      m.Canvas().cells if False else (snap["W1"] is led[37]["cells"]["W1"]))

# ---- dump for cross-process replay test ----
dump = {"ledger_hashes": [r["state_hash"] for r in led],
        "cells37": led[37]["cells"], "cells38": led[38]["cells"],
        "final_cells": train.cells, "res": res}
open("/tmp/lane-quiltformer/arena/competitors/claude/kimi_dump.json", "w").write(m.canonical(dump))
print("\ndumped to kimi_dump.json")
