"""MIDI input (chord progression) and output (candidate pitch sequences)."""
from __future__ import annotations

import mido

from .i18n import t
from .models import MidiNote, Song

# Velocity encodes the role so it is visible in the piano roll.
ROLE_VELOCITY = {"anchor": 100, "color": 84, "tension": 66}


def read_midi(path: str) -> Song:
    mid = mido.MidiFile(path)
    tempo = None
    sig = None
    notes = []

    for track in mid.tracks:
        t = 0
        active = {}  # (channel, pitch) -> [(start, velocity), ...]
        for msg in track:
            t += msg.time
            if msg.type == "set_tempo" and tempo is None:
                tempo = msg.tempo
            elif msg.type == "time_signature" and sig is None:
                sig = (msg.numerator, msg.denominator)
            elif msg.type == "note_on" and msg.velocity > 0:
                if msg.channel == 9:  # drums
                    continue
                active.setdefault((msg.channel, msg.note), []).append((t, msg.velocity))
            elif msg.type in ("note_off", "note_on"):  # note_on vel 0 == note off
                if msg.channel == 9:
                    continue
                stack = active.get((msg.channel, msg.note))
                if stack:
                    start, vel = stack.pop(0)
                    notes.append(MidiNote(msg.note, start, max(t, start + 1), vel))
        for (_, pitch), stack in active.items():  # hanging notes
            for start, vel in stack:
                notes.append(MidiNote(pitch, start, max(t, start + 1), vel))

    if not notes:
        raise ValueError(t("err.no_notes"))

    notes.sort(key=lambda n: (n.start, n.pitch))
    return Song(
        ticks_per_beat=mid.ticks_per_beat,
        tempo=tempo or 500_000,
        numerator=(sig or (4, 4))[0],
        denominator=(sig or (4, 4))[1],
        notes=notes,
    )


def _meta_track(song: Song, name: str) -> mido.MidiTrack:
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name=name, time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=song.tempo, time=0))
    track.append(
        mido.MetaMessage(
            "time_signature",
            numerator=song.numerator,
            denominator=song.denominator,
            time=0,
        )
    )
    return track


def _note_track(name: str, notes, flat_velocity: bool) -> mido.MidiTrack:
    events = []
    for n in notes:
        vel = 100 if flat_velocity else ROLE_VELOCITY.get(n.role, 100)
        events.append((n.tick, 1, n.pitch, vel))
        events.append((n.tick + n.length, 0, n.pitch, 0))
    events.sort(key=lambda e: (e[0], e[1]))  # note-off before note-on on the same tick

    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name=name, time=0))
    last = 0
    for tick, is_on, pitch, vel in events:
        track.append(
            mido.Message(
                "note_on" if is_on else "note_off",
                note=pitch,
                velocity=vel,
                time=tick - last,
                channel=0,
            )
        )
        last = tick
    return track


def write_midi(path: str, song: Song, tracks, flat_velocity: bool = False) -> None:
    """tracks: iterable of (name, [GenNote, ...]). One MIDI track each (type 1 file).

    `path` may be a file path or a writable binary file object."""
    mid = mido.MidiFile(type=1, ticks_per_beat=song.ticks_per_beat)
    mid.tracks.append(_meta_track(song, "riffgen"))
    for name, notes in tracks:
        mid.tracks.append(_note_track(name, notes, flat_velocity))
    if hasattr(path, "write"):
        mid.save(file=path)
    else:
        mid.save(path)
