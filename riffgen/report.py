"""Human-readable report + machine-readable JSON for a batch of candidates."""
from __future__ import annotations

import json

from .generator import STRATEGIES
from .i18n import t
from .models import pitch_name

def mark(note, flats: bool) -> str:
    suffix = {"anchor": "", "color": "~", "tension": "!"}[note.role]
    return pitch_name(note.pitch, flats) + suffix


def filename(c) -> str:
    level = int(round(c.outside * 100))
    if c.group > 0:
        return f"g{c.group:02d}_o{level:03d}_{c.strategy}_s{c.seed:06d}.mid"
    return f"{c.index:02d}_{c.strategy}_o{level:03d}_s{c.seed:06d}.mid"


def render_text(ctx, candidates, seed: int, source: str) -> str:
    flats = ctx.key.flats
    tpb = ctx.song.ticks_per_beat
    lines = [
        t("r.title", source=source),
        t("r.head1", bpm=ctx.song.bpm, num=ctx.song.numerator, den=ctx.song.denominator, key=ctx.key, seed=seed),
        t("r.head2", grid=ctx.grid, lo=pitch_name(ctx.lo, flats), hi=pitch_name(ctx.hi, flats),
          loop=t("r.yes") if ctx.loop else t("r.no")),
        t("r.chords") + " | ".join(f"{c.label(flats)} ({c.start / tpb:g}–{c.end / tpb:g})" for c in ctx.chords),
        t("r.legend"),
        t("r.note"),
        "",
    ]
    for c in candidates:
        m = c.metrics
        head = f"#{c.index:02d}  {c.strategy:<9} outside={c.outside:.2f}  seed={c.seed}"
        if c.group > 0:
            head = f"G{c.group:02d} " + head
        lines.append(head)
        lines.append("     " + t("r.metrics", cons=m["consonance"], a=m["anchor"], c=m["color"], t=m["tension"],
                                u=m["unresolved"], d=m["distinct_pcs"], s=m["span"]))
        for k, chord in enumerate(ctx.chords):
            seq = " ".join(mark(n, flats) for n in c.notes if n.chord_index == k)
            lines.append(f"     {chord.label(flats):<6}: {seq}")
        lines.append("")
    lines.append(t("r.strategies") + "; ".join(f"{s.name} = {t('strat.' + s.name)}" for s in STRATEGIES.values()))
    return "\n".join(lines) + "\n"


def to_json(ctx, candidates, seed: int, source: str) -> str:
    flats = ctx.key.flats
    data = {
        "source": source,
        "seed": seed,
        "key": str(ctx.key),
        "bpm": round(ctx.song.bpm, 2),
        "grid_beats": ctx.grid,
        "chords": [
            {"label": c.label(flats), "start_tick": c.start, "end_tick": c.end, "tones": list(c.tones)}
            for c in ctx.chords
        ],
        "candidates": [
            {
                "index": c.index,
                "group": c.group,
                "strategy": c.strategy,
                "outside": c.outside,
                "seed": c.seed,
                "file": filename(c),
                "metrics": c.metrics,
                "notes": [
                    {
                        "chord": ctx.chords[n.chord_index].label(flats),
                        "slot": n.slot,
                        "pitch": n.pitch,
                        "name": pitch_name(n.pitch, flats),
                        "role": n.role,
                        "intent": n.intent,
                        "resolved": n.resolved,
                        "clash": n.clash,
                    }
                    for n in c.notes
                ],
            }
            for c in candidates
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)
