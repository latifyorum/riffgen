"""Chord segmentation, chord detection and key estimation."""
from __future__ import annotations

import math
import re

from .i18n import t
from .models import Chord, Key, Song

# (suffix, intervals from root)
QUALITIES = [
    ("", (0, 4, 7)),
    ("m", (0, 3, 7)),
    ("dim", (0, 3, 6)),
    ("aug", (0, 4, 8)),
    ("sus2", (0, 2, 7)),
    ("sus4", (0, 5, 7)),
    ("7", (0, 4, 7, 10)),
    ("maj7", (0, 4, 7, 11)),
    ("m7", (0, 3, 7, 10)),
    ("m7b5", (0, 3, 6, 10)),
    ("dim7", (0, 3, 6, 9)),
    ("5", (0, 7)),
]

# Krumhansl-Kessler key profiles.
_KS_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_KS_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]

_NOTE_LETTER = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_KEY_RE = re.compile(r"^\s*([A-Ga-g])\s*([#b♯♭]?)\s*(m|min|minor|M|maj|major)?\s*$")


# ---------------------------------------------------------------- segmentation
def _overlap(n, a: int, b: int) -> int:
    return min(n.end, b) - max(n.start, a)


def _pcs(notes, a: int, b: int) -> frozenset:
    return frozenset(n.pitch % 12 for n in notes if n.start < b and n.end > a)


def _auto_segments(song: Song, min_beats: float):
    """Split wherever the set of sounding notes changes, then clean up."""
    notes = song.notes
    min_len = max(1, int(song.ticks_per_beat * min_beats))
    points = sorted({n.start for n in notes} | {n.end for n in notes})

    raw = [[a, b] for a, b in zip(points, points[1:]) if _pcs(notes, a, b)]

    # A: absorb short or identical-pitch-class slices into the previous contiguous one.
    merged = []
    for a, b in raw:
        if merged and merged[-1][1] == a and (
            (b - a) < min_len or _pcs(notes, a, b) == _pcs(notes, *merged[-1])
        ):
            merged[-1][1] = b
        else:
            merged.append([a, b])

    # B: a short slice with nothing before it joins the next one (or is dropped).
    cleaned = []
    for idx, (a, b) in enumerate(merged):
        if (b - a) >= min_len:
            cleaned.append([a, b])
        elif idx + 1 < len(merged) and merged[idx + 1][0] == b:
            merged[idx + 1][0] = a

    # C: merge neighbours that ended up with the same pitch classes.
    final = []
    for a, b in cleaned:
        if final and final[-1][1] == a and _pcs(notes, a, b) == _pcs(notes, *final[-1]):
            final[-1][1] = b
        else:
            final.append([a, b])
    return final


