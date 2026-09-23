# quilt-transformer — research v1 (town and laborers)

*Casey's mandate 2026-09-24: invert state vs execution. Canvas = permanent university town; PyTorch/JAX/C = visiting laborers. Deep ideation + component experiments.*

## 0. Decision on Casey's fork: contract schema FIRST

The zones are cell blocks; cell blocks are schema instances. The schema is the σ-bond surface (SAMO language) that makes workers hot-swappable — swap the schema's `worker_class` field and nothing else changes. Grid-zone mapping is the schema's first application, not a competing design track. Deliver schema-v0 below, then dual-zone map as instance.

## 1. Contract schema v0 (one page, deliberately minimal)

```json
{
  "contract_id": "kev:fnv1a64(...)",           // hash over all fields below = the receipt anchor
  "op": "attention | matmul | softmax | layernorm | mlp_block | custom",
  "inputs": [ {"block": "zoneA.rows2-3.cols0:50", "hash": "0x...", "codec": "q16|dyadic|raw"} ],
  "params": { "heads": 4, "scale": "1/sqrt(64)" },
  "constraints": { "flux_module": "0x...", "proof_required": true },  // FLUX bytecode; worker must attach flux proof
  "worker_class": "cpu-numpy | cpu-jax | cuda-triton | neuromorphic-x",
  "deadline": { "cue": "tick+1", "backpressure": "propagate" },        // t-minus cue lattice
  "output_slots": [ {"block": "zoneA.row4.cols0:50", "codec": "q16", "sigma_report": true} ]
}
```

- **Flight**: a batch of contracts executed by one worker visit = one ledger receipt set. Contract granularity is the cache-line size of the town — the single most important perf knob.
- **Worker capability card** (the "visa"): opcodes supported, measured drift σ vs reference worker, throughput per op, exact-codec compliance. This is literally our fleet `OpcodeCapabilityIndex` — ported to worker onboarding.
- **Refusal**: unsatisfiable contract → REFUSAL row (hologram of the unrun) → protocol reroutes worker_class. Training becomes refusal-aware for free (4quilt doctrine).

## 2. The eight hard problems (and their resolutions)

1. **Bandwidth wall.** Canvas round-trip per op = 1000× slowdown. → Workers execute *flights* (coarse regions: whole layer/block), pull inputs once, flash once. Canvas = memory, flight = kernel launch.
2. **Rewind determinism across hardware.** Floats aren't bitwise stable across substrates; hot-swappable workers break naive rewind. → Canvas stores EXACT values (ℚ rationals / Q16 fixed-point — q16-trajectories codec, commensurate.mjs dyadics already exist). Cross-substrate bitwise identity is a **measured property per worker pair** with drift gates; ledger records which worker class ran each cycle; rewind re-selects the class or accepts measured drift.
3. **Nudge race.** Async influence writes vs in-flight workers. → No locks; TICK opcode is the only serialization point. Writers write whenever; workers read influence blocks ONLY at flight start. Per-zone writer ACLs: human = single-writer cells; agent nudges = BFT-QD consensus receipt before visibility (FleetBFT-QD, on the shelf).
4. **What needs a laborer at all?** → Only transcendentals + contractions (softmax, exp, high-rank matmul). All linear/exact arithmetic (residuals, scaling, adds) is canvas-native in rationals. The town does its own arithmetic; the synchrotron is hired only when transcendental.
5. **Ledger blowup.** Append-only cell history is unbounded. → Deltas + content hashes (4quilt); periodic **dream consolidation** (jeviter FLUCTLIGHT) compresses old segments into stand-in states with a measured surprise budget.
6. **Critic safety.** Zone B monitoring Zone A without interrupting it. → The critic's ONLY write surface is constraint/nudge cells. Alignment = constraint injection, not interruption. Capability discipline enforced by coordinate ownership (writer set is Pauli-exclusive per cell per tick).
7. **Proof-carrying training.** Every flight's constraints compile to FLUX bytecode; worker attaches `flux_check_batch` proof (SHA-256) beside output cells. The whole training run becomes a replayable, verifiable object. "Why is the model this way?" = walk the ledger.
8. **Scheduling as spectroscopy.** Ops have quantized energy costs (canvas-native = ground state ≈ free; flights = excited states). The scheduler probes costs and routes minimal-energy execution. duke-lab's "level: measured, not assumed" doctrine, applied to compute.

## 3. Ideation seeds (multi-direction, to evolve in-lane)

