import os, subprocess, sys, pathlib, hashlib, time

HERE = pathlib.Path("/tmp/lane-quiltformer/arena/competitors/claude")
results = {}
for seed in ("0", "random"):
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = seed
    t0 = time.time()
    p = subprocess.run([sys.executable, "e1.py"], cwd=str(HERE), env=env,
                       capture_output=True, text=True)
    dt = time.time() - t0
    (HERE / f"seed_{seed}.out").write_text(p.stdout)
    (HERE / f"seed_{seed}.err").write_text(p.stderr)
    led = (HERE / "ledger.jsonl").read_bytes()
    moth = (HERE / "moth/round.jsonl").read_bytes()
    results[seed] = {
        "rc": p.returncode, "secs": round(dt, 1),
        "stdout_tail": p.stdout.strip().splitlines()[-4:],
        "stderr_tail": p.stderr.strip().splitlines()[-3:],
        "ledger_sha": hashlib.sha256(led).hexdigest(),
        "moth_sha": hashlib.sha256(moth).hexdigest(),
        "stdout_sha": hashlib.sha256(p.stdout.encode()).hexdigest(),
    }
    print(seed, results[seed]["rc"], results[seed]["secs"], "ledger", results[seed]["ledger_sha"][:16],
          "stdout", results[seed]["stdout_sha"][:16])

a, b = results["0"], results["random"]
print("\nDETERMINISM (PYTHONHASHSEED 0 vs random):")
print("  stdout identical:", a["stdout_sha"] == b["stdout_sha"])
print("  ledger identical:", a["ledger_sha"] == b["ledger_sha"])

theirs = pathlib.Path("/tmp/lane-quiltformer/arena/competitors/crush/ledger.jsonl").read_bytes()
mine = (HERE / "ledger.jsonl").read_bytes()
print("\nFRESH RUN vs PERSISTED crush/ledger.jsonl:")
print("  identical bytes:", mine == theirs, "| theirs sha", hashlib.sha256(theirs).hexdigest()[:16])
if mine != theirs:
    ml, tl = mine.decode().splitlines(), theirs.decode().splitlines()
    print("  line counts:", len(ml), len(tl))
    for i, (x, y) in enumerate(zip(ml, tl)):
        if x != y:
            print("  FIRST DIFF at line", i)
            print("   mine  :", x[:220])
            print("   theirs:", y[:220])
            break
