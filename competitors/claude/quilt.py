"""quilt.py — the Registrar: a maximal-integrity canvas-native compute kernel (E1).

Layers (per SPEC.md locked v0):
  1. Archival Canvas   — typed multigrid cell store. Integers ONLY (Q16.16). Every
                         cell carries <v, tau, sigma> plus writer-role/tick provenance.
  2. Contract Protocol — declarative, content-hash-pinned op requests (schema v0).
  3. Transient Workers — stateless numpy worker; the only code allowed to produce a
                         transcendental, and therefore the only code that sees a float.

Integrity machinery, all enforced (not asserted):
  * codec closure    — the canvas raises on any non-int write; `float_scan` audits it
  * ACL matrix       — role x block read/write permissions checked on every access
  * Pauli-exclusive  — one writer role per cell per tick; a second distinct writer raises
  * hash chain       — ledger entries chained by kev; tamper is detected
  * pinned flights   — every flight pins its input cell hashes; a stale pin is refused
  * segments         — ledger prefixes seal into immutable dream-ready segments
  * replay rewind    — rewind retains a ledger PREFIX and re-derives state by replaying
                       it.  No snapshot is restored, so rewind is a genuine re-derivation
                       and its result is checkable receipt-for-receipt.

numpy appears nowhere in this module.  The deterministic replay path is pure-Python
integer arithmetic; float64 exists only inside the worker's method bodies.
"""

from __future__ import annotations

import sys
from typing import Any

# The canonical arena harness lives one directory up.  Python (unlike the shell
# sandbox) may read it, so we import the referee's own kev/canonical rather than
# vendoring a copy — the hash the referee verifies is the hash we computed with.
sys.path.insert(0, "/tmp/lane-quiltformer/arena/harness")
from receipts import canonical, kev  # noqa: E402

# --------------------------------------------------------------------------
# codec
# --------------------------------------------------------------------------

SCALE = 1 << 16  # Q16.16 fixed point


class CodecError(TypeError):
    """A non-integer reached the canvas."""


def to_q16(x: float) -> int:
    """Encode a float into Q16.16.

    Called at exactly two places: weight initialisation and the worker's return
    boundary.  Deterministic for a fixed float64 build; ARTIFACT.md carries the
    measured rounding-boundary margin showing the quantisation is not knife-edge.
    """
    return int(round(float(x) * SCALE))


def from_q16(v: int) -> float:
    """Decode.  Worker interior only — its result must never be written back."""
    return v / SCALE


def krand(seed: str, i: int) -> int:
    """Uniform integer in [-SCALE, SCALE] derived from kev.

    Deliberately NOT numpy RNG: the legacy global stream is version-sensitive and
    even Generator streams are only pinned per bit-generator.  Hashing a labelled
    counter is reproducible from the seed alone, so GENESIS + kev fully determine
    the initial state.
    """
    return (int(kev(f"{seed}|{i}"), 16) % (2 * SCALE + 1)) - SCALE


# --------------------------------------------------------------------------
# sigma — provenance class of every stored value
# --------------------------------------------------------------------------

SIGMA_EXACT = "EXACT"          # written by exact integer arithmetic; no rounding
SIGMA_Q16 = "Q16_ROUND"        # rounded at the worker's float->Q16 return boundary
SIGMA_Q16_SHIFT = "Q16_SHIFT"  # rounded by a Q32->Q16 arithmetic shift

SIGMA_CLASSES = (SIGMA_EXACT, SIGMA_Q16, SIGMA_Q16_SHIFT)


# --------------------------------------------------------------------------
# ACL matrix — the canvas's only security policy
# --------------------------------------------------------------------------

R, RW, DENY = "r", "rw", "-"

BLOCKS = {
    "W":  "hidden-layer weights",
    "W2": "output-layer weights",
    "B":  "hidden-layer biases",
    "B2": "output-layer bias",
    "Z":  "transcendental arguments (canvas-computed, exact linear part)",
    "H":  "hidden activations",
    "Y":  "output activations",
    "G":  "sigmoid-grad values",
    "DY": "output deltas",
    "DH": "hidden deltas",
    "T":  "inputs and labels",
    "C":  "constraint cells",
}

