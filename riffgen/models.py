"""Shared data structures and small music-theory helpers."""
from __future__ import annotations

from dataclasses import dataclass, field

SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

MAJOR_SCALE = frozenset({0, 2, 4, 5, 7, 9, 11})
MINOR_SCALE = frozenset({0, 2, 3, 5, 7, 8, 10})  # natural minor

# Tonics whose key signature uses flats (spelling only).
_FLAT_MAJOR = {5, 10, 3, 8, 1, 6}
_FLAT_MINOR = {2, 7, 0, 5, 10, 3}


def pc_name(pc: int, flats: bool = False) -> str:
    return (FLAT_NAMES if flats else SHARP_NAMES)[pc % 12]


def pitch_name(pitch: int, flats: bool = False) -> str:
    """MIDI 60 -> C4."""
    return f"{pc_name(pitch, flats)}{pitch // 12 - 1}"


@dataclass(frozen=True)
class MidiNote:
    pitch: int
    start: int  # ticks
    end: int  # ticks
    velocity: int


@dataclass
class Song:
    """What we need from the input MIDI file."""

    ticks_per_beat: int
    tempo: int  # microseconds per quarter note
    numerator: int
    denominator: int
    notes: list = field(default_factory=list)

    @property
    def bpm(self) -> float:
        return 60_000_000 / self.tempo


@dataclass(frozen=True)
class Key:
    tonic: int  # pitch class
    mode: str  # "major" | "minor"

    @property
    def scale(self) -> frozenset:
        base = MAJOR_SCALE if self.mode == "major" else MINOR_SCALE
        return frozenset((self.tonic + i) % 12 for i in base)

    @property
    def flats(self) -> bool:
        return self.tonic in (_FLAT_MAJOR if self.mode == "major" else _FLAT_MINOR)

    def __str__(self) -> str:
        return f"{pc_name(self.tonic, self.flats)} {self.mode}"


@dataclass
class Chord:
    start: int  # ticks
    end: int  # ticks
    root: int  # pitch class
    quality: str  # "", "m", "7", ...
    tones: tuple  # pitch classes actually present, root first

    def label(self, flats: bool = False) -> str:
        return pc_name(self.root, flats) + self.quality


@dataclass
class GenNote:
    pitch: int
    tick: int
    length: int
    chord_index: int
    slot: int
    intent: str = ""  # how the generator produced it (root, anchor, approach, ...)
    role: str = ""  # anchor | color | tension (derived from the final pitch)
    resolved: bool = False  # tension note that steps into an anchor
    clash: float = 0.0  # 0..1 heuristic roughness against the chord


@dataclass
class Candidate:
    index: int
    strategy: str
    outside: float
    seed: int
    notes: list
    group: int = -1  # sweep mode: which skeleton this belongs to
    metrics: dict = field(default_factory=dict)