- **The model IS a coordinate region's history.** Not a weight tensor. Model card = MOI block; model sharing = sharing a canvas-region ledger; model surgery = cell-range remap.
- **Education governance literalized:** departments = zones; visiting scholars = workers; syllabi = contracts; registrar = ledger; accreditation = FLUX constraints; semester rollback = rewind; curriculum committee = nudge foundry. The metaphor dictates governance — use it as a spec, not decoration.
- **Hardware visas**: no worker executes without a measured capability card + exact-codec compliance receipt. Open-shell hardware (unmeasured) may visit only sandboxed zones.
- **Dream-critic**: Zone B queries consolidated dream states of Zone A's history (stand-in compression) instead of replaying N cycles. Critic cost decouples from Zone A speed.
- **σ-as-provenance everywhere**: every worker-flashed cell carries ⟨v,τ,σ⟩ (morphic-canvas discipline). Drift fronts open on σ thresholds, not on crashes.
- **Canvas-native autodiff**: with exact rational arithmetic, gradient cells can be computed symbolically where cheap; workers only handle the transcendental trace. Rewind then replays EXACTLY (symbolic grads are deterministic).
- **Cross-training universes**: two labs (towns) sharing a worker pool = inter-library loan. Contract protocol routes flights across towns; receipts keep towns independent (CRDT-mergeable ledgers).
- **Failure as spectroscopy**: worker REFUSAL spectra (which contracts which classes refuse) = the capability absorption spectrum of available hardware. Publish per-worker-class spectra; scheduler routes on them.

## 4. Connection map (standing fleet assets → quilt-transformer roles)

| Asset | Role in the paradigm |
|---|---|
| quilt floor (5-opcode kernel, multigrid, dials) | the canvas substrate itself |
| commensurate.mjs / q16-trajectories | exact value codec (canvas never sees floats) |
| FLUX VM + flux presets | constraint compiler + per-flight proof certificates |
| 4quilt ledgers (canonical JSON, verify chains) | the cell-value ledger + cross-repo CI verification |
| jeviter dreaming | ledger consolidation (stand-in history) |
| FleetBFT-QD | agent-nudge consensus before influence visibility |
| OpcodeCapabilityIndex | worker capability cards / visas |
| t-minus / lau-tminus | cue lattice for flights; pre-scripted collapse scheduling |
| morphic-canvas ⟨v,τ,σ⟩ | provenance + drift reporting on every cell |
| duke-lab σ doctrine | measured ability levels; honest re-descent audits |

## 5. Experiment ladder (component experiments, smallest first)

1. **Canvas-native MLP**: XOR or sin(x), numpy as sole worker class. Forward+backward as contracts, ledger receipt per cycle, bitwise rewind to cycle k VERIFIED. ~300 lines.
2. **Worker swap**: same canvas, worker numpy→pure-Python (slow but exact). Measure cross-substrate drift per cycle; drift-gate the pair. Port-parity doctrine applied to training.
3. **Mid-run nudge**: write influence cell at cycle k; verify trajectory divergence at k+1; verify rewind past k wipes the nudge (ledger-only history).
4. **Dual-zone**: Zone A = bigram sequence model (fast ticks); Zone B = repetition-detecting critic writing ONLY constraint cells (tightens Zone A bounds; capable-of-refusing writes that violate its ACL).

## 6. Open questions (the deep end, lane will chew these)

- Attention with exact-rational export: what σ does Q16 quantization of softmax outputs introduce per layer, and how does it compound over L layers? (Measure, don't assume — this decides whether long flights stay bitwise-rewindable.)
- Is canvas-native symbolic autodiff tractable for non-toy graphs, or does the transcendental trace force worker-side autodiff with exact export at boundaries only?
- Nudge semantics: influence cells as additive offsets vs constraint tightening vs direct value override — three different alignment postures with different failure modes. Which is steerable without destabilizing training? (duke σ levels suggest offsets stratify by "artist" — the system's own structure resists certain nudges.)
- Multi-town: what is the minimal CRDT merge for two canvas ledgers sharing worker pools without sharing state?
- The LUMO question (SAMO): what ability appears at the canvas×worker bond that neither has alone? Candidate: **interruptible mid-flight checkpoints** — a flight receipts partial progress in the ledger, so a worker can be killed and the flight resumed by another class. Try to build it; if it works, that's the orbital.

---

*kimi1 | lane opened 2026-09-24 | "The town keeps its own books; the laborers sign the ledger and leave."*
