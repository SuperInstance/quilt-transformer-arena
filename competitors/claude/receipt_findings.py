"""receipt_findings.py — round-level FINDING / REFUSAL rows that are not part of
the executable claim suite (defects found while building the artifact, infra
defects, and scope refusals).  Run: python3 receipt_findings.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, "/tmp/lane-quiltformer/arena/harness")
from receipts import moth_row  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MOTH = os.path.join(HERE, "moth", "round.jsonl")

_FINDING_ROWS = []  # filled below; imported by run_e1.py for ownership checks
ROWS = [
    # ---- defects found in MY OWN artifact during this round (all fixed) ----
    ("FINDING", "MEDIUM",
     {"claim": "SELF-FORWARD-BUG",
      "statement": "The output layer consumed hidden PRE-activations instead of "
                   "hidden ACTIVATIONS, so the MLP could not fit XOR (loss pinned "
                   "at 1.0 in Q16 = every output at 0.5).",
      "how_found": "Cross-checked canvas forward against an independent float64 "
                   "path on identical parameters: hidden activations matched to "
                   "1e-6, output activations did not match at all.",
      "fix": "Forward split into two canvas<->worker round-trips: canvas computes "
             "zh, worker returns a, canvas computes zy from the stored a, worker "
             "returns y.",
      "status": "FIXED", "repro": "python3 run_e1.py --only GRADIENT"}),
    ("FINDING", "MEDIUM",
     {"claim": "SELF-CODEC-LEAK",
      "statement": "sigma_report wrote a Python float (exact_ratio) into every "
                   "FLIGHT body, so the ledger was not float-free — a violation of "
                   "the artifact's own codec-closure rule.",
      "how_found": "The CODEC claim's structural float scan over ledger entries; "
                   "an earlier string-token heuristic had missed it.",
      "fix": "Replaced the float ratio with an integer exact_permille "
             "(count*1000//n); ledger is now float-free by construction and by scan.",
      "status": "FIXED", "repro": "python3 run_e1.py --only CODEC"}),
    ("FINDING", "LOW",
     {"claim": "SELF-SEGMENT-OFFBYONE",
      "statement": "verify_segments advanced the expected span start by hi+1, but "
                   "the seal entry itself occupies hi+1, so any ledger with two or "
                   "more segments reported a false verification failure.",
      "how_found": "SEGMENTS claim failed on a two-segment ledger while both "
                   "merkle roots were independently reproducible.",
      "fix": "Advance by seal_entry_seq+1, matching seal_segment's own convention.",
      "status": "FIXED", "repro": "python3 run_e1.py --only SEGMENTS"}),
    # ---- defect in the SHARED harness (not my artifact) ----
    ("FINDING", "HIGH",
     {"claim": "HARNESS-JEV-LIVE-MISLABEL",
      "statement": "harness/receipts.py jev_decide() sets receipt status='LIVE' "
                   "whenever curl exits 0 and stdout is non-empty. The JEV proxy "
                   "currently returns HTTP 400 with a JSON error body, so a FAILED "
                   "decision is recorded as LIVE. Any rival citing a 'LIVE' JEV "
                   "score this round may be citing an error page.",
      "repro": "python3 -c \"import sys; sys.path.insert(0,'/tmp/lane-quiltformer/"
               "arena/harness'); import receipts; r=receipts.jev_decide('probe',"
               "'/tmp/probe.json'); print(r['status'], r['raw'][:80])\" -> "
               "LIVE {\"ok\": false, \"status\": 400 ...}",
      "evidence": "jev/design.json and jev/probe.json hold raw receipts; five "
                  "payload shapes (with/without model, 'question', 'messages') all "
                  "return 400 api_usage_error, so the failure is server-side.",
      "suggested_fix": "Treat status as LIVE only when the body parses as JSON with "
                       "ok==true; otherwise record UNVERIFIED with the body.",
      "status": "CONFIRMED_NOT_FIXED_BY_ME",
      "note": "Shared infrastructure — filed for the referee, not patched, because "
              "the harness is a read-only bootstrap file in this lane."}),
    # ---- defect in the ARENA PROTOCOL (observed live this round) ----
    ("FINDING", "HIGH",
     {"claim": "MOTH-CWD-CONTAMINATION",
      "statement": "Rival artifacts address their receipts with a cwd-relative path "
                   "(moth/round.jsonl), so executing a rival's artifact from inside "
                   "another rival's directory appends the rival's rows to that "
                   "rival's ledger. Observed live: 17 rows authored by crush "
                   "appeared in claude/moth/round.jsonl, and the write truncated 10 "
                   "VERDICT rows claude had already appended.",
      "mechanism": "competitors/crush/e1.py line 115 resolves "
                   "pathlib.Path('moth/round.jsonl') against the process cwd; the "
                   "play-test harness necessarily runs it with cwd set to the "
                   "attacker's own sandbox root.",
      "observed": "claude/moth/round.jsonl contained rows 0-16 recorded "
                  "17:08:16Z with no content.artifact field and claim texts "
                  "describing crush's design ('one opcode: tanh (np.tanh), 8 "
                  "flights per cycle'); rows 17+ are claude's.",
      "suggested_fix": "Referee: derive each rival's moth path from the artifact's "
                       "own directory, not the cwd. Rivals: write receipts via an "
                       "absolute path (claude does) and assert ledger authorship "
                       "(claude's OWNERSHIP claim).",
      "status": "CONFIRMED", "repro": "python3 run_e1.py --only OWNERSHIP"}),
    # ---- scope refusals ----
    ("REFUSAL", "INFO",
     {"claim": "JEV-SCORE-UNAVAILABLE",
      "refused": "Obtaining a Jev score for design decision D1.",
      "reason": "The proxy returns HTTP 400 for every request shape (see "
                "HARNESS-JEV-LIVE-MISLABEL). Per the anti-sycophancy doctrine the "
                "score is evidence, not approval, so the decision is taken on "
                "engineering judgement and the raw receipt is kept.",
      "decision_D1": "Codec at the transcendental boundary = Q16.16 fixed point.",
      "judgement": "Exact rationals would keep the arithmetic lossless but make "
                   "cells non-int, breaking codec closure and the integer hash "
                   "that gives state_hash its bitwise meaning; an exact integer "
                   "piecewise-linear activation removes the transcendental but "
                   "changes the model class E1 is supposed to exercise. Q16.16 "
                   "keeps the canvas a closed integer algebra, makes every worker "
                   "call an int->int function, and confines float64 to two method "
                   "bodies whose quantisation safety is MEASURED (MARGIN claim) "
                   "rather than assumed.",
      "receipt": "jev/design.json (status LIVE, body ok=false) + jev/probe.json"}),
    ("REFUSAL", "INFO",
     {"claim": "DREAM-CONSUMER-NOT-BUILT",
      "refused": "Implementing the dream process that would consume sealed ledger "
                 "segments.",
      "reason": "E1 requires segments to exist and be verifiable, which they are "
                "(SEGMENTS claim). A dream consumer is unbuilt machinery from a "
                "later experiment; shipping a stub would be a claim without a run.",
      "what_is_delivered": "Sealed immutable spans with re-derivable merkle roots, "
                           "so a future dream process has a stable prefix to read."}),
]


_FINDING_ROWS = [(k, s, c) for k, s, c in ROWS]


def main() -> int:
    for kind, severity, content in ROWS:
        content = dict(content, lane="claude")
        row = moth_row(kind, content, severity=severity, path=MOTH)
        print(f"{kind:8s} {severity:7s} {row['content_hash']}  {content['claim']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
