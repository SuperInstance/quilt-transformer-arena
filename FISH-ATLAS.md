# FISH-ATLAS.md — known noise shapes in the arena's sonar

*Casey's spinning-disc doctrine: the fish were always in the ping. This atlas names the shapes we already know, so future ones are recognized as variants.*

## Atlas

### F-1: Codec boundary impedance mismatch
**Signature:** values crossing the canvas↔worker boundary without codec transform; downstream computation proceeds without error but is semantically void. **First specimen:** kimi E1 Round 1 — raw data ints passed to worker where Q16 ints expected; every input read as ~0; training was a silent no-op while the harness reported success. **Variant family:** unencoded probes (the measurement itself lying while the artifact is fine). **Detection:** assert-guard at canvas write (FLOAT LEAK) + probe-vs-system differential testing. **Expected re-occurrence:** HIGH — this is the paradigm's natural bug attractor; collect variants like specimens.

### F-2: Half-ULP σ floor
**Signature:** measured worker-boundary σ converging to exactly half the codec's ULP. **Specimens:** kimi 7.63e-6, crush 7.63e-6 — independent builds, identical number. **Open question:** quantization floor or attractor? (EMERGENCE item 1.) **Prediction:** if claude's independent build lands on the same σ, promote F-2 from observation to law.

### F-3: Refusal-set re-entry order
**Signature:** fields cut early (receipted REFUSALs) returning in a non-arbitrary order as rounds deepen. **Specimen:** crush's 10 cuts (Round 1). **Hypothesis:** re-entry order encodes necessity-vs-habit in system design. **Watch:** which cut returns first, and forced by what round pressure.

### F-4: Lying probe
**Signature:** measurement harness itself codec-violating, making a healthy artifact look broken (or vice versa). **Specimen:** kimi E1 Round 1 prediction probe. **Lesson:** always suspect the probe before the artifact; run probe-vs-probe differentials.

### F-5: Artifact geometry predicts attack geometry *(hypothesis, unconfirmed)*
**Signature:** the physical shape of a rival's ledger/storage constrains which attacks are even thinkable against it. **Specimen:** crush's 674KB on-disk jsonl vs kimi's in-memory full-value receipts. **Test in Round 2+:** do opponents attack the on-disk ledger differently (persistence/tamper) than the in-memory one (consistency/ordering)?

## Standing rules
- New specimen → add as variant under the matching family when possible; new family only when the shape is genuinely unseen.
- Every specimen gets: signature, first occurrence, detection method, expected re-occurrence rate.
- The atlas is operator training material — read it before writing Round N play-test notes.
