"""verify_playtest.py — independent confirmation of the play-test findings on
crush/e1.py, run by claude (not delegated) before filing CONFIRMED rows.

Read-only w.r.t. competitors/crush/.  integrity() is re-implemented verbatim from
crush/e1.py rather than imported, because importing their module executes it and
would write receipts into this directory.
"""
from __future__ import annotations
import json, pathlib, sys

sys.path.insert(0, "/tmp/lane-quiltformer/arena/harness")
from receipts import kev, canonical

CRUSH = pathlib.Path("/tmp/lane-quiltformer/arena/competitors/crush")
rows = [json.loads(l) for l in (CRUSH / "ledger.jsonl").read_text().splitlines() if l.strip()]


def integrity(rows):                       # verbatim logic from crush/e1.py
    rows = [dict(r, state=dict(r["state"])) for r in rows]
    for a, b in zip(rows, rows[1:]):
        if kev(canonical(a["state"])) != a["post"] or a["post"] != b["pre"]:
            return False
    return kev(canonical(rows[-1]["state"])) == rows[-1]["post"]


def report(name, ok, detail):
    print(f"{'PASS' if ok else 'FAIL'}  {name:34s} {detail}")


print(f"rows loaded                     : {len(rows)}")
report("pristine integrity()==True     ", integrity(rows) is True, "")
final = kev(canonical(rows[-1]["state"]))
print(f"pristine final post             : {final}")

# D1: mid-history state forge, adjacent hash fields repaired
import copy
t = copy.deepcopy(rows)
t[1500]["state"]["oa"] = t[1500]["state"]["oa"] + 1
t[1500]["post"] = kev(canonical(t[1500]["state"]))
t[1501]["pre"] = t[1500]["post"]
d1 = integrity(t)
report("D1 forged cell + repaired hashes", d1 is True,
       "integrity() stays True -> tamper UNDETECTED")
report("D1 published final hash unchanged", kev(canonical(t[-1]["state"])) == final, str(final))

# D2a: sigma column is not covered at all
t2 = copy.deepcopy(rows)
t2[1500]["sigma"] = "hacked"
report("D2a sigma -> 'hacked'           ", integrity(t2) is True, "UNDETECTED")

# D2b: truncation
t3 = copy.deepcopy(rows)[:2001]
report("D2b truncated 3001 -> 2001 rows ", integrity(t3) is True,
       f"integrity=True, final={kev(canonical(t3[-1]['state']))}")

# D2c: cycle renumbering
t4 = copy.deepcopy(rows)
for i, r in enumerate(t4):
    r["cycle"] = i * 7
report("D2c all cycle numbers renumbered", integrity(t4) is True, "UNDETECTED")

# D3: floats persisted in the ledger
frows = [r for r in rows[1:] if isinstance(r.get("sigma"), float)]
report("D3 float sigma rows persisted   ", len(frows) == len(rows) - 1,
       f"{len(frows)}/{len(rows)-1} non-genesis rows carry a float sigma")
print(f"     example                   : sigma={rows[1]['sigma']!r}")

# their own ARTIFACT.md wording on storage
art = (CRUSH / "ARTIFACT.md").read_text()
for line in art.splitlines():
    if "never stored" in line or "never" in line and "float" in line:
        print(f"     their ARTIFACT.md says    : {line.strip()[:100]}")
