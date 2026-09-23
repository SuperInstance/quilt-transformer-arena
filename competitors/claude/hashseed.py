"""PYTHONHASHSEED determinism test. Re-execs itself with the requested seed
(the sandbox blocks `env VAR=x cmd`), then runs kimi's E1 training and prints hashes."""
import importlib.util, json, os, sys

if os.environ.get("_SEED_APPLIED") != "1":
    os.environ["PYTHONHASHSEED"] = sys.argv[1]
    os.environ["_SEED_APPLIED"] = "1"
    os.execv(sys.executable, [sys.executable] + sys.argv)

KIMI = "/tmp/lane-quiltformer/arena/competitors/kimi/e1.py"
spec = importlib.util.spec_from_file_location("kimi_e1", KIMI)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

created = []
_Orig = m.Canvas
class Spy(_Orig):
    def __init__(self):
        super().__init__(); created.append(self)
m.Canvas = Spy

res = m.run()
train = created[0]
led = train.ledger
print("PYTHONHASHSEED =", os.environ["PYTHONHASHSEED"])
print("  res               :", json.dumps(res, sort_keys=True))
print("  max_sigma repr    :", repr(res["max_sigma"]))
print("  FINAL state_hash  :", m.kev(m.canonical(train.cells)))
print("  hash[37]          :", led[37]["state_hash"])
print("  hash[38]          :", led[38]["state_hash"])
print("  rewind_bitwise    :", res["rewind_bitwise"])
print("  ledger len        :", len(led))
print("  str-hash sample   :", hash("lane-quiltformer-probe"))
