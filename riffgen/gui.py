"""Local web UI: python -m riffgen.gui   (serves http://127.0.0.1:8765, standard library only)."""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import i18n
from .analysis import detect_key, parse_chords_text, parse_key, segment_chords, validate_manual_params
from .generator import Context, generate_candidates
from .io_midi import read_midi, write_midi
from .i18n import t
from .report import filename

INDEX = os.path.join(os.path.dirname(__file__), "index.html")
STATE: dict = {}  # last generation (single-user, local)
UI_LANG = "en"  # language the page starts in (the user can toggle it)


def _track(c):
    return f"{c.index:02d} {c.strategy} o{int(round(c.outside * 100))}", c.notes


def generate(midi_bytes: bytes, q: dict) -> dict:
    """Run the full pipeline; returns the JSON payload the page draws from."""
    i18n.set_lang(q.get("lang", UI_LANG))
    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
        f.write(midi_bytes)
        path = f.name
    try:
        song = read_midi(path)
    except Exception as e:  # mido raises on files that are not MIDI
        raise ValueError(t("err.midi_read", e=e))
    finally:
        os.unlink(path)

    chords = segment_chords(song, window_beats=float(q["window"]) if q.get("window") else None)
    key = parse_key(q["key"]) if q.get("key") else detect_key(song, first_chord=chords[0])
    ctx = Context(song=song, chords=chords, key=key, grid=float(q.get("grid", 0.5)))
    cands, seed = generate_candidates(
        ctx,
        count=max(1, min(64, int(q.get("count", 16)))),
        outside_range=(float(q.get("olo", 0)), float(q.get("ohi", 0.9))),
        seed=int(q["seed"]) if q.get("seed") else None,
        sweep=q.get("sweep") == "1",
    )
    STATE.update(song=song, cands={c.index: c for c in cands})

    flats = key.flats
    return {
        "key": str(key), "bpm": round(song.bpm, 1), "tpb": song.ticks_per_beat, "seed": seed,
        "total": max(c.end for c in chords),
        "chords": [{"n": c.label(flats), "s": c.start, "e": c.end, "tones": list(c.tones)} for c in chords],
        "candidates": [
            {"i": c.index, "s": c.strategy, "o": c.outside, "g": c.group, "m": c.metrics,
             "n": [{"p": n.pitch, "t": n.tick, "l": n.length, "r": n.role} for n in c.notes]}
            for c in cands
        ],
    }


def generate_from_chords(q: dict) -> dict:
    """Run the pipeline from a manual chord text; returns the same JSON payload as generate()."""
    from .models import Song  # local import to avoid circular issues at module level
    i18n.set_lang(q.get("lang", UI_LANG))

    chord_text = q.get("chords_text", "").strip()
    if not chord_text:
        raise ValueError(t("err.no_chord_text"))

    bpm, bars_per_chord = validate_manual_params(q.get("bpm", 120), q.get("bars", 1))
    tempo = int(60_000_000 / bpm)
    tpb = 480

    chords = parse_chords_text(chord_text, bars_per_chord=bars_per_chord, bpm=bpm, ticks_per_beat=tpb)

    # Build a synthetic Song whose notes are the chord tones (one note per chord tone per bar)
    from .models import MidiNote
    notes = []
    for ch in chords:
        for pc in ch.tones:
            midi_pitch = 48 + pc  # octave 3
            notes.append(MidiNote(pitch=midi_pitch, start=ch.start, end=ch.end, velocity=80))

    song = Song(ticks_per_beat=tpb, tempo=tempo, numerator=4, denominator=4, notes=notes)

    key = parse_key(q["key"]) if q.get("key") else detect_key(song, first_chord=chords[0])
    ctx = Context(song=song, chords=chords, key=key, grid=float(q.get("grid", 0.5)))
    cands, seed = generate_candidates(
        ctx,
        count=max(1, min(64, int(q.get("count", 16)))),
        outside_range=(float(q.get("olo", 0)), float(q.get("ohi", 0.9))),
        seed=int(q["seed"]) if q.get("seed") else None,
        sweep=q.get("sweep") == "1",
    )
    STATE.update(song=song, cands={c.index: c for c in cands})

    flats = key.flats
    return {
        "key": str(key), "bpm": round(bpm, 1), "tpb": tpb, "seed": seed,
        "total": max(c.end for c in chords),
        "chords": [{"n": c.label(flats), "s": c.start, "e": c.end, "tones": list(c.tones)} for c in chords],
        "candidates": [
            {"i": c.index, "s": c.strategy, "o": c.outside, "g": c.group, "m": c.metrics,
             "n": [{"p": n.pitch, "t": n.tick, "l": n.length, "r": n.role} for n in c.notes]}
            for c in cands
        ],
    }


def midi_for(which: str):
    """(download name, bytes) for one candidate index or 'all'; None if unknown."""
    cands = STATE.get("cands")
    if not cands:
        return None
    buf = io.BytesIO()
    if which == "all":
        write_midi(buf, STATE["song"], [_track(c) for c in cands.values()])
        return "all_candidates.mid", buf.getvalue()
    c = cands.get(int(which))
    if c is None:
        return None
    write_midi(buf, STATE["song"], [_track(c)])
    return filename(c), buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            with open(INDEX, "rb") as f:
                return self._send(200, f.read().replace(b"__LANG__", UI_LANG.encode()), "text/html; charset=utf-8")
        m = re.fullmatch(r"/midi/(all|\d+)\.mid", path)
        got = midi_for(m.group(1)) if m else None
        if got:
            name, data = got
            return self._send(200, data, "audio/midi", {"Content-Disposition": f'attachment; filename="{name}"'})
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/generate":
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            q = {k: v[0] for k, v in parse_qs(u.query).items() if v and v[0] != ""}
            try:
                self._send(200, json.dumps(generate(body, q)).encode(), "application/json")
            except Exception as e:
                self._send(400, json.dumps({"error": str(e)}, ensure_ascii=False).encode(), "application/json")
        elif u.path == "/api/generate_chords":
            self.rfile.read(int(self.headers.get("Content-Length", 0)))  # ignore body
            q = {k: v[0] for k, v in parse_qs(u.query).items() if v and v[0] != ""}
            try:
                self._send(200, json.dumps(generate_from_chords(q)).encode(), "application/json")
            except Exception as e:
                self._send(400, json.dumps({"error": str(e)}, ensure_ascii=False).encode(), "application/json")
        else:
            self._send(404, b"not found", "text/plain")


def main(argv=None) -> int:
    global UI_LANG
    argv = sys.argv[1:] if argv is None else list(argv)
    UI_LANG = i18n.pick_lang(argv)
    i18n.set_lang(UI_LANG)
    p = argparse.ArgumentParser(prog="riffgen.gui", description=t("g.desc"))
    p.add_argument("--port", type=int, default=8765, help=t("h.port"))
    p.add_argument("--no-browser", action="store_true", help=t("h.nobrowser"))
    p.add_argument("--lang", choices=sorted(i18n.STRINGS), default=None, help=t("h.lang"))
    args = p.parse_args(argv)

    server = None
    for port in range(args.port, args.port + 10):  # busy port (e.g. a window still open): try the next
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), Handler)  # local only
            break
        except OSError:
            continue
    if server is None:
        raise SystemExit(t("err.ports", a=args.port, b=args.port + 9))
    url = f"http://127.0.0.1:{port}"
    print(t("g.url", url=url))
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n" + t("g.closed"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
