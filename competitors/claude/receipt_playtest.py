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

    # ---- kimi ----
    ("VERDICT", "INFO", {
        "claim": "PLAYTEST-KIMI-REWIND-HOLDS-STRONGER-THAN-TESTED",
        "statement": "kimi's bitwise-rewind property is real and survives a much "
                     "stronger test than the one they ran. Their rewind restores a "
                     "stored snapshot for one step at one fixed cycle (37); an "
                     "independent full ledger replay from init reproduces all "
                     "20001 receipt hashes with 0 mismatches, and resume-at-k for "
                     "k in {0,1,37,500,9999,19999} all reach the identical final "
                     "hash 0xa815fb36ef032318.",
        "also_confirmed": "PYTHONHASHSEED 0/random/12345 give identical final hash, "
                          "identical hash[37] and hash[38], and identical preds "
                          "[0,1,1,0]; 0 floats across all 20001 receipt cell sets; "
                          "final y = 0.0177/0.9798/0.9840/0.0157 (not a loose "
                          "acceptance test); XOR converges from 4/5 alternate inits.",
        "honesty_note": "Their ledger retains six xor_solved=false receipts before "
                        "the passing one instead of laundering its own history — "
                        "the receipts doctrine applied against its author.",
        "artifact": "competitors/kimi/e1.py", "verified": True}),

    ("FINDING", "HIGH", {
        "claim": "PLAYTEST-KIMI-REWIND-AUTHENTICATES-NOTHING",
        "statement": "kimi's 'verified by rerunning' rewind cannot detect a forged "
                     "ledger. Receipts are unchained (each hash covers only that "
                     "receipt's own cells), e1.py contains no verification routine "
                     "(no verify/prev_hash/chain/seq/tamper tokens), and "
                     "saved_hash = c.ledger[rewind_to]['state_hash'] is dead code — "
                     "the restored snapshot's hash is never compared to anything.",
        "repro": "python3 tamper2.py   (uses kimi's own worker_forward/worker_grads/"
                 "sgd/kev and their real cycle-37/38 state)",
        "observed": ["baseline pristine: rewind_ok True",
                     "tamper cells[37] + re-sign hash[38]: rewind_ok True  <- "
                     "FORGERY PASSES",
                     "delete receipt 100: rewind_ok True  <- DELETION UNDETECTED",
                     "rewrite receipt 37 note field: rewind_ok True",
                     "rewrite receipt 37 cycle field: rewind_ok True"],
        "fairness": "kimi never claims tamper-evidence — their ARTIFACT.md flags "
                    "'no ACLs yet' as exposed surface. Filed HIGH because the "
                    "round's adversarial surface names ledger integrity "
                    "explicitly, and the check that exists cannot fail.",
        "status": "CONFIRMED"}),

    ("FINDING", "MEDIUM", {
        "claim": "PLAYTEST-KIMI-REWIND-IS-SNAPSHOT-RESTORE",
        "statement": "kimi's rewind is `c2.cells = dict(c.ledger[k]['cells'])` — a "
                     "snapshot restore from the ledger, then a one-step rerun "
                     "compared against the SAME ledger's next hash. SPEC rule 6 "
                     "defines rewind as 'ledger rollback to cycle k, then "
                     "re-derive', which is prefix replay. The property holds under "
                     "the stronger reading (see PLAYTEST-KIMI-REWIND-HOLDS-"
                     "STRONGER-THAN-TESTED), so this is a claim-scope gap, not a "
                     "wrong result.",
        "also": "the rewind snapshot is a SHALLOW copy, so nested lists alias the "
                "ledger; safe today only because sgd always allocates new lists.",
        "repro": "python3 -c \"import pathlib;t=pathlib.Path('/tmp/lane-quiltformer/"
                 "arena/competitors/kimi/e1.py').read_text();i=t.find('rewind_to');"
                 "print(t[i-200:i+700])\"",
        "status": "CONFIRMED"}),

    ("FINDING", "LOW", {
        "claim": "PLAYTEST-KIMI-BOOL-ACCEPTED-BY-CANVAS",
        "statement": "kimi's Canvas.set accepts Python bools "
                     "(isinstance(True, int) is True), so a bool enters the cell "
                     "store and the hash preimage as JSON true, contradicting the "
                     "artifact's 'ONLY Q16 int64 cells' invariant. claude's canvas "
                     "rejects bools explicitly for this reason.",
        "repro": "python3 -c \"import importlib.util as u;s=u.spec_from_file_location("
                 "'k','/tmp/lane-quiltformer/arena/competitors/kimi/e1.py');"
                 "m=u.module_from_spec(s);s.loader.exec_module(m);c=m.Canvas();"
                 "c.set('k',True);print(type(c.cells['k']), m.kev(m.canonical("
                 "c.cells)))\"",
        "status": "CONFIRMED"}),

    ("FINDING", "INFO", {
        "claim": "PLAYTEST-KIMI-CORROBORATES-JEV-MISLABEL",
        "statement": "kimi's jev/design.json also carries status LIVE with a 400 "
                     "error body — reproduced live with their exact prompt. This "
                     "corroborates claude's HARNESS-JEV-LIVE-MISLABEL: the proxy is "
                     "rejecting the harness's documented payload server-side, for "
                     "every rival, so no lane obtained a real Jev score this round.",
        "status": "CONFIRMED"}),
]


def main() -> int:
    for kind, severity, content in ROWS:
        content = dict(content, lane="claude")
        row = moth_row(kind, content, severity=severity, path=MOTH)
        print(f"{kind:8s} {severity:7s} {row['content_hash']}  {content['claim']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
