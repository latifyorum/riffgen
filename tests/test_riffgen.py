import os
import random
import sys
import tempfile

import mido

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from riffgen.analysis import detect_key, parse_key, segment_chords  # noqa: E402
from riffgen.generator import STRATEGIES, Context, build_candidate, generate_candidates, similarity  # noqa: E402
from riffgen.io_midi import read_midi, write_midi  # noqa: E402
from riffgen.models import Key  # noqa: E402

TPB = 480
PROGRESSION = [[57, 60, 64], [53, 57, 60], [50, 53, 57], [52, 56, 59]]  # Am F Dm E


def _write_chords(path, chords=PROGRESSION, jitter=0, arpeggiate=False, seed=1):
    rnd = random.Random(seed)
    mid = mido.MidiFile(type=1, ticks_per_beat=TPB)
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    tr.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(90), time=0))
    events = []
    for bar, chord in enumerate(chords):
        t0 = bar * 4 * TPB
        for i, note in enumerate(chord):
            if arpeggiate:  # each note on its own eighth, repeated through the bar
                for rep in range(8):
                    s = t0 + rep * TPB // 2
                    events.append((s, 1, chord[rep % len(chord)]))
                    events.append((s + TPB // 2 - 10, 0, chord[rep % len(chord)]))
                break
            off = rnd.randint(0, jitter) if jitter else 0
            events.append((t0 + off, 1, note))
            events.append((t0 + 4 * TPB - rnd.randint(0, jitter or 0), 0, note))
    events.sort(key=lambda e: (e[0], e[1]))
    last = 0
    for tick, on, note in events:
        tr.append(mido.Message("note_on" if on else "note_off", note=note, velocity=90 if on else 0, time=tick - last))
        last = tick
    mid.save(path)


def _ctx(tmp, **kw):
    path = os.path.join(tmp, "c.mid")
    _write_chords(path, **kw.pop("midi", {}))
    song = read_midi(path)
    chords = segment_chords(song)
    key = detect_key(song, first_chord=chords[0])
    return Context(song=song, chords=chords, key=key, **kw)


def test_chords_and_key():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = _ctx(tmp)
        assert [c.label() for c in ctx.chords] == ["Am", "F", "Dm", "E"]
        assert (ctx.key.tonic, ctx.key.mode) == (9, "minor")


def test_humanized_input_still_gives_four_chords():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = _ctx(tmp, midi={"jitter": 25})
        assert [c.label() for c in ctx.chords] == ["Am", "F", "Dm", "E"]


def test_window_mode_handles_arpeggios():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "arp.mid")
        _write_chords(path, arpeggiate=True)
        chords = segment_chords(read_midi(path), window_beats=4)
        assert [c.label() for c in chords] == ["Am", "F", "Dm", "E"]


def test_parse_key():
    assert parse_key("Am") == Key(9, "minor")
    assert parse_key("F#m") == Key(6, "minor")
    assert parse_key("Bb") == Key(10, "major")
    assert parse_key("C minor") == Key(0, "minor")


def test_outside_zero_never_produces_tension():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = _ctx(tmp)
        for name, strat in STRATEGIES.items():
            for seed in range(1, 40):
                cand = build_candidate(ctx, strat, 0.0, seed)
                assert cand.metrics["tension"] == 0, (name, seed)


def test_range_and_slot_counts():
    with tempfile.TemporaryDirectory() as tmp:
        for grid in (1.0, 0.5, 0.25):
            ctx = _ctx(tmp, grid=grid, lo=43, hi=69)
            cands, _ = generate_candidates(ctx, count=12, seed=3)
            for c in cands:
                assert all(43 <= n.pitch <= 69 for n in c.notes)
                assert len(c.notes) == int(round(16 / grid))


def test_seed_is_reproducible():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = _ctx(tmp)
        a, _ = generate_candidates(ctx, count=8, seed=11)
        b, _ = generate_candidates(ctx, count=8, seed=11)
        assert [[n.pitch for n in c.notes] for c in a] == [[n.pitch for n in c.notes] for c in b]


def test_sweep_adds_tension_to_same_skeleton():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = _ctx(tmp)
        cands, _ = generate_candidates(ctx, count=6, seed=5, sweep=True)
        for g in range(1, 7):
            group = [c for c in cands if c.group == g]
            levels = [c.outside for c in group]
            assert levels[0] == 0.0 and levels == sorted(levels)
            assert set(levels) <= {0.0, 0.25, 0.5, 0.75, 1.0}
            assert group[0].metrics["tension"] == 0
            seqs = [tuple(n.pitch for n in c.notes) for c in group]
            assert len(set(seqs)) == len(seqs)  # no identical neighbours kept
        # on average the sweep gets more tense toward the top
        tops = [max((c for c in cands if c.group == g), key=lambda c: c.outside) for g in range(1, 7)]
        assert sum(c.metrics["tension"] for c in tops) > 0


def test_default_batch_is_diverse():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = _ctx(tmp)
        cands, _ = generate_candidates(ctx, count=16, seed=2)
        assert len(cands) == 16
        seqs = {tuple(n.pitch for n in c.notes) for c in cands}
        assert len(seqs) == 16
        worst = max(similarity(a, b) for i, a in enumerate(cands) for b in cands[i + 1:])
        assert worst < 0.9


def test_midi_round_trip_preserves_pitches_and_timing():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = _ctx(tmp)
        cands, _ = generate_candidates(ctx, count=4, seed=9)
        out = os.path.join(tmp, "out.mid")
        write_midi(out, ctx.song, [(f"c{c.index}", c.notes) for c in cands])
        mid = mido.MidiFile(out)
        assert len(mid.tracks) == 1 + len(cands)  # meta track + one per candidate
        # Read the first candidate track back as a Song-like list.
        t, got = 0, []
        for msg in mid.tracks[1]:
            t += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                got.append((t, msg.note))
        assert got == [(n.tick, n.pitch) for n in cands[0].notes]


def test_key_prefers_reading_that_matches_first_chord():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "k.mid")
        _write_chords(path, chords=[[50, 53, 57], [46, 50, 53], [53, 57, 60], [48, 52, 55]])  # Dm Bb F C
        song = read_midi(path)
        chords = segment_chords(song)
        assert [c.label(flats=True) for c in chords] == ["Dm", "Bb", "F", "C"]
        assert str(detect_key(song, first_chord=chords[0])) == "D minor"
        _write_chords(path, chords=[[48, 52, 55], [55, 59, 62], [57, 60, 64], [53, 57, 60]])  # C G Am F
        song = read_midi(path)
        assert str(detect_key(song, first_chord=segment_chords(song)[0])) == "C major"


