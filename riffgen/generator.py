"""Chord-aware pitch-sequence generator.

Design notes
------------
* No rhythm: every chord segment is filled with an even grid of notes (placeholder
  timing). The producer re-times them.
* Every random decision comes from a pre-drawn table, so the same seed always gives
  the same riff, and raising `outside` mostly adds tension notes to the same skeleton.
* Tension notes only sit on odd slots (the weak positions of an even grid), and the
  "approach" kind is always followed by an anchor so it resolves.
* Motif reuse: with probability `strategy.repeat` a chord reuses the first chord's
  random draws, i.e. the same shape re-realised on the new chord's tones.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .models import Candidate, GenNote
from .scoring import annotate, note_clash

K = 8  # uniform draws per slot
R_TENSION, R_KIND, R_ROLE, R_ANCHOR, R_LEAP, R_STEP, R_DIR, R_PICK = range(K)

SWEEP_LEVELS = (0.0, 0.25, 0.5, 0.75, 1.0)
TENSION_KINDS = ("approach", "modal", "chromatic")


@dataclass(frozen=True)
class Strategy:
    name: str
    description: str
    anchor_bias: float  # P(anchor) among non-tension slots, rest are scale-step colours
    anchor_mode: str  # root | up | down | arp | pedal | random
    step_max: int  # max scale steps for colour notes
    leap: float  # P(octave leap) when placing an anchor
    repeat: float  # P(a chord reuses the first chord's shape)
    tension_max: float  # P(tension) on eligible slots when outside == 1
    kinds: tuple  # multipliers for (approach, modal, chromatic)
    center: int  # preferred MIDI register centre


STRATEGIES = {
    s.name: s
    for s in [
        Strategy("ostinato", "root-heavy, repeating narrow line", 0.70, "root", 1, 0.05, 0.90, 0.45, (1.0, 1.2, 0.6), 45),
        Strategy("arpeggio", "line sweeping through the chord tones up/down", 0.80, "arp", 2, 0.00, 0.80, 0.45, (1.0, 0.8, 0.5), 52),
        Strategy("pedal", "root pedal + moving upper voice", 0.60, "pedal", 2, 0.10, 0.80, 0.45, (1.4, 1.0, 0.7), 47),
        Strategy("melodic", "melodic line flowing in scale steps", 0.45, "random", 3, 0.10, 0.50, 0.40, (1.0, 1.0, 0.8), 57),
        Strategy("angular", "angular line leaping between chord tones", 0.80, "random", 3, 0.55, 0.40, 0.50, (1.3, 1.0, 1.0), 52),
        Strategy("crawl", "chromatic/modal crawling line", 0.35, "root", 1, 0.00, 0.70, 0.60, (0.6, 1.3, 2.2), 47),
    ]
}


@dataclass
class Context:
    song: object
    chords: list
    key: object
    grid: float = 0.5  # beats per note (0.5 = eighth notes in x/4)
    lo: int = 40  # E2
    hi: int = 72  # C5
    loop: bool = True  # treat the progression as a loop (last chord leads to the first)
    gate: float = 0.9  # note length as a fraction of the grid step

    def slots_for(self, chord) -> int:
        step = self.song.ticks_per_beat * self.grid
        return max(1, int(round((chord.end - chord.start) / step)))


# ----------------------------------------------------------------- small helpers
def _clamp(x, a, b):
    return max(a, min(b, x))


def _occurrences(pc: int, lo: int, hi: int):
    return [p for p in range(lo, hi + 1) if p % 12 == pc]


def _place(pc, ref, hint, lo, hi, leap, r_leap, r_pick, window=None):
    """Pick the octave of `pc` relative to the previous pitch."""
    cands = _occurrences(pc, lo, hi)
    if hint in ("up", "down"):
        if window:  # keep sweeps inside a two-octave window, wrap at its edge
            inside = [p for p in cands if window[0] <= p <= window[1]]
            cands = inside or cands
        if hint == "up":
            up = [p for p in cands if p > ref]
            return min(up) if up else min(cands)
        dn = [p for p in cands if p < ref]
        return max(dn) if dn else max(cands)
    cands.sort(key=lambda p: (abs(p - ref), p))
    if leap and r_leap < leap and len(cands) > 1:
        far = [c for c in cands[1:] if abs(c - ref) <= 19]  # at most an octave + fifth
        if far:
            return far[int(r_pick * len(far))]
    return cands[0]


_ROOT_WEIGHTS = [0.50, 0.22, 0.18, 0.10, 0.06, 0.04, 0.04, 0.04]


def _pick_anchor(mode, tones, j, r):
    n = len(tones)
    if mode == "up":
        return tones[j % n], "up"
    if mode == "down":
        return tones[(-j) % n], "down"
    if mode == "root":
        w = _ROOT_WEIGHTS[:n]
        x, acc = r * sum(w), 0.0
        for idx, wi in enumerate(w):
            acc += wi
            if x < acc:
                return tones[idx], None
        return tones[0], None
    return tones[min(n - 1, int(r * n))], None


def _color_pool(chord, key, lo, hi, thr):
    tones, scale = set(chord.tones), key.scale
    return [
        p
        for p in range(lo, hi + 1)
        if p % 12 in tones or (p % 12 in scale and note_clash(p % 12, chord.tones, scale) <= thr)
    ]


def _color_step(ref, pool, d, strat):
    idx = min(range(len(pool)), key=lambda i: (abs(pool[i] - ref), pool[i]))
    r = d[R_STEP]
    size = min(1 if r < 0.65 else (2 if r < 0.90 else 3), strat.step_max)
    p_up = _clamp(0.5 - 0.035 * (ref - strat.center), 0.15, 0.85)
    direction = 1 if d[R_DIR] < p_up else -1
    j = _clamp(idx + direction * size, 0, len(pool) - 1)
    if pool[j] == ref:
        j = _clamp(idx - direction * size, 0, len(pool) - 1)
    return pool[j]


def _kind_weights(outside, strat):
    m = strat.kinds
    approach = 1.0 * m[0]
    modal = _clamp((outside - 0.20) / 0.30, 0, 1) * 0.9 * m[1]
    chromatic = _clamp((outside - 0.65) / 0.30, 0, 1) * 0.8 * m[2]
    return approach, modal, chromatic


def _plan_intents(N, d, strat, mode, p_t, weights, allow_last):
    intents = [None] * N
    total = sum(weights)
    for i in range(N):
        if i == 0:
            intents[i] = "root"
            continue
        if mode == "pedal" and i % 2 == 0:
            intents[i] = "pedal"
            continue
        if intents[i] is not None:  # forced by a preceding approach tone
            continue
        di = d[i]
        eligible = (i % 2 == 1) and (allow_last or i != N - 1)
        if eligible and di[R_TENSION] < p_t:
            x = di[R_KIND] * total
            if x < weights[0]:
                kind = "approach"
            elif x < weights[0] + weights[1]:
                kind = "modal"
            else:
                kind = "chromatic"
            intents[i] = kind
            if kind == "approach" and mode != "pedal" and i + 1 < N:
                intents[i + 1] = "anchor"
        else:
            intents[i] = "anchor" if di[R_ROLE] < strat.anchor_bias else "color"
    return intents


def _scan(flat, pos, step, loop):
    """Nearest non-None pitch before/after `pos` in the flattened sequence."""
    n = len(flat)
    for k in range(1, n):
        q = pos + step * k
        if not loop and not (0 <= q < n):
            return None
        v = flat[q % n]
        if v is not None:
            return v
    return None


# -------------------------------------------------------------------- generation
def build_candidate(ctx: Context, strat: Strategy, outside: float, seed: int,
                    index: int = 0, group: int = -1) -> Candidate:
    rng = random.Random(seed)
    chords, key = ctx.chords, ctx.key
    lo, hi = ctx.lo, ctx.hi
    scale = key.scale
    n_chords = len(chords)
    slots = [ctx.slots_for(c) for c in chords]
    width = max(slots)

    # All randomness is drawn up front, independent of `outside`. The tension gate
    # is stratified over the eligible (odd) slots, so raising `outside` adds tension
    # notes in even steps instead of leaving whole levels identical.
    own = []
    for _ in range(n_chords):
        rows = [[rng.random() for _ in range(K)] for _ in range(width)]
        elig = list(range(1, width, 2))
        if elig:
            order = list(range(len(elig)))
            rng.shuffle(order)
            for pos, i in enumerate(elig):
                rows[i][R_TENSION] = (order[pos] + rows[i][R_TENSION]) / len(elig)
        own.append([tuple(r) for r in rows])
    draws = [own[0] if (k > 0 and rng.random() < strat.repeat) else own[k] for k in range(n_chords)]

    mode = strat.anchor_mode
    if mode == "arp":
        mode = "up" if seed % 2 == 0 else "down"

    weights = _kind_weights(outside, strat)
    p_t = strat.tension_max * outside
    avoid_thr = 0.33 + 0.5 * outside
    center = _clamp(strat.center, lo, hi)

    intents, pitches = [], []
    ref = center
    upper = None

    # ---- pass 1: everything except tension notes
    for k, chord in enumerate(chords):
        N, d = slots[k], draws[k]
        its = _plan_intents(N, d, strat, mode, p_t, weights, ctx.loop or k < n_chords - 1)
        pool = _color_pool(chord, key, lo, hi, avoid_thr)
        ps = [None] * N
        pedal, j = None, 0

        for i, it in enumerate(its):
            if it in TENSION_KINDS:
                continue
            di = d[i]
            if mode == "pedal" and it in ("anchor", "color"):
                # upper voice stays at least a minor third above the pedal
                p_lo = _clamp(pedal + 3, lo, hi - 11)
                r_ref = upper if (upper is not None and upper >= p_lo) else _clamp(pedal + 12, p_lo, hi)
                p_pool = [q for q in pool if q >= p_lo] or pool
            else:
                p_lo, r_ref, p_pool = lo, ref, pool

            if it == "root":
                p = _place(chord.root, ref, None, lo, hi, 0, 1, 0)
                pedal = p
                j += 1
            elif it == "pedal":
                p = pedal
            elif it == "anchor":
                pc, hint = _pick_anchor(mode, chord.tones, j, di[R_ANCHOR])
                window = (max(lo, center - 12), min(hi, center + 12)) if hint else None
                p = _place(pc, r_ref, hint, p_lo, hi, strat.leap, di[R_LEAP], di[R_PICK], window)
                j += 1
            else:  # color
                p = _color_step(r_ref, p_pool, di, strat)

            ps[i] = p
            if it in ("root", "pedal"):
                ref = p
            elif mode == "pedal":
                upper = p
            else:
                ref = p

        intents.append(its)
        pitches.append(ps)

    # ---- pass 2: tension notes, placed relative to their (already fixed) neighbours
    seq = [(k, i) for k in range(n_chords) for i in range(slots[k])]
    flat = [pitches[k][i] for k, i in seq]

    for pos, (k, i) in enumerate(seq):
        kind = intents[k][i]
        if kind not in TENSION_KINDS:
            continue
        chord, d = chords[k], draws[k][i]
        prev = _scan(flat, pos, -1, ctx.loop)
        nxt = _scan(flat, pos, +1, ctx.loop)
        if prev is None:
            prev = center

        def pref(p, chord=chord):  # 0 = genuinely outside (not scale, not chord tone)
            return 0 if (p % 12 not in scale and p % 12 not in chord.tones) else 1

        if kind == "approach" and nxt is None:
            kind = "chromatic"

        p = None
        if kind == "approach":
            opts = [q for q in (nxt - 1, nxt + 1) if lo <= q <= hi]
            opts.sort(key=lambda q: (pref(q), abs(q - prev)))
            if len(opts) == 2 and pref(opts[0]) == pref(opts[1]):
                p = opts[0] if d[R_PICK] < 0.6 else opts[1]
            elif opts:
                p = opts[0]
            else:
                kind = "chromatic"

        if kind == "modal":
            pool_pcs = {(key.tonic + 1) % 12, (key.tonic + 6) % 12, (chord.root + 1) % 12, (chord.root + 6) % 12}
            if key.mode == "minor":
                pool_pcs.add((key.tonic + 11) % 12)
            else:
                pool_pcs.update({(key.tonic + 3) % 12, (key.tonic + 10) % 12})  # blue notes
            pool_pcs -= set(chord.tones)
            outside_pcs = {pc for pc in pool_pcs if pc not in scale}
            pool_pcs = outside_pcs or pool_pcs
            cands = sorted((q for q in range(lo, hi + 1) if q % 12 in pool_pcs), key=lambda q: (abs(q - prev), q))
            if cands:
                p = cands[0] if (d[R_PICK] < 0.65 or len(cands) == 1) else cands[1]
            else:
                kind = "chromatic"

        if kind == "chromatic":
            opts = [q for q in (prev - 1, prev + 1) if lo <= q <= hi]
            opts.sort(key=lambda q: (pref(q), q))
            if len(opts) == 2 and pref(opts[0]) == pref(opts[1]):
                p = opts[0] if d[R_PICK] < 0.5 else opts[1]
            else:
                p = opts[0]

        pitches[k][i] = p
        flat[pos] = p

    # ---- lay the notes on the placeholder grid
    notes = []
    for k, chord in enumerate(chords):
        span = chord.end - chord.start
        step = span / slots[k]
        for i in range(slots[k]):
            notes.append(
                GenNote(
                    pitch=pitches[k][i],
                    tick=chord.start + int(round(i * step)),
                    length=max(1, int(step * ctx.gate)),
                    chord_index=k,
                    slot=i,
                    intent=intents[k][i],
                )
            )

    cand = Candidate(index=index, strategy=strat.name, outside=round(outside, 3), seed=seed, notes=notes, group=group)
    annotate(cand, chords, key, ctx.loop)
    return cand


# --------------------------------------------------------------------- diversity
def _sign(x):
    return (x > 0) - (x < 0)


def similarity(a: Candidate, b: Candidate) -> float:
    """0..1: how alike two candidates are (pitch classes + contour)."""
    pa, pb = [n.pitch for n in a.notes], [n.pitch for n in b.notes]
    m = min(len(pa), len(pb))
    pc = sum(1 for x, y in zip(pa, pb) if x % 12 == y % 12) / m
    ca = [_sign(y - x) for x, y in zip(pa, pa[1:])]
    cb = [_sign(y - x) for x, y in zip(pb, pb[1:])]
    mc = max(1, min(len(ca), len(cb)))
    contour = sum(1 for x, y in zip(ca, cb) if x == y) / mc
    return 0.5 * (pc + contour)


def generate_candidates(ctx: Context, count: int = 16, outside=None, outside_range=(0.0, 0.9),
                        seed=None, sweep: bool = False, strategies=None):
    """Return (candidates, seed). Reproducible for a given seed."""
    base_seed = seed if seed is not None else random.randrange(1, 1_000_000)
    rng = random.Random(base_seed)
    names = list(strategies) if strategies else list(STRATEGIES)

    out = []
    if sweep:
        # Same skeleton, five outside levels: hear exactly what "outside" adds.
        # A level that changes nothing versus the previous kept one is skipped.
        for g in range(count):
            strat = STRATEGIES[names[g % len(names)]]
            cseed = rng.randrange(1, 1_000_000)
            last = None
            for lv in SWEEP_LEVELS:
                cand = build_candidate(ctx, strat, lv, cseed, group=g + 1)
                pitches = [n.pitch for n in cand.notes]
                if pitches == last:
                    continue
                last = pitches
                cand.index = len(out) + 1
                out.append(cand)
        return out, base_seed

    lo_o, hi_o = outside_range
    threshold, fails = 0.70, 0
    while len(out) < count:
        i = len(out)
        strat = STRATEGIES[names[i % len(names)]]
        if outside is not None:
            level = outside
        else:
            level = lo_o + (hi_o - lo_o) * (i / (count - 1) if count > 1 else 0.5)
        cand = build_candidate(ctx, strat, level, rng.randrange(1, 1_000_000), index=i + 1)
        if all(similarity(cand, o) < threshold for o in out):
            out.append(cand)
            fails = 0
        else:
            fails += 1
            if fails >= 10:  # not enough room for that much variety: relax
                threshold = min(1.01, threshold + 0.03)
                fails = 0
    return out, base_seed