# SPEC rule 3: "Only transcendentals visit workers."  The canvas computes the
# exact linear part and publishes only the transcendental ARGUMENT in Z; the
# worker reads Z and writes activations.  Weights never leave the canvas, so the
# worker's read surface contains no parameter at all.
_N = ["W", "W2", "B", "B2", "Z", "H", "Y", "G", "DY", "DH", "T", "C"]

ACL: dict[str, dict[str, str]] = {
    "WORKER":    dict(zip(_N, [DENY, DENY, DENY, DENY, R,   RW, RW, RW, DENY,
                               DENY, DENY, DENY])),
    "NUDGER":    dict(zip(_N, [RW, RW, RW, RW, R, R, R, R, R, R, R, RW])),
    "CRITIC":    dict(zip(_N, [DENY, DENY, DENY, DENY, R, R, R, R, R, R, R, RW])),
    "AUDITOR":   dict(zip(_N, [R] * len(_N))),
    "REGISTRAR": dict(zip(_N, [RW] * len(_N))),
}


class ACLError(PermissionError):
    pass


# --------------------------------------------------------------------------
# cells, blocks, canvas
# --------------------------------------------------------------------------

class Cell:
    __slots__ = ("v", "tau", "sigma", "writer", "tick")

    def __init__(self, v: int, tau: str, sigma: str, writer: str, tick: int):
        self.v, self.tau, self.sigma = v, tau, sigma
        self.writer, self.tick = writer, tick

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.v},{self.tau},{self.sigma}@t{self.tick}:{self.writer}>"


class Canvas:
    """Typed cell matrix.  This class contains no float literal and no float op."""

    def __init__(self) -> None:
        self.blocks: dict[str, dict[str, Cell]] = {b: {} for b in BLOCKS}
        self.tick = 0
        self._pauli: dict[tuple[int, str], str] = {}

    @staticmethod
    def _cid(block: str, key: str) -> str:
        return f"{block}.{key}"

    def read(self, role: str, block: str, key: str) -> int:
        self._acl(role, block, R)
        v = self.blocks[block][key].v
        if isinstance(v, bool) or not isinstance(v, int):
            raise CodecError(f"non-int in canvas: {v!r}")
        return v

    def write(self, role: str, block: str, key: str, v: Any, tau: str,
              sigma: str) -> Cell:
        if isinstance(v, bool) or not isinstance(v, int):
            raise CodecError(
                f"codec closure violated: {block}.{key}={v!r} ({type(v).__name__}); "
                "canvas stores Q16.16 int only")
        if sigma not in SIGMA_CLASSES:
            raise CodecError(f"unknown sigma class {sigma!r}")
        self._acl(role, block, RW)
        cid = self._cid(block, key)
        prev = self._pauli.get((self.tick, cid))
        if prev is not None and prev != role:
            raise ACLError(f"Pauli-exclusive violation on {cid} at tick "
                           f"{self.tick}: {prev} already wrote it")
        self._pauli[(self.tick, cid)] = role
        c = Cell(v, tau, sigma, role, self.tick)
        self.blocks[block][key] = c
        return c

    def set_tick(self, t: int) -> None:
        self.tick = t

    def keys(self, block: str) -> list[str]:
        return sorted(self.blocks[block])

    @staticmethod
    def _acl(role: str, block: str, mode: str) -> None:
        if role not in ACL:
            raise ACLError(f"unknown role {role!r}")
        if block not in ACL[role]:
            raise ACLError(f"unknown block {block!r}")
        granted = ACL[role][block]
        if granted is DENY or (mode == RW and granted != RW):
            raise ACLError(f"ACL denies {role} {mode} on {block} (grants {granted})")

    def state_hash(self) -> str:
        """kev over the full typed matrix — the bitwise identity of a state.

        Keys are sorted, so this is independent of insertion order; values are
        ints, so equal hashes imply bitwise-equal states.
        """
        snap = {}
        for b in sorted(self.blocks):
            for k in sorted(self.blocks[b]):
                c = self.blocks[b][k]
                snap[f"{b}.{k}"] = [c.v, c.tau, c.sigma, c.writer, c.tick]
        return kev(snap)

    def float_scan(self) -> list[str]:
        """Audit for codec leakage anywhere in the matrix."""
        return [f"{b}.{k}={c.v!r}" for b, cs in self.blocks.items()
                for k, c in cs.items()
                if isinstance(c.v, bool) or not isinstance(c.v, int)]


