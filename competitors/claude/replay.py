"""Replay / determinism / rewind-depth / init-robustness attacks on kimi E1. Read-only."""
import importlib.util, json, os, time

KIMI = "/tmp/lane-quiltformer/arena/competitors/kimi/e1.py"
spec = importlib.util.spec_from_file_location("kimi_e1", KIMI)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

data = [([0, 0], 0), ([0, 1], 1), ([1, 0], 1), ([1, 1], 0)]
INIT = {"W1": [m.q16(0.5), m.q16(-0.3), m.q16(0.2), m.q16(0.8)],
        "b1": [m.q16(0.0), m.q16(0.0)], "W2": [m.q16(0.4), m.q16(-0.6)], "b2": m.q16(0.1)}
def h(cells): return m.kev(m.canonical(cells))

created = []
_Orig = m.Canvas
class Spy(_Orig):
    def __init__(self):
        super().__init__(); created.append(self)
m.Canvas = Spy

t0 = time.time()
res = m.run()
train = created[0]
led = train.ledger
print("SEED:", os.environ.get("PYTHONHASHSEED", "<unset>"))
print("T run: %.1fs" % (time.time() - t0))
print("res:", json.dumps(res, sort_keys=True))
print("FINAL HASH:", h(train.cells))
print("hash[37]=%s hash[38]=%s hash[19999]=%s hash[20000]=%s" %
      (led[37]["state_hash"], led[38]["state_hash"], led[19999]["state_hash"], led[20000]["state_hash"]))

# 1. genuine replay from init
def replay(n, lr=0.5, init=None):
    c = _Orig()
    for k, v in (init or INIT).items(): c.set(k, v)
    hs = [h(c.cells)]
    for k in range(1, n + 1):
        x, t = data[k % 4]
        xq = [m.q16(v) for v in x]
        fwd, _ = m.worker_forward(xq, c.cells)
        for name, v in (("h", fwd["h"]), ("y", fwd["y"])): c.set(name, v)
        grads, _ = m.worker_grads(xq, m.q16(t), c.cells, fwd)
        m.sgd(c, grads, m.q16(lr))
        hs.append(h(c.cells))
    return hs, c.cells

hs45, _ = replay(45)
bad = [i for i in range(46) if hs45[i] != led[i]["state_hash"]]
print("REPLAY 0..45 vs ledger: mismatches =", len(bad), bad[:5])

hs_all, fin = replay(20000)
print("FULL REPLAY final == recorded:", h(fin) == h(train.cells), h(fin))

# 2. resume-from-ledger-snapshot at many k, run to 20000, compare final state
for k in (0, 1, 37, 500, 9999, 19999):
    c = _Orig(); c.cells = json.loads(json.dumps(led[k]["cells"]))
    for j in range(k + 1, 20001):
        x, t = data[j % 4]
        xq = [m.q16(v) for v in x]
        fwd, _ = m.worker_forward(xq, c.cells)
        for name, v in (("h", fwd["h"]), ("y", fwd["y"])): c.set(name, v)
        grads, _ = m.worker_grads(xq, m.q16(t), c.cells, fwd)
        m.sgd(c, grads, m.q16(j and 0.5))
    ok_step = (h(c.cells) == led[k + 1]["state_hash"])
    print("RESUME k=%-5d -> step k+1 match: %-5s | final-20000 match: %s" %
          (k, ok_step, h(c.cells) == h(train.cells)))

# 3. init robustness: is 'XOR is learned' init-specific?
print("--- init robustness (20000 cycles, lr 0.5) ---")
import numpy as _np
inits = {"zeros": {"W1": [0, 0, 0, 0], "b1": [0, 0], "W2": [0, 0], "b2": 0},
         "symmetric-rows": {"W1": [m.q16(0.3)] * 4, "b1": [0, 0],
                            "W2": [m.q16(0.3), m.q16(-0.3)], "b2": 0}}
for s in (0, 1, 2):
    r = _np.random.default_rng(s)
    inits["rng%d" % s] = {"W1": [m.q16(v) for v in r.uniform(-1, 1, 4)],
                          "b1": [m.q16(v) for v in r.uniform(-1, 1, 2)],
                          "W2": [m.q16(v) for v in r.uniform(-1, 1, 2)], "b2": m.q16(r.uniform(-1, 1))}
for name, init in inits.items():
    hs, cells = replay(20000, init=init)
    preds = [round(m.f64(m.worker_forward([m.q16(v) for v in x], cells)[0]["y"])) for x, _ in data]
    print("  init %-15s preds=%s xor_solved=%s" % (name, preds, preds == [0, 1, 1, 0]))
print("T total: %.1fs" % (time.time() - t0))