def test_gui_pipeline_and_downloads():
    import io
    from riffgen import gui

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "c.mid")
        _write_chords(path)
        with open(path, "rb") as f:
            payload = gui.generate(f.read(), {"count": "6", "seed": "3"})
    assert payload["key"] == "A minor" and [c["n"] for c in payload["chords"]] == ["Am", "F", "Dm", "E"]
    assert len(payload["candidates"]) == 6 and payload["total"] == 16 * TPB
    first = payload["candidates"][0]
    assert {"p", "t", "l", "r"} <= set(first["n"][0])
    name, data = gui.midi_for(str(first["i"]))
    assert name.endswith(".mid") and len(mido.MidiFile(file=io.BytesIO(data)).tracks) == 2
    assert len(mido.MidiFile(file=io.BytesIO(gui.midi_for("all")[1])).tracks) == 7
    assert gui.midi_for("999") is None


def test_i18n_languages_are_in_sync():
    import string

    from riffgen import i18n

    en, tr = i18n.STRINGS["en"], i18n.STRINGS["tr"]
    assert set(en) == set(tr)
    fields = lambda s: {x[1] for x in string.Formatter().parse(s) if x[1]}  # noqa: E731
    assert all(fields(en[k]) == fields(tr[k]) for k in en)


def test_pick_lang():
    from riffgen import i18n

    saved = os.environ.pop("RIFFGEN_LANG", None)
    try:
        assert i18n.pick_lang([]) == "en"
        assert i18n.pick_lang(["x.mid", "--lang", "tr"]) == "tr"
        assert i18n.pick_lang(["--lang=tr"]) == "tr"
        assert i18n.pick_lang(["--lang", "zz"]) == "en"
        os.environ["RIFFGEN_LANG"] = "tr"
        assert i18n.pick_lang([]) == "tr"
        assert i18n.pick_lang(["--lang", "en"]) == "en"
    finally:
        os.environ.pop("RIFFGEN_LANG", None)
        if saved is not None:
            os.environ["RIFFGEN_LANG"] = saved


def test_report_is_localised_and_english_has_no_turkish():
    import re

    from riffgen import i18n, report

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _ctx(tmp)
        cands, seed = generate_candidates(ctx, count=3, seed=1)
        try:
            i18n.set_lang("en")
            text_en = report.render_text(ctx, cands, seed, "c.mid")
            i18n.set_lang("tr")
            text_tr = report.render_text(ctx, cands, seed, "c.mid")
        finally:
            i18n.set_lang("en")
    assert "consonance" in text_en and not re.search("[çğıöşüÇĞİÖŞÜ]", text_en)
    assert "uyum" in text_tr and "raporu" in text_tr