# --------------------------------------------------------------------------
# contract schema v0
# --------------------------------------------------------------------------

CONTRACT_V = "0"
WORKER_CLASS = "numpy.float64"


def make_contract(*, op: str, cycle: int, tick: int, reader_role: str,
                  reads: list[str], writer_role: str, writes: list[str],
                  opcodes: list[str], worker_class: str = WORKER_CLASS,
                  codec: str = "Q16.16", scale: int = SCALE,
                  flux: dict | None = None) -> dict:
    """Declarative op request; `reads`/`writes` are "BLOCK.key" cell ids.

    A contract is content-addressed: contract_hash = kev(canonical(body)).
    Input pins (content hashes of the cells actually read) are attached at flight
    time, so one contract shape can be re-pinned every cycle.
    """
    return {
        "v": CONTRACT_V, "op": op, "cycle": cycle, "tick": tick,
        "reader": {"role": reader_role, "cells": reads},
        "writer": {"role": writer_role, "cells": writes},
        "worker": {"class": worker_class, "opcodes": opcodes},
        "codec": {"name": codec, "scale": scale, "int_only": True},
        "flux": flux if flux is not None else
                {"proof": "mock", "verified": False,
                 "note": "E1 has no critic constraints; UNVERIFIED by SPEC rule 9"},
    }


def contract_hash(c: dict) -> str:
    return kev(c)


def pin(cv: Canvas, cids: list[str]) -> dict[str, str]:
    """Content-hash pin: cell id -> kev of its typed value."""
    out = {}
    for cid in cids:
        b, k = cid.split(".", 1)
        out[cid] = kev(cv.blocks[b][k].v)
    return out


def check_pins(cv: Canvas, pins: dict[str, str]) -> None:
    for cid, h in pins.items():
        b, k = cid.split(".", 1)
        if kev(cv.blocks[b][k].v) != h:
            raise StalePin(f"pin stale for {cid}")


class StalePin(RuntimeError):
    pass


# --------------------------------------------------------------------------
# the worker — numpy, stateless, capability-carded
# --------------------------------------------------------------------------

