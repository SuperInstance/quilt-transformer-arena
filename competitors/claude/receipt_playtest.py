"""receipt_playtest.py — adversarial play-test rows for the rivals' artifacts.

Every CONFIRMED row was reproduced by claude directly (not on the sub-agent's
word) via verify_playtest.py, which re-implements crush's own integrity() check
verbatim and runs it against their delivered ledger read-only.
"""
from __future__ import annotations
import os, sys

sys.path.insert(0, "/tmp/lane-quiltformer/arena/harness")
from receipts import moth_row

MOTH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "moth", "round.jsonl")

ROWS = [
    ("VERDICT", "INFO", {
        "claim": "PLAYTEST-CRUSH-REWIND-GENUINE",
        "statement": "crush's bitwise rewind is a real re-derivation, not a "
                     "snapshot restore: running their rewind_check against the "
                     "PERSISTED ledger.jsonl at k in {0, 1500, 2995} returns "
                     "bitwise_equal=True with rerun_final_hash 0x14bae40992f440af.",
        "also_confirmed": "A fresh `python3 e1.py` reproduces their delivered "
                          "674 KB ledger.jsonl bit-for-bit (sha256 9e83908eb38ae2f2) "
                          "under PYTHONHASHSEED=0 and =random; all 17 receipt "
                          "content_hash values reproduce exactly.",
        "sigma_note": "Their sigma_max = 7.629326058800068e-06 equals the Q16.16 "
                      "half-ULP bound 2**-17 = 7.62939453125e-06 to 5 s.f. — they "
                      "measured the codec floor instead of hand-waving exactness.",
        "artifact": "competitors/crush/e1.py", "verified": True}),

    ("FINDING", "HIGH", {
        "claim": "PLAYTEST-CRUSH-CHAIN-NOT-A-CHAIN",
        "statement": "crush's integrity() is not a hash CHAIN. post[n] = "
                     "kev(state[n]) hashes only that row's own snapshot and "
                     "pre[n+1] merely copies post[n], so no hash commits history. "
                     "A mid-history cell forge with the two adjacent hash fields "
                     "repaired leaves integrity() True AND the published final "
                     "hash unchanged.",
        "repro": "python3 verify_playtest.py   (section D1)",
        "observed": "integrity()=True on 3001 rows after state[1500].oa += 1 with "
                    "post[1500] recomputed and pre[1501] re-pointed; final "
                    "0x14bae40992f440af unchanged.",
        "why_it_matters": "Their ARTIFACT.md claim 'tampering one cell by +1 is "
                          "detected (chain check fails)' is only true for a tamper "
                          "that leaves adjacent hash fields stale — i.e. the "
                          "weakest possible attacker. Their own tamper test does "
                          "exactly that.",
        "fix_cost": "One concept: post[n] = kev(post[n-1] + canonical(state[n])).",
        "status": "CONFIRMED", "severity_justification": "defeats the artifact's "
                           "stated ledger-integrity claim"}),

    ("FINDING", "HIGH", {
        "claim": "PLAYTEST-CRUSH-INTEGRITY-BLIND-FIELDS",
        "statement": "crush's integrity() reads only {state, post, pre}. The sigma "
                     "column, the cycle numbers, and the ledger's own length are "
                     "all outside the checksum, so each can be altered with no "
                     "detection at all — and truncation yields a DIFFERENT final "
                     "hash while integrity() still returns True.",
        "repro": "python3 verify_playtest.py   (sections D2a, D2b, D2c)",
        "observed": ["sigma[1500] -> 'hacked': integrity True",
                     "3001 rows truncated to 2001: integrity True, final "
                     "0xf37089955f3e1d91 (differs from 0x14bae40992f440af)",
                     "every cycle renumbered x7: integrity True"],
        "status": "CONFIRMED"}),

    ("FINDING", "LOW", {
        "claim": "PLAYTEST-CRUSH-VERDICT-LITERALS",
        "statement": "Two of crush's five VERDICT rows carry assertion literals "
                     "rather than measured values (int_assert_passed: True; "
                     "worker_class/opcodes/flights_per_cycle are hardcoded), and "
                     "the console's passed= expression falls through a .get chain "
                     "to True when no recognised key is present, so those rows "
                     "print passed=True unconditionally.",
        "mitigation": "Their three substantive verdicts (XOR learned, rewind "
                      "bitwise, integrity/tamper) ARE computed from the run.",
        "repro": "python3 -c \"import pathlib;print(pathlib.Path('/tmp/lane-"
                 "quiltformer/arena/competitors/crush/e1.py').read_text()"
                 ".split('verdicts = [')[1][:900])\"",
        "status": "CONFIRMED"}),

    ("FINDING", "INFO", {
        "claim": "PLAYTEST-CRUSH-CODEC-HYGIENE-NOT-A-DEFECT",
        "statement": "crush's ledger persists a float sigma in 3000/3000 "
                     "non-genesis rows, and two VERDICT rows place floats inside "
                     "the kev preimage. Filed as an observation, NOT a defect: "
                     "their ARTIFACT.md claims only 'canvas never sees a float' "
                     "and 'wire is int->int', both of which hold. An initial "
                     "report that this contradicted their own wording was checked "
                     "and withdrawn — their doc makes no ledger float-freedom "
                     "claim.",
        "note": "For a referee verifying receipts without float ambiguity, an "
                "integer sigma (e.g. ulps) would make the ledger codec-clean at "
                "no cost.",
        "repro": "python3 verify_playtest.py   (section D3)",
        "status": "CONFIRMED_AS_OBSERVATION"}),
]


def main() -> int:
    for kind, severity, content in ROWS:
        content = dict(content, lane="claude")
        row = moth_row(kind, content, severity=severity, path=MOTH)
        print(f"{kind:8s} {severity:7s} {row['content_hash']}  {content['claim']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
