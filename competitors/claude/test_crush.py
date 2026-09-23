import sys, json, pathlib, copy
HERE = pathlib.Path("/tmp/lane-quiltformer/arena/competitors/claude")
sys.path.insert(0, str(HERE))
import e1  # my copy; harness resolves to arena/harness exactly as for crush

THEIRS = pathlib.Path("/tmp/lane-quiltformer/arena/competitors/crush/ledger.jsonl")
rows = [json.loads(l) for l in THEIRS.read_text().splitlines()]
print("loaded persisted ledger rows:", len(rows))
print("clean integrity():", e1.integrity(rows))

def report(name, ok):
    print(f"  -> {name}: {'UNDETECTED ***' if ok else 'detected'}")

print("\n=== A. field-level tamper of the persisted ledger, judged by THEIR integrity() ===")
# A1 sigma float tamper
r = copy.deepcopy(rows); r[1500]["sigma"] = 0.0
report("sigma 7.6e-06 -> 0.0 at cycle 1500", e1.integrity(r))
r = copy.deepcopy(rows); r[1500]["sigma"] = "hacked"
report("sigma -> string 'hacked'", e1.integrity(r))

# A2 cycle renumber
r = copy.deepcopy(rows); r[1500]["cycle"] = 99999
report("cycle 1500 -> 99999", e1.integrity(r))
r = copy.deepcopy(rows)
for i in range(len(r)): r[i]["cycle"] = i * 7   # renumber the whole timeline
report("every cycle number renumbered x7", e1.integrity(r))

# A3 truncate the ledger (drop last 1000 cycles)
r = copy.deepcopy(rows[:2001])
print(f"  -> truncation to 2001/3001 rows (drops cycles 2001..3000): "
      f"{'UNDETECTED ***' if e1.integrity(r) else 'detected'} (integrity={e1.integrity(r)}, final post={r[-1]['post']})")

# A4 duplicate-row insertion
r = copy.deepcopy(rows)
dup = dict(r[1500]); r.insert(1501, dup)
report("insert duplicate copy of row 1500 (chain grows, history repeated)", e1.integrity(r))

# A5 full rechain forgery: bump a cell at cycle 1500 and re-derive every downstream hash
r = copy.deepcopy(rows)
r[1500]["state"]["oa"] += 1
for i in range(1500, len(r)):
    r[i]["post"] = e1.ch(r[i]["state"])
    if i + 1 < len(r):
        r[i + 1]["pre"] = r[i]["post"]
print(f"  -> forged history (cell oa +1 at cycle 1500, chain re-derived): "
      f"{'UNDETECTED ***' if e1.integrity(r) else 'detected'}; new final post={r[-1]['post']} "
      f"(published 0x14bae40992f440af)")

# A6 forged genesis
r = copy.deepcopy(rows)
r[0]["state"]["h1a"] += 1
r[0]["post"] = e1.ch(r[0]["state"]); r[1]["pre"] = r[0]["post"]
print(f"  -> forged GENESIS cell (h1a+1, row0 post + row1 pre re-derived): "
      f"{'UNDETECTED ***' if e1.integrity(r) else 'detected'}")

print("\n=== B. rewind_check on forged ledgers ===")
r = copy.deepcopy(rows)
r[1500]["state"]["oa"] += 1
out = e1.rewind_check(r, 1500)
print("  rewind from tampered(+) row 1500:", json.dumps(out)[:120])
r2 = copy.deepcopy(rows)
r2[1500]["state"]["oa"] += 1
for i in range(1500, len(r2)):
    r2[i]["post"] = e1.ch(r2[i]["state"])
    if i + 1 < len(r2): r2[i + 1]["pre"] = r2[i]["post"]
out2 = e1.rewind_check(r2, 1500)
print("  rewind from fully-rewritten history:", json.dumps(out2)[:140])

print("\n=== C. type hole: a ledger whose cells are FLOATS passes integrity + rewind ===")
rf = copy.deepcopy(rows)
for i in range(1500, len(rf)):
    rf[i]["state"] = {k: float(v) for k, v in rf[i]["state"].items()}
    rf[i]["post"] = e1.ch(rf[i]["state"])
    if i + 1 < len(rf): rf[i + 1]["pre"] = rf[i]["post"]
print("  half the ledger converted to float cells, rechained -> integrity:",
      e1.integrity(rf))
outf = e1.rewind_check(rf, 1500)
print("  rewind_check 'bitwise_equal' on float-state ledger:", outf["bitwise_equal"],
      "| final hash:", outf["rerun_final_hash"])
print("  (note: rewind_check's own compare is dict ==, and 205246 == 205246.0 in python)")

print("\n=== D. independent recompute of the XOR / sigma claims from the PERSISTED final state ===")
C = rows[-1]["state"]
margins = sorted(round(abs(e1.forward(C, x)[2] - e1.F // 2) / e1.F, 4) for x, t in e1.DATA)
cls = [((e1.forward(C, x)[2] > e1.F // 2) == (t == e1.F)) for x, t in e1.DATA]
print("  classified:", cls, "| margins:", margins, "| min:", margins[0], "(ARTIFACT claims 0.4728)")
sm = max(rr["sigma"] for rr in rows[1:])
print("  sigma_max over persisted ledger:", sm, " 2**-17 =", 2**-17, " 2**-16 =", 2**-16)
print("  sigma_max == 2**-17 exactly:", sm == 2**-17)

print("\n=== E. float scan of the persisted ledger ===")
import math
types = set()
for rr in rows:
    types.add(tuple(sorted({type(v).__name__ for v in rr["state"].values()})))
    if not all(isinstance(v, int) for v in rr["state"].values()):
        print("  NON-INT CELL at cycle", rr["cycle"]); break
print("  state-cell type sets seen across 3001 rows:", types)
print("  rows whose 'sigma' is a float:", sum(1 for rr in rows if isinstance(rr["sigma"], float)))
print("  json of row 1 contains a float literal:",
      any("." in tok for tok in json.dumps(rows[1]).split('"') if tok.replace('.','',1).replace('-','',1).replace('e-0','',1).isdigit()))
