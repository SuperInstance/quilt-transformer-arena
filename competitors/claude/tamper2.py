"""Refined ledger-tamper tests: is ANY forgery detected by their 'verified by rerunning' rewind?"""
import importlib.util, json, copy

KIMI = "/tmp/lane-quiltformer/arena/competitors/kimi/e1.py"
spec = importlib.util.spec_from_file_location("kimi_e1", KIMI)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

data = [([0, 0], 0), ([0, 1], 1), ([1, 0], 1), ([1, 1], 0)]
dump = json.loads(open("/tmp/lane-quiltformer/arena/competitors/claude/kimi_dump.json").read())
led = [{"cycle": i, "note": "", "state_hash": dump["ledger_hashes"][i]} for i in range(20001)]
led[37]["cells"] = dump["cells37"]; led[38]["cells"] = dump["cells38"]
# only 37/38 carry cells in the dump; rewind at 37 only needs those + hash[38]
del led[20000]

def rewind_ok(L, k=37, lr=0.5):
    snap = L[k]["cells"]
    cc = m.Canvas(); cc.cells = dict(snap)
    x, t = data[(k + 1) % 4]
    xq = [m.q16(v) for v in x]
    fwd, _ = m.worker_forward(xq, cc.cells)
    for n, v in (("h", fwd["h"]), ("y", fwd["y"])): cc.set(n, v)
    g, _ = m.worker_grads(xq, m.q16(t), cc.cells, fwd)
    m.sgd(cc, g, m.q16(lr))
    return m.kev(m.canonical(cc.cells)) == L[k + 1]["state_hash"]

def forge_next_hash(L, k=37, lr=0.5):
    """Attacker replays one step from their tampered cells and re-signs receipt k+1."""
    cc = m.Canvas(); cc.cells = dict(L[k]["cells"])
    x, t = data[(k + 1) % 4]
    xq = [m.q16(v) for v in x]
    fwd, _ = m.worker_forward(xq, cc.cells)
    for n, v in (("h", fwd["h"]), ("y", fwd["y"])): cc.set(n, v)
    g, _ = m.worker_grads(xq, m.q16(t), cc.cells, fwd)
    m.sgd(cc, g, m.q16(lr))
    L[k + 1]["state_hash"] = m.kev(m.canonical(cc.cells))

print("baseline (pristine)                       rewind_ok =", rewind_ok(led))

L = copy.deepcopy(led); L[37]["cells"]["W2"][0] = 424242
forge_next_hash(L); print("B' tamper cells[37] + re-sign hash[38]    rewind_ok =", rewind_ok(L), "<- FORGERY PASSES")

L = copy.deepcopy(led); del L[100]
print("C' delete receipt 100 (outside 37->38)    rewind_ok =", rewind_ok(L), "<- DELETION UNDETECTED")

L = copy.deepcopy(led); L[37]["note"] = "tampered"
print("F' rewrite receipt 37 note field          rewind_ok =", rewind_ok(L), "<- UNDETECTED")

L = copy.deepcopy(led); L[37]["cycle"] = 9999
print("G' rewrite receipt 37 cycle field         rewind_ok =", rewind_ok(L), "<- UNDETECTED")

L = copy.deepcopy(led); L[38]["state_hash"] = "0x0000000000000000"
print("H' forge hash[38] only                    rewind_ok =", rewind_ok(L), "(silent mismatch, no tamper verdict)")

# does the artifact contain ANY verification routine at all?
src = open(KIMI).read()
print("\nverify/chain/signature tokens in e1.py:",
      {t: (t in src) for t in ("verify", "prev_hash", "prev", "chain", "signature", "seq", "tamper")})
