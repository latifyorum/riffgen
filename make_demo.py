"""Writes demo_chords.mid: Am | F | Dm | E, one bar each, 4/4, 85 BPM."""
import mido

TPB = 480
CHORDS = [
    [57, 60, 64],  # Am  (A3 C4 E4)
    [53, 57, 60],  # F   (F3 A3 C4)
    [50, 53, 57],  # Dm  (D3 F3 A3)
    [52, 56, 59],  # E   (E3 G#3 B3)
]
BAR = 4 * TPB

mid = mido.MidiFile(type=1, ticks_per_beat=TPB)
track = mido.MidiTrack()
mid.tracks.append(track)
track.append(mido.MetaMessage("track_name", name="chords", time=0))
track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(85), time=0))
track.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))

for chord in CHORDS:
    for i, note in enumerate(chord):
        track.append(mido.Message("note_on", note=note, velocity=90, time=0))
    for i, note in enumerate(chord):
        track.append(mido.Message("note_off", note=note, velocity=0, time=BAR if i == 0 else 0))

mid.save("demo_chords.mid")
print("demo_chords.mid written")
