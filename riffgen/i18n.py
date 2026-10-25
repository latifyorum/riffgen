"""Tiny i18n layer. English is the default; Turkish via --lang tr, RIFFGEN_LANG=tr or the UI toggle."""
from __future__ import annotations

import os

LANG = "en"

STRINGS = {
    "en": {
        "err.no_notes": "No notes found in the MIDI file.",
        "err.no_chords": "Could not extract chord segments. Try a fixed window with --window.",
        "err.bad_key": "Could not parse key: {text!r} (examples: Am, F#m, Bb, C minor)",
        "err.midi_read": "Could not read MIDI: {e}",
        "err.ports": "Ports {a}-{b} are busy. Try another one with --port.",
        "err.low_high": "Error: --high must be at least one octave above --low.",
        "err.grid_count": "Error: --grid must be > 0 and --count >= 1.",
        "err.outside": "Error: outside values must be between 0 and 1.",
        "cli.desc": "Generate role-labelled pitch-sequence (riff idea) candidates from a chord-progression MIDI file.",
        "h.midi": "MIDI file containing the chord progression",
        "h.count": "number of candidates (skeletons in sweep mode)",
        "h.grid": "beats per note: 1=quarter, 0.5=eighth, 0.25=sixteenth (default 0.5)",
        "h.outside": "fixed 'outside' level for all candidates, 0..1",
        "h.orange": "candidates spread from safe to risky across this range (default 0 0.9)",
        "h.sweep": "5 outside levels (0, .25, .5, .75, 1) per skeleton",
        "h.strategies": "only use these strategies",
        "h.key": "set the key by hand (e.g. Am, F#m, Bb, 'C minor')",
        "h.window": "analyse chords in fixed windows (beats); for arpeggiated or busy chord tracks",
        "h.low": "lowest MIDI note (40 = E2)",
        "h.high": "highest MIDI note (72 = C5)",
        "h.seed": "same seed, same result",
        "h.noloop": "don't treat the last chord as leading back to the first",
        "h.flatvel": "don't encode the role in velocity (all 100)",
        "h.out": "output folder (default: riffgen_out/<file name>)",
        "h.lang": "interface language: en or tr (default: en, or RIFFGEN_LANG)",
        "h.port": "port (default 8765)",
        "h.nobrowser": "do not open the browser automatically",
        "c.key": "Key",
        "c.chords": "Chords",
        "c.seed": "Seed",
        "c.key_auto": "  (estimated; override with --key if wrong)",
        "c.th_strategy": "strategy",
        "c.th_outside": "outside",
        "c.th_score": "score",
        "c.th_tension": "tension",
        "c.th_unres": "unresolved",
        "c.done": "{n} candidates + all_candidates.mid + report.txt + candidates.json -> {dir}",
        "g.desc": "riffgen local web UI",
        "g.url": "riffgen UI: {url}  (Ctrl+C to quit)",
        "g.closed": "closed",
        "s.missing": "Missing package: {name}",
        "s.fix": "Fix: run  pip install mido  (on Windows, if that fails: py -m pip install mido)",
        "s.enter": "Press Enter to close...",
        "s.error": "Error: {e}",
        "r.title": "riffgen report: {source}",
        "r.head1": "BPM {bpm:.1f} | {num}/{den} | key {key} | seed {seed}",
        "r.head2": "grid {grid} beats/note | range {lo}–{hi} | loop {loop}",
        "r.yes": "yes",
        "r.no": "no",
        "r.chords": "Chords: ",
        "r.legend": "Marks: plain = anchor (chord tone) | ~ = color (in scale, not a chord tone) | ! = tension (outside the scale)",
        "r.note": "The consonance score is a heuristic (100 = all chord tones); use it to sort candidates, the final call is your ear's.",
        "r.metrics": "consonance {cons:5.1f} | anchor {a} color {c} tension {t} (unresolved {u}) | distinct pitch classes {d} | span {s} semitones",
        "r.strategies": "Strategies: ",
        "strat.ostinato": "root-heavy, repeating narrow line",
        "strat.arpeggio": "line sweeping through the chord tones up/down",
        "strat.pedal": "root pedal + moving upper voice",
        "strat.melodic": "melodic line flowing in scale steps",
        "strat.angular": "angular line leaping between chord tones",
        "strat.crawl": "chromatic/modal crawling line",
    },
    "tr": {
        "err.no_notes": "MIDI dosyasında nota bulunamadı.",
        "err.no_chords": "Akor segmenti çıkarılamadı. --window ile sabit pencere deneyin.",
        "err.bad_key": "Tonalite anlaşılamadı: {text!r} (örnek: Am, F#m, Bb, C minor)",
        "err.midi_read": "MIDI okunamadı: {e}",
        "err.ports": "{a}-{b} portları dolu. --port ile başka bir port dene.",
        "err.low_high": "Hata: --low ile --high arasında en az bir oktav olmalı.",
        "err.grid_count": "Hata: --grid > 0 ve --count >= 1 olmalı.",
        "err.outside": "Hata: outside değerleri 0 ile 1 arasında olmalı.",
        "cli.desc": "Akor dizisi MIDI'sinden rol etiketli perde dizisi (riff fikri) adayları üretir.",
        "h.midi": "akor dizisini içeren MIDI dosyası",
        "h.count": "aday sayısı (sweep modunda iskelet sayısı)",
        "h.grid": "nota başına vuruş: 1=dörtlük, 0.5=sekizlik, 0.25=onaltılık (varsayılan 0.5)",
        "h.outside": "tüm adaylar için sabit 'dışarı çıkma' seviyesi, 0..1",
        "h.orange": "adaylar bu aralıkta güvenliden riskliye yayılır (varsayılan 0 0.9)",
        "h.sweep": "her iskelet için 5 outside seviyesi (0, .25, .5, .75, 1) üret",
        "h.strategies": "yalnızca bu stratejileri kullan",
        "h.key": "tonaliteyi elle belirle (örn. Am, F#m, Bb, 'C minor')",
        "h.window": "akorları sabit pencerelerle (vuruş) çöz; arpej/yoğun akor izleri için",
        "h.low": "en düşük MIDI notası (40 = E2)",
        "h.high": "en yüksek MIDI notası (72 = C5)",
        "h.seed": "aynı seed aynı sonucu verir",
        "h.noloop": "son akordan ilkine geçişi hesaba katma",
        "h.flatvel": "velocity'yi role göre kodlama (hepsi 100)",
        "h.out": "çıktı klasörü (varsayılan: riffgen_out/<dosya adı>)",
        "h.lang": "arayüz dili: en veya tr (varsayılan: en, ya da RIFFGEN_LANG)",
        "h.port": "port (varsayılan 8765)",
        "h.nobrowser": "tarayıcıyı otomatik açma",
        "c.key": "Tonalite",
        "c.chords": "Akorlar",
        "c.seed": "Seed",
        "c.key_auto": "  (tahmin; yanlışsa --key ile değiştirin)",
        "c.th_strategy": "strateji",
        "c.th_outside": "outside",
        "c.th_score": "uyum",
        "c.th_tension": "tension",
        "c.th_unres": "çözülmemiş",
        "c.done": "{n} aday + all_candidates.mid + report.txt + candidates.json -> {dir}",
        "g.desc": "riffgen yerel web arayüzü",
        "g.url": "riffgen arayüzü: {url}  (kapatmak için Ctrl+C)",
        "g.closed": "kapatıldı",
        "s.missing": "Eksik paket: {name}",
        "s.fix": "Çözüm: komut satırına  pip install mido  yaz (Windows'ta olmazsa: py -m pip install mido)",
        "s.enter": "Kapatmak için Enter'a bas...",
        "s.error": "Hata: {e}",
        "r.title": "riffgen raporu: {source}",
        "r.head1": "BPM {bpm:.1f} | {num}/{den} | tonalite {key} | seed {seed}",
        "r.head2": "grid {grid} vuruş/nota | aralık {lo}–{hi} | döngü {loop}",
        "r.yes": "evet",
        "r.no": "hayır",
        "r.chords": "Akorlar: ",
        "r.legend": "İşaretler: düz = anchor (akor sesi) | ~ = color (gamdan, akor dışı) | ! = tension (gam dışı)",
        "r.note": "uyum skoru sezgisel bir göstergedir (100 = tamamen akor sesleri); sıralamak için kullanın, karar kulağınızın.",
        "r.metrics": "uyum {cons:5.1f} | anchor {a} color {c} tension {t} (çözülmemiş {u}) | farklı nota sınıfı {d} | ambitus {s} yarım ton",
        "r.strategies": "Stratejiler: ",
        "strat.ostinato": "kök ağırlıklı, tekrar eden dar hat",
        "strat.arpeggio": "akor seslerini yukarı/aşağı tarayan hat",
        "strat.pedal": "kök pedal + hareketli üst ses",
        "strat.melodic": "gam adımlarıyla akan melodik hat",
        "strat.angular": "akor sesleri arası sıçramalı, köşeli hat",
        "strat.crawl": "kromatik/modal sürünen hat",
    },
}


def set_lang(code) -> None:
    global LANG
    LANG = code if code in STRINGS else "en"


def pick_lang(argv=None) -> str:
    """--lang X / --lang=X in argv, else $RIFFGEN_LANG, else English."""
    argv = list(argv or [])
    for i, a in enumerate(argv):
        if a == "--lang" and i + 1 < len(argv):
            return argv[i + 1] if argv[i + 1] in STRINGS else "en"
        if a.startswith("--lang="):
            return a.split("=", 1)[1] if a.split("=", 1)[1] in STRINGS else "en"
    env = os.environ.get("RIFFGEN_LANG", "en")
    return env if env in STRINGS else "en"


def t(key: str, /, **kw) -> str:
    s = STRINGS[LANG].get(key) or STRINGS["en"][key]
    return s.format(**kw) if kw else s