def _window_segments(song: Song, window_beats: float):
    """Fixed windows; use this for arpeggiated or very busy chord tracks."""
    notes = song.notes
    w = max(1, int(song.ticks_per_beat * window_beats))
    t_end = max(n.end for n in notes)
    a = (min(n.start for n in notes) // w) * w
    out = []
    while a < t_end:
        if _pcs(notes, a, a + w):
            out.append([a, a + w])
        a += w
    return out


# -------------------------------------------------------------- chord detection
def _weights(notes, a: int, b: int) -> dict:
    w = {}
    for n in notes:
        ov = _overlap(n, a, b)
        if ov > 0:
            w[n.pitch % 12] = w.get(n.pitch % 12, 0.0) + ov * (n.velocity / 127.0)
    return w


def _bass_pc(notes, a: int, b: int) -> int:
    span = b - a
    sustained = [n.pitch for n in notes if _overlap(n, a, b) >= 0.5 * span]
    pool = sustained or [n.pitch for n in notes if _overlap(n, a, b) > 0]
    return min(pool) % 12


def detect_chord(present: dict, bass: int):
    """present: {pitch class: relative weight 0..1}. Returns (root, suffix, tones)."""
    best = None
    for root in range(12):
        for suffix, ivs in QUALITIES:
            tpcs = {(root + i) % 12 for i in ivs}
            matched = sum(present[pc] for pc in tpcs if pc in present)
            extra = sum(w for pc, w in present.items() if pc not in tpcs)
            missing = sum(1.0 if i == 0 else 0.7 for i in ivs if (root + i) % 12 not in present)
            score = matched - 1.1 * extra - 0.8 * missing
            if bass == root:
                score += 0.4
            if len(ivs) > 3:
                score -= 0.05 * (len(ivs) - 3)
            if best is None or score > best[0]:
                best = (score, root, suffix)
    _, root, suffix = best

    # Chord tones = what was actually played (add9/11 etc. count), root first.
    others = sorted({(pc - root) % 12 for pc in present if pc != root})
    tones = (root,) + tuple((root + iv) % 12 for iv in others)
    return root, suffix, tones


def segment_chords(song: Song, window_beats=None, min_beats: float = 0.5):
    segs = _window_segments(song, window_beats) if window_beats else _auto_segments(song, min_beats)
    q = max(1, song.ticks_per_beat // 4)  # snap boundaries to 16th notes

    chords = []
    for a, b in segs:
        a2, b2 = int(round(a / q) * q), int(round(b / q) * q)
        if b2 <= a2:
            continue
        w = _weights(song.notes, a2, b2)
        if not w:
            continue
        top = max(w.values())
        present = {pc: v / top for pc, v in w.items() if v >= 0.2 * top}
        root, suffix, tones = detect_chord(present, _bass_pc(song.notes, a2, b2))
        chords.append(Chord(start=a2, end=b2, root=root, quality=suffix, tones=tones))

    if not chords:
        raise ValueError(t("err.no_chords"))
    return chords


# ------------------------------------------------------------------------- key
def _pearson(x, y) -> float:
    mx, my = sum(x) / len(x), sum(y) / len(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den = math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    return num / den if den else 0.0


_MINOR_LIKE = {"m", "m7", "dim", "m7b5", "dim7", "m6", "m9", "madd9", "mmaj7"}
_MAJOR_LIKE = {"", "7", "maj7", "6", "9", "maj9", "add9"}


def detect_key(song: Song, first_chord=None) -> Key:
    """Krumhansl-Schmuckler on a duration-weighted pitch-class histogram.

    The first chord nudges the result: progressions usually start on the tonic, and a
    minor first chord points to the minor reading over its relative major.
    """
    hist = [0.0] * 12
    for n in song.notes:
        hist[n.pitch % 12] += n.end - n.start

    best = None
    for tonic in range(12):
        for mode, prof in (("major", _KS_MAJOR), ("minor", _KS_MINOR)):
            rotated = [prof[(pc - tonic) % 12] for pc in range(12)]
            r = _pearson(hist, rotated)
            if first_chord is not None and tonic == first_chord.root:
                r += 0.03
                q = first_chord.quality
                if (mode == "minor" and q in _MINOR_LIKE) or (mode == "major" and q in _MAJOR_LIKE):
                    r += 0.09
            if best is None or r > best[0]:
                best = (r, tonic, mode)
    return Key(best[1], best[2])


# ------------------------------------------------------------ manual chord entry
# Kept separate from QUALITIES on purpose: MIDI chord *detection* iterates QUALITIES,
# and adding e.g. "6" there would make C6 and Am7 indistinguishable.
MANUAL_QUALITIES = dict(QUALITIES)
MANUAL_QUALITIES.update({
    "6": (0, 4, 7, 9), "m6": (0, 3, 7, 9),
    "9": (0, 4, 7, 10, 14), "m9": (0, 3, 7, 10, 14), "maj9": (0, 4, 7, 11, 14),
    "add9": (0, 4, 7, 14), "madd9": (0, 3, 7, 14), "mmaj7": (0, 3, 7, 11),
})

_QUALITY_ALIASES = {
    "maj": "", "M": "", "min": "m", "-": "m", "min7": "m7", "-7": "m7",
    "M7": "maj7", "Δ": "maj7", "Δ7": "maj7", "mM7": "mmaj7",
    "+": "aug", "°": "dim", "°7": "dim7", "ø": "m7b5", "ø7": "m7b5", "sus": "sus4",
}

# letter, accidental, quality (anything but "/"), optional /bass
_CHORD_RE = re.compile(r"^([A-Ga-g])([#b♯♭]?)([^/]*)(?:/([A-Ga-g])([#b♯♭]?))?$")


def validate_manual_params(bpm, bars):
    """Return (bpm: float, bars: int) or raise ValueError with a localised message."""
    try:
        bpm = float(bpm)
    except (TypeError, ValueError):
        raise ValueError(t("err.bpm_range"))
    if not 20 <= bpm <= 300:  # also rejects nan and inf
        raise ValueError(t("err.bpm_range"))
    try:
        bars = int(bars)
    except (TypeError, ValueError):
        raise ValueError(t("err.bars_range"))
    if not 1 <= bars <= 16:
        raise ValueError(t("err.bars_range"))
    return bpm, bars


def _pitch_class(letter: str, acc: str) -> int:
    pc = _NOTE_LETTER[letter.upper()]
    if acc in ("#", "♯"):
        pc += 1
    elif acc in ("b", "♭"):
        pc -= 1
    return pc % 12


def _parse_chord_token(token: str):
    """(root pc, canonical quality, tones) for 'Am', 'F#m7', 'Bbmaj7', 'C/G' ...

    An unknown quality is an error; it never falls back to a major triad. For a slash
    chord the bass note is added to the tones if the chord does not already contain it.
    """
    m = _CHORD_RE.match(token)
    if not m:
        raise ValueError(t("err.bad_chord", token=token))
    letter, acc, raw_qual, bass_letter, bass_acc = m.groups()
    quality = _QUALITY_ALIASES.get(raw_qual, raw_qual)
    if quality not in MANUAL_QUALITIES:
        raise ValueError(t("err.bad_chord", token=token))
    root = _pitch_class(letter, acc)
    tones = tuple((root + i) % 12 for i in MANUAL_QUALITIES[quality])
    if bass_letter:
        bass = _pitch_class(bass_letter, bass_acc)
        if bass not in tones:
            tones += (bass,)
    return root, quality, tones


def parse_chords_text(
    text: str,
    bars_per_chord: int = 1,
    bpm: float = 120.0,
    ticks_per_beat: int = 480,
) -> list:
    """Parse a space/comma/bar-line separated chord string into a list of Chord objects.

    Tokens look like ``Am``, ``F#m7``, ``Bb``, ``Cmaj7``, ``Gsus4``, ``Cm9``, ``C/G``.
    Separators are whitespace, ``,`` and ``|`` (``/`` is *not* a separator: it marks a
    slash chord). Unknown chord types raise ValueError.

    bars_per_chord: bars each chord occupies (4/4 assumed).
    bpm: kept for API compatibility; the tick length does not depend on it.
    """
    tokens = [x for x in re.split(r"[\s,|]+", text.strip()) if x]
    if not tokens:
        raise ValueError(t("err.no_chord_text"))

    ticks_per_chord = ticks_per_beat * 4 * bars_per_chord  # assume 4/4
    chords = []
    for idx, token in enumerate(tokens):
        root, quality, tones = _parse_chord_token(token)
        start = idx * ticks_per_chord
        chords.append(Chord(start=start, end=start + ticks_per_chord, root=root, quality=quality, tones=tones))
    return chords


def parse_key(text: str) -> Key:
    m = _KEY_RE.match(text)
    if not m:
        raise ValueError(t("err.bad_key", text=text))
    letter, acc, mode = m.groups()
    pc = _NOTE_LETTER[letter.upper()]
    if acc in ("#", "♯"):
        pc += 1
    elif acc in ("b", "♭"):
        pc -= 1
    minor = mode in ("m", "min", "minor")
    return Key(pc % 12, "minor" if minor else "major")
