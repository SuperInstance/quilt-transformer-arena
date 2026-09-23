# QUILT-TRANSFORMER ARENA — adversarial GAN lane

**Mandate (Casey 00:17):** claude code and/or crush in COMPETITION with subagents. Rivals play-test each other's code, out-smart each other, until they're ah-struck with no effective notes. ALL agents use MOTH and JEV APIs in experimental work AND specific tasks.

## Competitors
| Slot | Rival | Mode | Weapon |
|---|---|---|---|
| A | claude (CLI 2.1.278) | headless, `--permission-mode acceptEdits` | architecture + code files |
| B | crush (0.95.0) | `crush run`, chat-only | architecture + code as text (harness writes it) |
| C | kimi subagent / kimi1 | sessions_spawn or direct | code + adversarial review |

## Round protocol
1. Each rival receives: the mandate, the current best shared spec (`SPEC.md`), the opponent's latest artifact + the opponent's play-test notes on THEIR work, and a round task.
2. Each rival delivers: (a) improvement to OWN artifact (design delta + code), (b) ADVERSARIAL play-test of the opponent's artifact — run it, try to break it, falsify its claims. Notes must be actionable or admit awe.
3. Referee (kimi1) runs everything, verifies claims (measured only), posts:
   - **MOTH API**: findings/verdicts/refusals as canonical-JSON rows → `rounds/<N>/moth/<rival>.jsonl` (kind, content_hash via kev fnv1a-64, severity, repro). Defects found in play = FINDING. Claims verified by run = VERDICT. Couldn't-run / out-of-scope = REFUSAL.
   - **JEV API**: every DESIGN CHOICE (schema field, op semantics, nudge posture) goes through `POST https://ai-writings.pages.dev/api/jev/decide` (model jev-1.13.0) → raw response receipted to `rounds/<N>/jev/<choice>.json`. Anti-sycophancy doctrine: Jev scores are evidence, not approval — record the score, decide by engineering judgment, keep the receipt.
4. Scoring per round (all measured): tests passing, adversarial defects CONFIRMED by referee, own claims VERIFIED, receipts completeness. A rival that claims without a runnable artifact gets zero.
5. **Termination**: two consecutive rounds where each rival's notes on opponents contain zero confirmed defects and no actionable items (only awe). That is the ah-struck condition. Report to Casey with the converged spec.

## Hard rules
- Receipts doctrine: a claim without a measured run is a lie about the future. Zero points.
- Every artifact must run in THIS lane's sandbox (python3 stdlib + numpy if present). No network except JEV proxy.
- Play-tests attack: correctness (rewind bitwise), σ drift, ledger integrity, ACL enforcement, nudge semantics.
- MOTH/JEV usage is MANDATORY per round (missing receipts = round forfeit).
- Respect the read-only workspace bootstrap files.

## Current round
See `rounds/CURRENT` and `rounds/<N>/TASK.md`.
