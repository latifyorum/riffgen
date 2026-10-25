"""Role labels (anchor/color/tension) and a heuristic consonance score.

The score is a rough proxy, not a verdict: it measures how much each note rubs
against the chord underneath, discounted when the note is in the key or when it
steps into a chord tone. Use it to sort ideas, then trust your ears.
"""
from __future__ import annotations

# Penalty per interval class between a note and a chord tone.
_CLASH_WEIGHT = {1: 0.70, 2: 0.15, 6: 0.35}  # m2/M7, M2/m7, tritone
_IN_SCALE_FACTOR = 0.45
_RESOLVED_FACTOR = 0.40


def _interval_class(a: int, b: int) -> int:
    d = (a - b) % 12
    return min(d, 12 - d)


def note_clash(pc: int, tones, scale) -> float:
    """0 = chord tone, 1 = worst roughness against the chord."""
    if pc in tones:
        return 0.0
    base = min(1.0, sum(_CLASH_WEIGHT.get(_interval_class(pc, t), 0.0) for t in tones))
    # Cross-relation (e.g. G natural against an E major chord's G#): being in the
    # key does not soften it.
    cross = any(t not in scale and _interval_class(pc, t) == 1 for t in tones)
    if pc in scale and not cross:
        base *= _IN_SCALE_FACTOR
    return base


def annotate(cand, chords, key, loop: bool = True) -> None:
    """Fill role/resolved/clash on every note and cand.metrics."""
    notes = cand.notes
    n = len(notes)
    scale = key.scale

    for nt in notes:
        tones = chords[nt.chord_index].tones
        pc = nt.pitch % 12
        if pc in tones:
            nt.role = "anchor"
        elif pc in scale:
            nt.role = "color"
        else:
            nt.role = "tension"

    for idx, nt in enumerate(notes):
        nxt = notes[(idx + 1) % n] if (loop or idx + 1 < n) and n > 1 else None
        nt.resolved = bool(
            nt.role == "tension"
            and nxt is not None
            and nxt.role == "anchor"
            and abs(nxt.pitch - nt.pitch) <= 2
        )
        tones = chords[nt.chord_index].tones
        clash = note_clash(nt.pitch % 12, tones, scale)
        if nt.resolved:
            clash *= _RESOLVED_FACTOR
        nt.clash = round(clash, 3)

    tension = [x for x in notes if x.role == "tension"]
    pitches = [x.pitch for x in notes]
    cand.metrics = {
        "consonance": round(100 * (1 - sum(x.clash for x in notes) / n), 1),
        "anchor": sum(1 for x in notes if x.role == "anchor"),
        "color": sum(1 for x in notes if x.role == "color"),
        "tension": len(tension),
        "tension_pct": round(100 * len(tension) / n, 1),
        "unresolved": sum(1 for x in tension if not x.resolved),
        "distinct_pcs": len({p % 12 for p in pitches}),
        "span": max(pitches) - min(pitches),
        "leaps": sum(1 for a, b in zip(pitches, pitches[1:]) if abs(b - a) > 7),
    }
