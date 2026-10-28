# riffgen

**A writer's-block breaker that turns a chord-progression MIDI file into riff ideas.**

English · [Türkçe](README.tr.md)

Give it a chord progression as MIDI and it generates role-labelled **pitch sequences** (riff ideas) that sit on those
chords. It does not generate rhythm: notes are laid on an even grid across each chord (placeholder timing). You decide
the rhythm, the placement and the final call. The goal is not to write "the right riff" but to hand you varied,
unexpected raw material.

## Features

- Chord and key detection (fixed-window mode for arpeggiated or busy chord tracks)
- **Manual chord entry**: type the progression (`Am F C G`, `Cm9/G`, ...) instead of loading a MIDI file
- 6 strategies: `ostinato`, `arpeggio`, `pedal`, `melodic`, `angular`, `crawl`
- **Outside** control (0-1): how far to step outside the chord and scale
- **Sweep** mode: the same skeleton at 5 outside levels, so you can hear what "outside" adds
- Every note is role-labelled (anchor / color / tension), plus a heuristic consonance score
- Near-duplicate candidates are rejected
- Same seed, same result
- Local browser UI: piano roll, audio preview, .mid download
- Command-line interface
- One dependency: [mido](https://github.com/mido/mido)

## Language

The UI, console output and report support English and Turkish. English is the default. For Turkish use `--lang tr` (e.g. `python -m riffgen chords.mid --lang tr`, `python start_gui.py --lang tr`) or set `RIFFGEN_LANG=tr`. In the web UI the **TR/EN** button (bottom right) switches the language; the choice is remembered in the browser.

## Quick start

Download or clone this repository (the green **Code** button on GitHub), open a terminal in the project folder and run:

```bash
pip install -r requirements.txt

python make_demo.py                 # writes demo_chords.mid (Am | F | Dm | E)
python -m riffgen.gui               # opens the UI in your browser (or double-click start_gui.py)
python -m riffgen demo_chords.mid   # or generate 16 candidates from the CLI
python -m riffgen -c "Am F C G" --bpm 90   # or type the chords instead of using a MIDI file
```

Tested on Python 3.12; 3.9+ is the intended target.

## Install as a command (optional)

```bash
pip install .            # or: pip install -e .   (editable, for development)
riffgen chords.mid       # same as: python -m riffgen chords.mid
riffgen-gui              # same as: python -m riffgen.gui
```

`pipx install .` works too and keeps it isolated from your other Python packages.

## Manual chord entry

No MIDI file needed: type the progression. In the web UI use the **Manual chords** tab; on the command line use `-c`:

```bash
python -m riffgen -c "Am F C G" --bpm 90
python -m riffgen -c "Cm9 Fm7 | Bbmaj7 G7" --bars 2 --key Cm
```

Chords are separated by spaces, commas or `|`. Each chord lasts `--bars` bars (default 1) in 4/4 at `--bpm` (default 120, allowed 20-300).

| Part | Accepted |
|---|---|
| Root | `A`-`G` (case-insensitive) with an optional `#` or `b` (`F#`, `Bb`; `♯`/`♭` also work) |
| Quality | none = major, `m`, `dim`, `aug`, `sus2`, `sus4`, `5`, `6`, `m6`, `7`, `maj7`, `m7`, `m7b5`, `dim7`, `9`, `m9`, `maj9`, `add9`, `madd9`, `mmaj7` |
| Aliases | `maj`/`M` (major), `min`/`-` (minor), `M7`/`Δ` (maj7), `+` (aug), `°` (dim), `ø` (m7b5), `sus` (sus4) |
| Slash bass | `C/G`, `Am7/E`: the bass note is added to the chord tones if the chord does not already contain it (the root stays the chord's root) |

An unknown chord type is an error; it never falls back to a major triad.

The key is estimated from the chords (weighted toward the first chord). Some progressions, such as `Am7 F C G`, are genuinely
ambiguous between A minor and C major, so pass `--key` (or fill the **Key** field in the UI) when it matters.

## Web UI

`python -m riffgen.gui` serves a local page at `http://127.0.0.1:8765`.

1. Pick a chord MIDI file on the **MIDI file** tab, or type the chords on the **Manual chords** tab (with BPM and bars per chord), adjust the settings, press **Generate**.
2. Select a candidate in the list: it is drawn in a piano roll, colored by role (green anchor, yellow color, red
   tension), and plays automatically.
3. **↑/↓** selects a candidate, **Space** plays/stops.
4. Download one candidate or all of them (as separate tracks) as .mid.

You can also start it by double-clicking `start_gui.py` (the working directory does not matter). The console window is the server: closing it stops the UI. If a busy port is hit, the next one is tried automatically.

The server only listens on 127.0.0.1. The audio preview is a basic browser synth, meant for hearing the notes, not
for choosing a sound. Flags: `--port`, `--no-browser`.

## Command line

```bash
python -m riffgen chords.mid                  # 16 candidates, outside spread from 0 to 0.9
python -m riffgen chords.mid --sweep -n 4     # 4 skeletons x 5 outside levels
python -m riffgen chords.mid --key Em --grid 0.25 --seed 7
```

Output goes to `riffgen_out/<file name>/`: one .mid per candidate, `all_candidates.mid` (one track per candidate),
`report.txt` (note names and role marks per chord) and `candidates.json`.

| Flag | Meaning |
|---|---|
| `-n 16` | Number of candidates (skeletons in sweep mode) |
| `--grid 0.5` | Beats per note: 1 = quarter, 0.5 = eighth, 0.25 = sixteenth |
| `--outside 0.4` | Fixed outside level for all candidates (0-1) |
| `--outside-range 0 0.9` | Candidates spread from safe to risky across this range (default) |
| `--sweep` | 5 outside levels (0, .25, .5, .75, 1) per skeleton |
| `--strategies crawl pedal` | Only use these strategies |
| `--key Am` | Set the key by hand (`F#m`, `Bb`, `"C minor"`) |
| `--window 4` | Analyse chords in fixed windows (beats); for arpeggios or busy chord tracks |
| `--low 40 --high 72` | Pitch range (MIDI numbers; 40 = E2, 72 = C5) |
| `--seed 7` | Same seed, same result |
| `--no-loop` | Do not treat the last chord as leading back to the first |
| `--flat-velocity` | Do not encode the role in velocity |
| `-c "Am F C G"`, `--chords` | Type the chords instead of giving a MIDI file (if both are given, the chord text is used) |
| `--bpm 120` | Tempo for manual chords (20-300) |
| `--bars 1` | Bars per chord for manual chords (1-16) |
| `--lang tr` | Interface language: `en` (default) or `tr`; also `RIFFGEN_LANG` |

## Roles

Each note is labelled by the pitch that actually results, not by the generator's intent:

- **anchor**: a chord tone. Fits long, strong beats. Velocity 100.
- **color**: in the key's scale but not a chord tone. Velocity 84.
- **tension**: outside the scale. Reads as color on a short, weak beat and as a mistake on a long, strong one. Velocity 66.

In `report.txt`: plain = anchor, `~` = color, `!` = tension.

Tension notes come in three kinds: **approach** (a semitone from the next chord tone, always resolves), **modal**
(characteristic "outside" sounds such as b2, b5 and the natural 7 in minor) and **chromatic** (a semitone neighbour of
the previous note, only at high outside levels). Tension only lands on the weak (odd-numbered) positions of the grid.

## Consonance score

0-100, where 100 means every note is a chord tone. It looks at how much each note rubs against the chord (semitone,
tritone, second). Notes in the key and tension notes that step into a chord tone are penalised less.
**It is a heuristic, not a verdict.** Use it to sort candidates; whether something sounds right is decided by your ears
in the context of your track.

## How it works

```
chord MIDI → chord/key analysis → strategy + outside → pitch sequence → role labels + score → MIDI / UI
```

Every random decision comes from a table drawn up front from one seed, so the same seed gives the same riff and raising
`outside` adds tension notes to the same skeleton. Depending on the strategy, a chord may reuse the first chord's shape
adapted to its own tones (motif repetition).

## Limitations

- No rhythm; the grid is a placeholder.
- The key is estimated (weighted toward the first chord). Override with `--key` if it is wrong.
- No guitar layer (string/fret mapping, playability); only a pitch-range limit.
- The score is heuristic.
- Manual chords assume 4/4 and give every chord the same length (`--bars`); several chords per bar are not supported yet.
- A slash chord's bass note is added to the chord tones but is not shown in the chord label.

## Project layout

```
riffgen/
├── io_midi.py     MIDI reading/writing
├── analysis.py    chord segmentation, chord and key detection
├── generator.py   strategies, outside control, diversity filter
├── scoring.py     role labels and consonance score
├── report.py      report.txt / candidates.json
├── gui.py         local web server
├── index.html     the UI (piano roll + audio preview)
├── i18n.py        English/Turkish strings
└── cli.py         command line
tests/             python -m pytest
```

## Tests

```bash
pip install pytest
python -m pytest
```

## License

[MIT](LICENSE)
