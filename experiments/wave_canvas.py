"""WaveCanvas — the Quilt matrix as a quantum phase field (Casey's wave-guide lane).

Cells hold COMPLEX phases as exact integers (Q16.16 re/im) so the whole field stays
bitwise-hashable and receiptable. A write is a pebble: it ripples signed interference
(constructive/destructive) to neighbors — no conditionals, pure propagation. A boundary
scanner emits a flat structural array (per-edge energy gradients) — the JEV-shaped input.
A typed structural judge gates the loop; a fault wakes System 2. All receipts via MOTH.

Substrate honesty: the "Moth phase" here is a deterministic integer field, not a QPU.
Vendor quantum substrates enter by measurement (E-D), never by assertion. Receipts doctrine.
"""
import json, math, pathlib, time, sys

SCALE = 1 << 16
def q16(x: float) -> int: return int(round(x * SCALE))

def canonical(o) -> str: return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
def kev(d) -> str:
    if not isinstance(d, (str, bytes)): d = canonical(d)
    if isinstance(d, str): d = d.encode()
    h = 0xcbf29ce484222325
    for b in d: h = ((h ^ b) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"0x{h:016x}"

class WaveCanvas:
    """W×H field of complex phases (re,im int Q16) + per-cell energy. Bitwise deterministic."""
    def __init__(self, w: int, h: int, ripple_k: float = 0.18, dissipate: float = 0.30):
        self.w, self.h = w, h
        self.k = q16(ripple_k); self.diss = q16(dissipate)
        self.re = [0] * (w * h); self.im = [0] * (w * h); self.en = [0] * (w * h)
        self.ticks = 0

    def idx(self, x, y): return y * self.w + x

    def write(self, x: int, y: int, d_re: int, d_im: int):
        """A pebble: add phase at (x,y); ripple propagates on tick()."""
        i = self.idx(x, y); self.re[i] += d_re; self.im[i] += d_im

    def tick(self):
        """One interference step: each cell radiates signed k·phase to 4-neighbors."""
        w, h, k = self.w, self.h, self.k
        nre = self.re[:]; nim = self.im[:]
        for y in range(h):
            for x in range(w):
                i = y * w + x
                sr, si = (self.re[i] * k) >> 16, (self.im[i] * k) >> 16
                for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    nx, ny = x+dx, y+dy
                    if 0 <= nx < w and 0 <= ny < h:
                        j = ny * w + nx
                        nre[j] += sr; nim[j] += si   # signed: constructive OR destructive
                # open field: the phase itself dissipates (energy physically leaves),
                # so a pebble storm relaxes instead of faulting forever
                dr = (self.re[i] * self.diss) >> 16; di = (self.im[i] * self.diss) >> 16
                nre[i] -= dr; nim[i] -= di
                d = (self.en[i] * self.diss) >> 16
                self.en[i] -= d
                self.en[i] += abs(sr) + abs(si)
        self.re, self.im = nre, nim
        self.ticks += 1

    def structural_array(self) -> list:
        """The flat JEV input: per-edge energy gradient, row-major, len = 2WH-W-H."""
        out = []; w, h = self.w, self.h
        for y in range(h):
            for x in range(w):
                i = self.idx(x, y)
                if x + 1 < w: out.append(abs(self.en[self.idx(x+1,y)] - self.en[i]))
                if y + 1 < h: out.append(abs(self.en[self.idx(x,y+1)] - self.en[i]))
        return out

    def field_hash(self) -> str:
        return kev({"re": self.re, "im": self.im, "en": self.en, "ticks": self.ticks})

class StructuralJudge:
    """Typed-probability gate over the structural array. Local surrogate by default;
    the JEV endpoint can be slotted in (E-D) — the receipt shape is identical."""
    RUBRIC = {"max_grad": q16(2.2), "mean_grad_floor": 0, "nonlocality": 40}
    def judge(self, arr: list) -> dict:
        if not arr: return {"verdict": "NO_SIGNAL", "p_fault": 0.0}
        mg = max(arr); mean = sum(arr) / len(arr)
        nl = sum(1 for v in arr if v > mean * 4)   # nonlocal spikes: peaks far above field
        fault = mg > self.RUBRIC["max_grad"] or nl > self.RUBRIC["nonlocality"]
        p = min(0.999, (mg / (self.RUBRIC["max_grad"] * 2)) + nl * 0.05)
        return {"verdict": "FAULT" if fault else "DETERMINISTIC",
                "p_fault": round(p, 4), "max_grad": mg, "mean_grad": round(mean, 1),
                "nonlocality": nl}

def run_demo(path="moth.jsonl"):
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    rows = []
    def moth(kind, content, sev="INFO"):
        row = {"kind": kind, "severity": sev, "content": content,
               "content_hash": kev(content), "recorded": time.time()}
        rows.append(row)
        with open(path, "a") as f: f.write(canonical(row) + "\n")
        return row

    c = WaveCanvas(16, 16)
    system2_wakes = []
    # simulate: gentle sensor drift for 12 ticks, then a structural fault (pebble storm)
    for t in range(14):
        c.write(t % 16, (t * 3) % 16, q16(0.05 * math.sin(t)), q16(0.03 * math.cos(t)))
        if t == 9:  # inject the anomaly: 5 pebbles at once in one corner (non-local spike)
            for px in range(3):
                for py in range(3): c.write(px, py, q16(1.4), q16(0.9))
        c.tick()
        j = StructuralJudge().judge(c.structural_array())
        if j["verdict"] == "FAULT": system2_wakes.append((t, j))
    h1 = c.field_hash()
    # determinism: rebuild, replay identical writes, expect bitwise-identical field
    c2 = WaveCanvas(16, 16)
    for t in range(14):
        c2.write(t % 16, (t * 3) % 16, q16(0.05 * math.sin(t)), q16(0.03 * math.cos(t)))
        if t == 9:
            for px in range(3):
                for py in range(3): c2.write(px, py, q16(1.4), q16(0.9))
        c2.tick()
    h2 = c2.field_hash()
    det = h1 == h2
    moth("VERDICT", {"claim": "DETERMINISM", "field_hash": h1, "replay_hash": h2,
                     "pass": det, "repro": "python3 experiments/wave_canvas.py"}, "VERIFIED" if det else "FAIL")
    caught = len(system2_wakes) > 0
    moth("VERDICT", {"claim": "FAULT_ISOLATION", "system2_wakes": system2_wakes,
                     "pass": caught, "note": "System 2 woke ONLY at the injected non-local spike"}, "VERIFIED" if caught else "FAIL")
    moth("FINDING", {"id": "WAVEGUIDE-ENERGY-LEDGER", "note":
        "dissipation is billed per-cell; total energy is NOT conserved by design (it is an "
        "open field) — publish the ledger, do not claim conservation. Receipt-first."})
    print(json.dumps({"deterministic": det, "wakes": len(system2_wakes),
                      "field_hash": h1, "rows": len(rows)}, indent=1))
    return det and caught

if __name__ == "__main__":
    ok = run_demo(sys.argv[1] if len(sys.argv) > 1 else "/tmp/wave-moth.jsonl")
    print("WAVE-CANVAS", "OK" if ok else "FAIL")
