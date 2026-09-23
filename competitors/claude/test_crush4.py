import sys, json, pathlib, copy
HERE = pathlib.Path("/tmp/lane-quiltformer/arena/competitors/claude")
sys.path.insert(0, str(HERE))
import e1

print("=== Q. floats in HASH PREIMAGES? ===")
rounds = [json.loads(l) for l in
          pathlib.Path("/tmp/lane-quiltformer/arena/competitors/crush/moth/round.jsonl").read_text().splitlines()]
for r in rounds:
    if r["kind"] == "VERDICT":
        floats = {k: v for k, v in r["content"].items() if isinstance(v, float)}
        if floats:
            print(f"  {r['content_hash']} {r['content']['claim'][:48]!r}")
            print(f"      float fields inside the kev() preimage: {floats}")
led = [json.loads(l) for l in
       pathlib.Path("/tmp/lane-quiltformer/arena/competitors/crush/ledger.jsonl").read_text().splitlines()]
print("  ledger preimage = canonical(state) only -> floats in preimage:",
      any(isinstance(v, float) for r in led for v in r["state"].values()))
print("  ledger row body carries float sigma:", sum(1 for r in led if isinstance(r['sigma'], float)), "of 3000")
print("  ARTIFACT wording: 'floats exist only inside the flight "
      "(sigma residual reported, NEVER STORED)' -> contradicted by ledger.jsonl sigma column")

print("\n=== R. minimal forge recipe, end to end (the headline test) ===")
r = copy.deepcopy(led)
r[1500]["state"]["oa"] += 1                       # 1. edit one cell, one row
r[1500]["post"] = e1.ch(r[1500]["state"])          # 2. fix this row's hash
r[1501]["pre"] = r[1500]["post"]                   # 3. fix the next row's pointer
print("  integrity()                :", e1.integrity(r))
print("  final post (published val) :", r[-1]["post"], "unchanged:", r[-1]["post"] == led[-1]["post"])
print("  rows touched               : 1 (plus 2 hash fields); no downstream state changes")
print("  rewind_check(k=0) diverges :", not e1.rewind_check(r, 0)["bitwise_equal"], "(the only checker that sees it)")

print("\n=== S. same-attack sweep: which of their 2 checkers sees which tamper ===")
def probe(name, mutate, use_rewind=True):
    t = copy.deepcopy(led); mutate(t)
    integ = e1.integrity(t)
    rw = "n/a"
    if use_rewind:
        try:
            rw = e1.rewind_check(t, 0)["bitwise_equal"]
        except Exception as ex:
            rw = f"crash:{type(ex).__name__}"
    seen = []
    if not integ: seen.append("integrity")
    if rw is False: seen.append("rewind@0")
    print(f"  {name:<44} integrity={str(integ):<5} rewind@0_bitwise_equal={rw}  seen_by={seen or 'NOTHING ***'}")

probe("sigma := 0.0 at cycle 1500", lambda t: t[1500].__setitem__("sigma", 0.0), use_rewind=False)
probe("all 3001 cycle numbers renumbered x7", lambda t: [t[i].__setitem__("cycle", i * 7) for i in range(len(t))], use_rewind=False)
probe("truncate to 2001 rows (drop 1000 cycles)", lambda t: t.__setitem__(slice(2001), None).__class__ or None, use_rewind=False) if False else None
t = copy.deepcopy(led)[:2001]
print(f"  {'truncate to 2001 rows (drop 1000 cycles)':<44} integrity={e1.integrity(t)}  seen_by={'integrity' if not e1.integrity(t) else 'NOTHING ***'}")
probe("state oa+1 at 1500 + 2 hash fields fixed", lambda t: (t[1500]["state"].__setitem__("oa", t[1500]["state"]["oa"] + 1),
                                                            t[1500].__setitem__("post", e1.ch(t[1500]["state"])),
                                                            t[1501].__setitem__("pre", t[1500]["post"])))
probe("state oa+1 at 1500, hashes NOT fixed (their test)", lambda t: t[1500]["state"].__setitem__("oa", t[1500]["state"]["oa"] + 1))
probe("all cells -> float, rechained", lambda t: ([x.__setitem__("state", {k: float(v) for k, v in x["state"].items()}) for x in t],
                                                 [t[i].__setitem__("post", e1.ch(t[i]["state"])) for i in range(len(t))],
                                                 [t[i + 1].__setitem__("pre", t[i]["post"]) for i in range(len(t) - 1)]))