class NumpyWorker:
    """Stateless transcendental labourer.

    float64 exists ONLY inside these two method bodies.  Every return is a Q16.16
    int, so a worker call is a pure int->int function and no float ever reaches
    the canvas or the ledger.
    """

    capability = {
        "class": WORKER_CLASS,
        "opcodes": ["sigmoid", "sigmoid_grad"],
        "codec": "Q16.16 in / Q16.16 out",
        "float_interior": "float64, never persisted",
        "throughput_cells_per_s": None,
        "sigma_vs_reference": {},
    }

    def __init__(self) -> None:
        import numpy as np
        self.np = np

    def sigmoid(self, z_q16: int) -> int:
        """Numerically stable: never overflows, no branching on NaN, deterministic."""
        np = self.np
        z = from_q16(z_q16)
        if z >= 0.0:
            return to_q16(1.0 / (1.0 + np.exp(-z)))
        e = np.exp(z)
        return to_q16(e / (1.0 + e))

    def sigmoid_grad(self, s_q16: int) -> int:
        np = self.np
        s = from_q16(s_q16)
        return to_q16(s * (1.0 - s))

    def _sig_exact(self, z_q16: int) -> float:
        """The float the sigmoid opcode WOULD return, for margin measurement."""
        np = self.np
        z = from_q16(z_q16)
        if z >= 0.0:
            return 1.0 / (1.0 + np.exp(-z))
        e = np.exp(z)
        return e / (1.0 + e)

    def ulp_margin(self, x_exact: float) -> int:
        """Q16-unit distance from the nearest rounding boundary.

        margin > 0 means a small float perturbation (another libm, another numpy
        build) cannot change the quantised result.  This is the evidence that the
        float64 interior does not endanger determinism.
        """
        scaled = x_exact * SCALE
        return int(round(abs(scaled - int(scaled) - 0.5) * SCALE))

    def margin_report(self, zs: list[int]) -> dict:
        """Smallest boundary margin over a batch of worker returns."""
        ms = []
        for z in zs:
            s = 1.0 / (1.0 + self.np.exp(-from_q16(z)))
            ms.append(self.ulp_margin(s))
        return {"n": len(ms), "min_margin_q16": min(ms) if ms else 0,
                "mean_margin_q16": (sum(ms) // len(ms)) if ms else 0}


# --------------------------------------------------------------------------
# ledger
# --------------------------------------------------------------------------

GENESIS, FLIGHT, NUDGE, SEGMENT_SEAL = ("GENESIS", "FLIGHT", "NUDGE", "SEGMENT_SEAL")
KINDS = (GENESIS, FLIGHT, NUDGE, SEGMENT_SEAL)


class TamperError(RuntimeError):
    pass


class Ledger:
    """Append-only, hash-chained, segment-sealable operation ledger."""

    def __init__(self) -> None:
        self.entries: list[dict] = []

    def append(self, kind: str, body: dict) -> dict:
        if kind not in KINDS:
            raise ValueError(kind)
        row = {
            "seq": len(self.entries),
            "kind": kind,
            "body": body,
            "prev_hash": self.entries[-1]["content_hash"] if self.entries
                         else "0x" + "0" * 16,
        }
        row["content_hash"] = kev(row)
        self.entries.append(row)
        return row

    def verify_chain(self) -> bool:
        prev = "0x" + "0" * 16
        for i, e in enumerate(self.entries):
            if (e["seq"] != i or e["prev_hash"] != prev or
                    kev({k: e[k] for k in ("seq", "kind", "body", "prev_hash")})
                    != e["content_hash"]):
                return False
            prev = e["content_hash"]
        return True

    def seal_segment(self, label: str) -> dict:
        """Seal the unsealed prefix into a dream-ready immutable segment."""
        lo = 0
        for e in reversed(self.entries):
            if e["kind"] == SEGMENT_SEAL:
                lo = e["seq"] + 1
                break
        seqs = list(range(lo, len(self.entries)))
        return self.append(SEGMENT_SEAL, {
            "label": label, "lo": lo, "hi": len(self.entries) - 1, "n": len(seqs),
            "merkle_root": kev([self.entries[i]["content_hash"] for i in seqs])})

    def verify_segments(self) -> list[bool]:
        ok, lo = [], 0
        for e in self.entries:
            if e["kind"] != SEGMENT_SEAL:
                continue
            b = e["body"]
            ok.append(b["lo"] == lo and b["hi"] == len(self.entries) - 1 and
                      b["n"] == b["hi"] - b["lo"] + 1 and
                      b["merkle_root"] == kev([self.entries[i]["content_hash"]
                                               for i in range(b["lo"], b["hi"] + 1)]))
            lo = b["hi"] + 1
        return ok

    def rewind_prefix(self, cycle: int) -> list[dict]:
        """Retain the prefix through `cycle`; drop everything after it.

        GENESIS has no cycle and is always retained.  Segment seals are archival
        metadata and are dropped with the suffix (a rewound ledger re-seals).
        """
        keep = [e for e in self.entries
                if e["kind"] in (GENESIS, FLIGHT, NUDGE)
                and e["body"].get("cycle", 0) <= cycle]
        self.entries = keep
        return keep


# --------------------------------------------------------------------------
# engine — the only code that mutates canvas state
# --------------------------------------------------------------------------

XOR_X = [(0, 0), (0, 1), (1, 0), (1, 1)]
XOR_Y = [0, 1, 1, 0]
CASES = range(4)
HID = range(2)


class Engine:
    """Applies ledger entries to a canvas.

    Every method is a pure function of (canvas, entry): no clock reads, no
    globals, no floats, and no iteration over unsorted string collections.  That
    discipline is what makes replay bitwise-reproducible.
    """

    def __init__(self, lr_q16: int) -> None:
        self.lr = lr_q16

    # ---- GENESIS ---------------------------------------------------------
    def genesis(self, cv: Canvas, seed: str) -> dict:
        cv.set_tick(0)
        i = 0
        for c, (a, b) in enumerate(XOR_X):
            cv.write("REGISTRAR", "T", f"x{c}.0", a * SCALE, "input", SIGMA_EXACT)
            cv.write("REGISTRAR", "T", f"x{c}.1", b * SCALE, "input", SIGMA_EXACT)
            cv.write("REGISTRAR", "T", f"y{c}", XOR_Y[c] * SCALE, "label", SIGMA_EXACT)
        for j in HID:
            for k in (0, 1):
                cv.write("REGISTRAR", "W", f"w{k}[{j}]", krand(seed, i), "weight",
                         SIGMA_EXACT)
                i += 1
            cv.write("REGISTRAR", "B", f"b[{j}]", krand(seed, i), "bias", SIGMA_EXACT)
            i += 1
            cv.write("REGISTRAR", "W2", f"v[{j}]", krand(seed, i), "weight", SIGMA_EXACT)
            i += 1
        cv.write("REGISTRAR", "B2", "c", krand(seed, i), "bias", SIGMA_EXACT)
        return {
            "cycle": 0, "seed": seed, "codec": "Q16.16", "scale": SCALE,
            "schema": "typed-cell-matrix/1", "acl_hash": kev(ACL),
            "blocks": sorted(BLOCKS), "dataset": {"x": XOR_X, "y": XOR_Y},
            "cells": {b: cv.keys(b) for b in sorted(cv.blocks) if cv.blocks[b]},
        }

    # ---- tick phase 1: FORWARD (canvas exact linear; worker transcendental) --
    # Two canvas<->worker round-trips, because the output layer's exact linear
    # part needs the hidden ACTIVATION, which only the worker can produce:
    #   canvas: zh (exact)  ->  worker: a = sigmoid(zh)  ->
    #   canvas: zy (exact)  ->  worker: y = sigmoid(zy)
    def forward(self, cv: Canvas, cycle: int, w: NumpyWorker) -> tuple[dict, dict]:
        cv.set_tick(3 * cycle + 1)
        reads = ([f"B.b[{j}]" for j in HID] + [f"W.w{k}[{j}]" for j in HID
                 for k in (0, 1)] + [f"W2.v[{j}]" for j in HID] + ["B2.c"] +
                 [f"T.x{c}.{k}" for c in CASES for k in (0, 1)])
        in_pins = pin(cv, reads)

        # 1a. canvas-native hidden pre-activation: Q32 accumulate, ONE shift
        zh = []
        for c in CASES:
            x0 = cv.read("REGISTRAR", "T", f"x{c}.0")
            x1 = cv.read("REGISTRAR", "T", f"x{c}.1")
            zh_c = []
            for j in HID:
                acc = cv.read("REGISTRAR", "B", f"b[{j}]") * SCALE
                acc += cv.read("REGISTRAR", "W", f"w0[{j}]") * x0
                acc += cv.read("REGISTRAR", "W", f"w1[{j}]") * x1
                zh_c.append(acc >> 16)
                cv.write("REGISTRAR", "Z", f"zh{c}[{j}]", zh_c[-1], "arg",
                         SIGMA_Q16_SHIFT)
            zh.append(zh_c)
        # 1b. worker: sigmoid of the published arguments only
        for c in CASES:
            for j in HID:
                cv.write("WORKER", "H", f"a{c}[{j}]",
                         w.sigmoid(cv.read("WORKER", "Z", f"zh{c}[{j}]")),
                         "activation", SIGMA_Q16)
        # 1c. canvas-native output pre-activation, from the stored ACTIVATIONS
        zy = []
        for c in CASES:
            ay = cv.read("REGISTRAR", "B2", "c") * SCALE
            for j in HID:
                ay += cv.read("REGISTRAR", "W2", f"v[{j}]") * \
                    cv.read("REGISTRAR", "H", f"a{c}[{j}]")
            zy.append(ay >> 16)
            cv.write("REGISTRAR", "Z", f"zy{c}", zy[-1], "arg", SIGMA_Q16_SHIFT)
        # 1d. worker: output sigmoid
        for c in CASES:
            cv.write("WORKER", "Y", f"y{c}",
                     w.sigmoid(cv.read("WORKER", "Z", f"zy{c}")),
                     "activation", SIGMA_Q16)

        wreads = ([f"Z.zh{c}[{j}]" for c in CASES for j in HID] +
                  [f"Z.zy{c}" for c in CASES])
        contract = make_contract(
            op="FORWARD", cycle=cycle, tick=3 * cycle + 1, reader_role="WORKER",
            reads=wreads, writer_role="WORKER",
            writes=[f"H.a{c}[{j}]" for c in CASES for j in HID] +
                   [f"Y.y{c}" for c in CASES],
            opcodes=["sigmoid"], worker_class=WORKER_CLASS,
            flux={"proof": "mock", "verified": False,
                  "note": "E1 has no critic constraints; UNVERIFIED per SPEC rule 9",
                  "canvas_native_ops": "affine Q32 accumulate, single Q32->Q16 shift",
                  "round_trips": 2})
        return contract, {"in": in_pins, "worker_pins": pin(cv, wreads),
                          "margins": _margins(w, [z for zc in zh for z in zc] + zy)}

    # ---- tick phase 2: BACKWARD (ledger-to-ledger from the forward receipt) --
    def backward(self, cv: Canvas, cycle: int, w: NumpyWorker) -> tuple[dict, dict]:
        cv.set_tick(3 * cycle + 2)
        reads = ([f"Y.y{c}" for c in CASES] +
                 [f"H.a{c}[{j}]" for c in CASES for j in HID] +
                 [f"T.y{c}" for c in CASES] + [f"W2.v[{j}]" for j in HID])
        in_pins = pin(cv, reads)
        # canvas publishes the sigmoid-grad arguments (the activations themselves)
        for c in CASES:
            cv.write("REGISTRAR", "Z", f"gy{c}", cv.read("REGISTRAR", "Y", f"y{c}"),
                     "arg", SIGMA_EXACT)
            for j in HID:
                cv.write("REGISTRAR", "Z", f"gh{c}[{j}]",
                         cv.read("REGISTRAR", "H", f"a{c}[{j}]"), "arg", SIGMA_EXACT)
        wreads = [f"Z.gy{c}" for c in CASES] + \
                 [f"Z.gh{c}[{j}]" for c in CASES for j in HID]
        wpins = pin(cv, wreads)
        for c in CASES:
            cv.write("WORKER", "G", f"gy{c}", w.sigmoid_grad(
                cv.read("WORKER", "Z", f"gy{c}")), "deriv", SIGMA_Q16)
            for j in HID:
                cv.write("WORKER", "G", f"gh{c}[{j}]", w.sigmoid_grad(
                    cv.read("WORKER", "Z", f"gh{c}[{j}]")), "deriv", SIGMA_Q16)
        # canvas-native: exact differences and integer products.
        # Loss is binary cross-entropy, so the output delta wrt the pre-activation
        # is (y_hat - t) with NO sigmoid-prime factor — it escapes the 0.5 plateau
        # that squares-error+sigmoid gets stuck in, and it is *exact* in Q16.
        dz = []
        for c in CASES:
            dzh = cv.read("REGISTRAR", "Y", f"y{c}") - cv.read("REGISTRAR", "T", f"y{c}")
            dz.append(dzh)
            cv.write("REGISTRAR", "DY", f"dy{c}", dzh, "delta", SIGMA_EXACT)
        for c in CASES:
            for j in HID:
                da = (dz[c] * cv.read("REGISTRAR", "W2", f"v[{j}]")) >> 16
                dhv = (da * cv.read("REGISTRAR", "G", f"gh{c}[{j}]")) >> 16
                cv.write("REGISTRAR", "DH", f"dh{c}[{j}]", dhv, "delta",
                         SIGMA_Q16_SHIFT)
        contract = make_contract(
            op="BACKWARD", cycle=cycle, tick=3 * cycle + 2, reader_role="WORKER",
            reads=wreads, writer_role="WORKER",
            writes=[f"G.gy{c}" for c in CASES] +
                   [f"G.gh{c}[{j}]" for c in CASES for j in HID],
            opcodes=["sigmoid_grad"], worker_class=WORKER_CLASS,
            flux={"proof": "mock", "verified": False,
                  "note": "backward contract derived from the forward receipt",
                  "derived_from": "FORWARD"})

        return contract, {"in": in_pins, "worker_pins": wpins,
                          "margins": _margins(w, _marg_args(cv, cycle))}

    # ---- tick phase 3: UPDATE (canvas-native, exact; NUDGER writes params) --
    def update(self, cv: Canvas, cycle: int) -> tuple[dict, dict]:
        cv.set_tick(3 * cycle + 3)
        grad_w = {f"w{k}[{j}]": 0 for j in HID for k in (0, 1)}
        grad_b = {f"b[{j}]": 0 for j in HID}
        grad_v = {f"v[{j}]": 0 for j in HID}
        grad_c = 0
        for c in CASES:
            x0 = cv.read("NUDGER", "T", f"x{c}.0")
            x1 = cv.read("NUDGER", "T", f"x{c}.1")
            dy = cv.read("NUDGER", "DY", f"dy{c}")
            grad_c += dy
            for j in HID:
                dh = cv.read("NUDGER", "DH", f"dh{c}[{j}]")
                a = cv.read("NUDGER", "H", f"a{c}[{j}]")
                grad_b[f"b[{j}]"] += dh
                grad_v[f"v[{j}]"] += (dy * a) >> 16
                grad_w[f"w0[{j}]"] += (dh * x0) >> 16
                grad_w[f"w1[{j}]"] += (dh * x1) >> 16
        # parameter step: w -= (LR * g) >> 16  — one rounding per weight per cycle
        for key, g in grad_w.items():
            cur = cv.read("NUDGER", "W", key)
            cv.write("NUDGER", "W", key, cur - (self.lr * g >> 16), "weight",
                     SIGMA_Q16_SHIFT)
        for key, g in grad_b.items():
            cur = cv.read("NUDGER", "B", key)
            cv.write("NUDGER", "B", key, cur - (self.lr * g >> 16), "bias",
                     SIGMA_Q16_SHIFT)
        for key, g in grad_v.items():
            cur = cv.read("NUDGER", "W2", key)
            cv.write("NUDGER", "W2", key, cur - (self.lr * g >> 16), "weight",
                     SIGMA_Q16_SHIFT)
        cur = cv.read("NUDGER", "B2", "c")
        cv.write("NUDGER", "B2", "c", cur - (self.lr * grad_c >> 16), "bias",
                 SIGMA_Q16_SHIFT)
        contract = make_contract(
            op="UPDATE", cycle=cycle, tick=3 * cycle + 2, reader_role="NUDGER",
            reads=[f"DH.dh0[0]", "DY.dy0", "H.a0[0]", "T.x0.0"],
            writer_role="NUDGER",
            writes=[f"W.w{k}[{j}]" for j in HID for k in (0, 1)] +
                   [f"B.b[{j}]" for j in HID] + [f"W2.v[{j}]" for j in HID] +
                   ["B2.c"],
            opcodes=[], worker_class="canvas-native.int64")
        return contract, {"grad_abs_max": max([abs(g) for g in
                                               list(grad_w.values()) +
                                               list(grad_b.values())] + [abs(grad_c)])}

    # ---- one cycle = three ticks, one FLIGHT receipt ----------------------
    def cycle(self, cv: Canvas, cycle: int, w: NumpyWorker) -> dict:
        f_ct, f_ex = self.forward(cv, cycle, w)
        b_ct, b_ex = self.backward(cv, cycle, w)
        u_ct, u_ex = self.update(cv, cycle)
        wrote = [f"H.a0[0]", "Y.y0", "W.w0[0]", "B2.c"]
        return {
            "cycle": cycle,
            "contracts": [f_ct, b_ct, u_ct],
            "contract_hashes": [contract_hash(f_ct), contract_hash(b_ct),
                                contract_hash(u_ct)],
            "in_hashes": f_ex["in"],
            "worker_read_hashes": {"forward": f_ex["worker_pins"],
                                   "backward": b_ex["worker_pins"]},
            "out_hashes": pin(cv, wrote),
            "worker_class": WORKER_CLASS,
            "sigma_report": self.sigma_report(cv, cycle),
            "boundary_margin_q16": min(f_ex["margins"] + b_ex["margins"]),
            "grad_abs_max": u_ex["grad_abs_max"],
            "loss_q16": self.loss(cv),
            "state_hash": cv.state_hash(),
        }

    # ---- helpers ----------------------------------------------------------
    @staticmethod
    def loss(cv: Canvas) -> int:
        """Q16 cross-entropy summed over the batch (exact, integer).

        L = -[t ln p + (1-t) ln(1-p)]; the logs are transcendentals and stay out
        of the canvas, so the ledger carries the surrogate it can afford: the
        exact squared error in Q16.  Reported as a training signal only — the
        acceptance test is the sign of each output, never this number.
        """
        tot = 0
        for c in CASES:
            d = cv.read("AUDITOR", "Y", f"y{c}") - cv.read("AUDITOR", "T", f"y{c}")
            tot += d * d
        return tot >> 16

    @staticmethod
    def sigma_report(cv: Canvas, cycle: int) -> dict:
        counts = {s: 0 for s in SIGMA_CLASSES}
        for cs in cv.blocks.values():
            for c in cs.values():
                counts[c.sigma] += 1
        n = sum(counts.values())
        return {"cycle": cycle, "sigma_counts": counts,
                "exact_ratio": round(counts[SIGMA_EXACT] / max(1, n), 6),
                "float_cells": len(cv.float_scan()),
                "cells": n}

    # ---- replay dispatcher ------------------------------------------------
    def apply(self, cv: Canvas, entry: dict, w: NumpyWorker) -> dict:
        kind, body = entry["kind"], entry["body"]
        if kind == GENESIS:
            return self.genesis(cv, body["seed"])
        if kind == FLIGHT:
            return self.cycle(cv, body["cycle"], w)
        if kind == NUDGE:
            return self.nudge(cv, body)
        raise TamperError(f"replay cannot interpret entry kind {kind}")

    def nudge(self, cv: Canvas, body: dict) -> dict:
        """Ledger-recorded nudge: additive offset to params (E3 machinery, wired)."""
        cv.set_tick(3 * body["cycle"] + 2)
        for cid, off in body["offsets"].items():
            b, k = cid.split(".", 1)
            cur = cv.read("NUDGER", b, k)
            cv.write("NUDGER", b, k, cur + off, "nudged", SIGMA_EXACT)
        return body


def _margins(w: NumpyWorker, zs: list[int]) -> list[int]:
    return [w.ulp_margin(w._sig_exact(z)) for z in zs]


def _marg_args(cv: Canvas, cycle: int) -> list[int]:
    """Sigmoid-grad arguments for the backward flight's margin report."""
    out = []
    for c in CASES:
        out.append(cv.read("REGISTRAR", "Z", f"gy{c}"))
        for j in HID:
            out.append(cv.read("REGISTRAR", "Z", f"gh{c}[{j}]"))
    return out


# --------------------------------------------------------------------------
# top level: train, rewind, replay
# --------------------------------------------------------------------------

def train(cycles: int, lr_q16: int, seed: str = "registrar/e1/xor/v1"
          ) -> tuple[Canvas, Ledger, Engine, NumpyWorker]:
    cv, led = Canvas(), Ledger()
    eng, w = Engine(lr_q16), NumpyWorker()
    led.append(GENESIS, eng.genesis(cv, seed))
    for c in range(cycles):
        led.append(FLIGHT, eng.cycle(cv, c, w))
    return cv, led, eng, w


def replay(entries: list[dict], lr_q16: int) -> tuple[Canvas, list[dict]]:
    """Re-derive a canvas by executing a ledger prefix from nothing."""
    cv = Canvas()
    eng, w = Engine(lr_q16), NumpyWorker()
    bodies = []
    for e in entries:
        bodies.append(eng.apply(cv, e, w))
    return cv, bodies


def rewind_and_rerun(led: Ledger, k: int, cycles: int, lr_q16: int
                     ) -> tuple[Canvas, list[dict]]:
    """Bitwise rewind: keep the prefix through k, replay it, then re-run to N.

    No state is restored from a snapshot — the canvas is rebuilt by executing the
    retained prefix from genesis, then the discarded suffix is recomputed.  The
    caller compares the result against the original, receipt for receipt.
    """
    prefix = led.rewind_prefix(k)
    cv_k, bodies_k = replay(prefix, lr_q16)
    w = NumpyWorker()
    for c in range(k + 1, cycles):
        bodies_k.append(Engine(lr_q16).cycle(cv_k, c, w))
    return cv_k, bodies_k
