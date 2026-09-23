import sys, json, pathlib
HERE = pathlib.Path("/tmp/lane-quiltformer/arena/competitors/claude")
sys.path.insert(0, str(HERE))
import e1

rows = [json.loads(l) for l in
        pathlib.Path("/tmp/lane-quiltformer/arena/competitors/crush/ledger.jsonl").read_text().splitlines()]

print("=== M. rewind claim executed against the PERSISTED ledger file (not in-memory objects) ===")
for k in (0, 1500, 2995):
    out = e1.rewind_check(rows, k)
    print(f"  k={k}: bitwise_equal={out['bitwise_equal']} rerun_final_hash={out['rerun_final_hash']}")

print("\n=== N. regenerated receipts vs persisted ones (claims reproducible?) ===")
mine = [json.loads(l) for l in (HERE / "moth/round.jsonl").read_text().splitlines()]
theirs = [json.loads(l) for l in
          pathlib.Path("/tmp/lane-quiltformer/arena/competitors/crush/moth/round.jsonl").read_text().splitlines()]
mh = [(r["kind"], r["content_hash"]) for r in mine]
th = [(r["kind"], r["content_hash"]) for r in theirs]
print("  row count mine/theirs:", len(mine), len(theirs))
print("  (kind, content_hash) sequences identical:", mh == th)
for a, b in zip(mh, th):
    if a != b:
        print("   MISMATCH", a, b)
print("  recorded timestamps differ (expected):",
      mine[0]["recorded"] != theirs[0]["recorded"], mine[0]["recorded"], theirs[0]["recorded"])

print("\n=== O. ARTIFACT.md hash citations all present in round.jsonl? ===")
art = pathlib.Path("/tmp/lane-quiltformer/arena/competitors/crush/ARTIFACT.md").read_text()
import re
cited = re.findall(r"0x[0-9a-f]{16}", art)
allh = {r["content_hash"] for r in theirs}
for c in cited:
    print(f"   {c}  cited-in-ARTIFACT  in-round.jsonl={c in allh}")

print("\n=== P. verdict rows are emitted VERDICT even when a check fails? (static) ===")
src = pathlib.Path("/tmp/lane-quiltformer/arena/competitors/crush/e1.py").read_text()
i = src.index("for v in verdicts:")
print(src[i:i+400])
j = src.index('"worker_class": "numpy"')
print("...\n" + src[j-260:j+220])
