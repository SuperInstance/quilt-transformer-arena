import sys, json, pathlib, copy
HERE = pathlib.Path("/tmp/lane-quiltformer/arena/competitors/claude")
sys.path.insert(0, str(HERE))
import e1

rows = [json.loads(l) for l in
        pathlib.Path("/tmp/lane-quiltformer/arena/competitors/crush/ledger.jsonl").read_text().splitlines()]

print("=== F. does rewind_check(k=0) backstop the mid-history state edit? ===")
r = copy.deepcopy(rows)
r[1500]["state"]["oa"] += 1
r[1500]["post"] = e1.ch(r[1500]["state"]); r[1501]["pre"] = r[1500]["post"]
print("  integrity on mid-history edit:", e1.integrity(r))
out = e1.rewind_check(r, 0)
print("  rewind_check(k=0) bitwise_equal:", out["bitwise_equal"], out.get("first_divergence_cycle"), out.get("cells"))
out = e1.rewind_check(r, 1500)
print("  rewind_check(k=1500) bitwise_equal:", out["bitwise_equal"], out.get("first_divergence_cycle"))

print("\n=== G. self-consistent rewrite (attacker replays training from a forged cell) ===")
r = copy.deepcopy(rows)
r[1500]["state"]["oa"] += 1
for j in range(1501, len(r)):
    e1.one_pass(r[j - 1]["state"], e1.LR)  # no-op placeholder, real rewrite below
C = dict(r[1500]["state"])
for j in range(1501, len(r)):
    e1.one_pass(C, e1.LR)
    r[j]["state"] = dict(C)
for i in range(1500, len(r)):
    r[i]["post"] = e1.ch(r[i]["state"])
    if i + 1 < len(r): r[i + 1]["pre"] = r[i]["post"]
print("  fully rewritten ledger integrity:", e1.integrity(r))
print("  rewind_check(k=0) catches it:", e1.rewind_check(r, 0)["bitwise_equal"])
print("  rewind_check(k=1500) catches it:", e1.rewind_check(r, 1500)["bitwise_equal"])
print("  new final post:", r[-1]["post"], "(published 0x14bae40992f440af)",
      "-> only detectable by comparing to the externally published hash")

print("\n=== H. all-float ledger passes integrity (kev chain does not enforce int cells) ===")
rf = copy.deepcopy(rows)
for row in rf:
    row["state"] = {k: float(v) for k, v in row["state"].items()}
for i in range(len(rf)):
    rf[i]["post"] = e1.ch(rf[i]["state"])
    if i + 1 < len(rf): rf[i + 1]["pre"] = rf[i]["post"]
print("  integrity on 3001 rows of float cells:", e1.integrity(rf))
print("  sample state:", rf[7]["state"])
print("  sample hash:", rf[7]["post"], "vs int-hash", rows[7]["post"], "(differ -> chain is type-blind, not type-checked)")

print("\n=== I. structural facts of the persisted ledger ===")
print("  row0 keys:", sorted(rows[0].keys()), "| row1 keys:", sorted(rows[1].keys()))
print("  genesis (row0) hash published anywhere in ARTIFACT.md:",
      "0x2981c490f65f1d0d" in pathlib.Path('/tmp/lane-quiltformer/arena/competitors/crush/ARTIFACT.md').read_text())
chain_ok = all(rows[i]["post"] == rows[i + 1].get("pre") for i in range(len(rows) - 1))
self_ok = all(e1.ch(r["state"]) == r["post"] for r in rows)
print("  post[n]==pre[n+1] for all 3000 pairs:", chain_ok, "| kev(state)==post for all rows:", self_ok)

print("\n=== J. claim values recomputed from the persisted final state ===")
C = rows[-1]["state"]
ms = sorted(round(abs(e1.forward(C, x)[2] - e1.F // 2) / e1.F, 4) for x, t in e1.DATA)
cls = all(((e1.forward(C, x)[2] > e1.F // 2) == (t == e1.F)) for x, t in e1.DATA)
print("  4/4 classified:", cls, "| margins:", ms, "| min margin:", ms[0], "(ARTIFACT: 0.4728)")
sm = max(rr["sigma"] for rr in rows[1:])
print("  sigma_max over ledger:", repr(sm), "== 2**-17:", sm == 2**-17, "<= 2**-16:", sm <= 2**-16)
print("  rows with float sigma:", sum(1 for rr in rows if isinstance(rr['sigma'], float)), "/ 3000 non-genesis")
print("  state cell types seen:", {tuple(sorted({type(v).__name__ for v in rr['state'].values()})) for rr in rows})

print("\n=== K. is np.rint a second numpy op in the 'one opcode' flight? ===")
import numpy as np, inspect
print("  flight_tanh source:")
print("\n".join("    " + l for l in inspect.getsource(e1.flight_tanh).splitlines()))
print("  rint ties-to-even demo: np.rint(0.5) =", np.rint(0.5), " np.rint(1.5) =", np.rint(1.5),
      " np.rint(-0.5) =", np.rint(-0.5))

print("\n=== L. line count vs '≈150 lines' claim ===")
n = len(pathlib.Path('/tmp/lane-quiltformer/arena/competitors/crush/e1.py').read_text().splitlines())
print("  e1.py lines:", n)
