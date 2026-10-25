"""Command-line entry point: python -m riffgen chords.mid"""
from __future__ import annotations

import argparse
import os
import sys

from . import i18n, report
from .analysis import detect_key, parse_key, segment_chords
from .generator import STRATEGIES, Context, generate_candidates
from .i18n import t
from .io_midi import read_midi, write_midi


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="riffgen", description=t("cli.desc"))
    p.add_argument("midi", help=t("h.midi"))
    p.add_argument("-n", "--count", type=int, default=16, help=t("h.count"))
    p.add_argument("--grid", type=float, default=0.5, help=t("h.grid"))
    p.add_argument("--outside", type=float, default=None, help=t("h.outside"))
    p.add_argument("--outside-range", type=float, nargs=2, metavar=("LO", "HI"), default=(0.0, 0.9), help=t("h.orange"))
    p.add_argument("--sweep", action="store_true", help=t("h.sweep"))
    p.add_argument("--strategies", nargs="+", choices=sorted(STRATEGIES), default=None, help=t("h.strategies"))
    p.add_argument("--key", default=None, help=t("h.key"))
    p.add_argument("--window", type=float, default=None, help=t("h.window"))
    p.add_argument("--low", type=int, default=40, help=t("h.low"))
    p.add_argument("--high", type=int, default=72, help=t("h.high"))
    p.add_argument("--seed", type=int, default=None, help=t("h.seed"))
    p.add_argument("--no-loop", action="store_true", help=t("h.noloop"))
    p.add_argument("--flat-velocity", action="store_true", help=t("h.flatvel"))
    p.add_argument("-o", "--out", default=None, help=t("h.out"))
    p.add_argument("--lang", choices=sorted(i18n.STRINGS), default=None, help=t("h.lang"))
    return p


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    argv = sys.argv[1:] if argv is None else list(argv)
    i18n.set_lang(i18n.pick_lang(argv))
    args = build_parser().parse_args(argv)

    if args.high - args.low < 12:
        sys.exit(t("err.low_high"))
    if args.grid <= 0 or args.count < 1:
        sys.exit(t("err.grid_count"))
    for lv in ([args.outside] if args.outside is not None else []) + list(args.outside_range):
        if not 0 <= lv <= 1:
            sys.exit(t("err.outside"))

    try:
        song = read_midi(args.midi)
        chords = segment_chords(song, window_beats=args.window)
        key = parse_key(args.key) if args.key else detect_key(song, first_chord=chords[0])
    except ValueError as e:
        sys.exit(str(e))

    ctx = Context(song=song, chords=chords, key=key, grid=args.grid,
                  lo=args.low, hi=args.high, loop=not args.no_loop)

    candidates, seed = generate_candidates(
        ctx, count=args.count, outside=args.outside, outside_range=tuple(args.outside_range),
        seed=args.seed, sweep=args.sweep, strategies=args.strategies,
    )

    source = os.path.basename(args.midi)
    out_dir = args.out or os.path.join("riffgen_out", os.path.splitext(source)[0])
    os.makedirs(out_dir, exist_ok=True)

    def track(c):
        return f"{c.index:02d} {c.strategy} o{int(round(c.outside * 100))}", c.notes

    for c in candidates:
        write_midi(os.path.join(out_dir, report.filename(c)), song, [track(c)], flat_velocity=args.flat_velocity)
    write_midi(os.path.join(out_dir, "all_candidates.mid"), song, [track(c) for c in candidates],
               flat_velocity=args.flat_velocity)

    with open(os.path.join(out_dir, "report.txt"), "w", encoding="utf-8") as f:
        f.write(report.render_text(ctx, candidates, seed, source))
    with open(os.path.join(out_dir, "candidates.json"), "w", encoding="utf-8") as f:
        f.write(report.to_json(ctx, candidates, seed, source))

    flats = key.flats
    tpb = song.ticks_per_beat
    print(f"{t('c.key'):<8}: {key}" + ("" if args.key else t("c.key_auto")))
    print(f"{t('c.chords'):<8}: " + " | ".join(f"{c.label(flats)} ({c.start / tpb:g}–{c.end / tpb:g})" for c in chords))
    print(f"{t('c.seed'):<8}: {seed}\n")
    print(f"{'#':>3}  {t('c.th_strategy'):<9} {t('c.th_outside'):>7} {t('c.th_score'):>6} "
          f"{t('c.th_tension'):>8} {t('c.th_unres'):>11}")
    for c in candidates:
        m = c.metrics
        print(f"{c.index:>3}  {c.strategy:<9} {c.outside:>7.2f} {m['consonance']:>6.1f} {m['tension']:>8} {m['unresolved']:>11}")
    print("\n" + t("c.done", n=len(candidates), dir=out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
