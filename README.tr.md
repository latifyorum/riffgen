# riffgen

**Akor dizisi MIDI'sinden riff fikirleri üreten, yazma bloğu kırıcı bir araç.**

[English](README.md) · Türkçe

Bir akor dizisini MIDI olarak verirsin; riffgen o akorların üzerine oturan, rol etiketli **perde dizileri** (riff fikirleri)
üretir. Ritim üretmez: notalar her akorun süresine eşit aralıklı bir ızgaraya yerleşir (yer tutucu). Ritmi, vuruş
yerlerini ve son kararı sen verirsin. Amaç "doğru riff" yazmak değil, çeşitli ve beklenmedik hammadde sunmaktır.

## Özellikler

- Akor ve tonalite tespiti (arpej ve yoğun akor izleri için sabit pencere modu)
- 6 strateji: `ostinato`, `arpeggio`, `pedal`, `melodic`, `angular`, `crawl`
- **Outside** ayarı: akor ve gamın ne kadar dışına çıkılacağını 0-1 arasında kontrol eder
- **Sweep** modu: aynı iskeleti 5 farklı outside seviyesinde üretir, "dışarının" ne kattığını duyarsın
- Her nota rol etiketli (anchor / color / tension) ve sezgisel bir uyum skoru
- Birbirine çok benzeyen adaylar elenir
- Aynı seed aynı sonucu verir
- Tarayıcıda çalışan yerel arayüz: piano roll, ses önizleme, .mid indirme
- Komut satırı arayüzü
- Tek bağımlılık: [mido](https://github.com/mido/mido)

## Dil

Arayüz, konsol çıktısı ve rapor İngilizce ve Türkçe destekler. Varsayılan İngilizcedir. Türkçe için `--lang tr` (örn. `python -m riffgen akorlar.mid --lang tr`, `python start_gui.py --lang tr`) ya da `RIFFGEN_LANG=tr` ortam değişkenini kullan. Web arayüzünde sağ alttaki **TR/EN** düğmesi dili değiştirir; tercih tarayıcıda hatırlanır.

## Hızlı başlangıç

```bash
git clone https://github.com/latifyorum/riffgen.git
cd riffgen
pip install -r requirements.txt

python make_demo.py              # demo_chords.mid üretir (Am | F | Dm | E)
python -m riffgen.gui            # tarayıcıda arayüzü açar (veya start_gui.py'ye çift tıkla)
python -m riffgen demo_chords.mid   # veya komut satırından 16 aday üretir
```

Python 3.12'de test edildi; 3.9+ ile uyumlu olması hedeflenmiştir.

## Arayüz

`python -m riffgen.gui` komutu `http://127.0.0.1:8765` adresinde yerel bir sayfa açar.

1. Akor MIDI'sini seç, ayarları yap, **Üret** (İngilizce arayüzde **Generate**) düğmesine bas.
2. Adayı listeden seç: piano roll'da rol renkleriyle görünür (yeşil anchor, sarı color, kırmızı tension) ve otomatik çalar.
3. **↑/↓** aday seçer, **Boşluk** oynatır/durdurur.
4. **Bu adayı indir** tek aday, **Hepsini indir** tüm adaylar (ayrı track'ler) olarak .mid verir.

`start_gui.py` dosyasına çift tıklayarak da başlatabilirsin (hangi klasörde olduğu fark etmez). Siyah pencere sunucudur: kapatırsan arayüz durur. Çift tıklayınca bir editör açılıyorsa dosyaya sağ tıkla, *Birlikte aç* ile Python'u seç. Port doluysa otomatik sonraki port denenir.

Sunucu yalnızca bu bilgisayardan erişilebilir (127.0.0.1). Ses önizlemesi basit bir tarayıcı sentezidir; amaç notaları
duymak, tını seçmek değil. `--port` ve `--no-browser` bayrakları vardır.

## Komut satırı

```bash
python -m riffgen akorlarim.mid                  # 16 aday, outside 0'dan 0.9'a yayılır
python -m riffgen akorlarim.mid --sweep -n 4     # 4 iskelet x 5 outside seviyesi
python -m riffgen akorlarim.mid --key Em --grid 0.25 --seed 7
```

Çıktılar `riffgen_out/<dosya adı>/` içine yazılır:

| Dosya | İçerik |
|---|---|
| `01_ostinato_o000_s339564.mid` ... | Her aday ayrı MIDI. Ad: sıra, strateji, outside seviyesi, seed |
| `all_candidates.mid` | Hepsi tek dosyada, her aday ayrı track |
| `report.txt` | Akor akor nota isimleri, rol işaretleri ve skorlar |
| `candidates.json` | Aynı bilgi makine okunur biçimde |

| Bayrak | Anlamı |
|---|---|
| `-n 16` | Aday sayısı (sweep'te iskelet sayısı) |
| `--grid 0.5` | Nota başına vuruş. 1 = dörtlük, 0.5 = sekizlik, 0.25 = onaltılık |
| `--outside 0.4` | Tüm adaylar için sabit outside seviyesi (0-1) |
| `--outside-range 0 0.9` | Adaylar bu aralıkta güvenliden riskliye yayılır (varsayılan) |
| `--sweep` | Her iskelet için 5 outside seviyesi (0, .25, .5, .75, 1) |
| `--strategies crawl pedal` | Yalnızca bu stratejiler |
| `--key Am` | Tonaliteyi elle belirle (`F#m`, `Bb`, `"C minor"`) |
| `--window 4` | Akorları sabit pencerelerle (vuruş) çöz; arpej veya yoğun akor izleri için |
| `--low 40 --high 72` | Perde aralığı (MIDI numarası; 40 = E2, 72 = C5) |
| `--seed 7` | Aynı seed aynı sonucu verir |
| `--no-loop` | Son akordan ilkine geçişi hesaba katma |
| `--flat-velocity` | Velocity'yi role göre kodlama |
| `--lang tr` | Arayüz dili: `en` (varsayılan) veya `tr`; `RIFFGEN_LANG` ile de ayarlanır |

## Rol etiketleri

Her nota, üretildiği anki niyete değil, sonuçta ortaya çıkan perdeye göre etiketlenir:

- **anchor**: akorun içinde bir ses. Uzun ve güçlü vuruşa uygun. Velocity 100.
- **color**: tonalitenin gamından ama akor dışı. Velocity 84.
- **tension**: gam dışı. Kısa ve zayıf vuruşta renk gibi, uzun ve güçlü vuruşta hata gibi duyulur. Velocity 66.

`report.txt` içinde işaretler: düz = anchor, `~` = color, `!` = tension.

Tension notaları üç türden gelir: **approach** (sonraki akor sesine yarım ton yaklaşan, her zaman çözülür),
**modal** (b2, b5, minörde doğal 7 gibi karakteristik "dışarı" sesler) ve **chromatic** (önceki notanın yarım ton
komşusu, yalnızca yüksek outside'da). Tension yalnızca ızgaranın zayıf (tek numaralı) konumlarına konur.

## Uyum skoru

0-100 arasıdır; 100 = tüm notalar akor sesi. Her notanın akordaki seslerle yarım ton, tritone ve ikili sürtünmesine
bakar. Gam içindeki notalar ve akor sesine adımla çözülen tension notaları daha hafif cezalanır.
**Bu sezgisel bir göstergedir, hüküm değil.** Adayları sıralamak için kullan; "kulağa uyumlu geliyor mu" sorusunun
cevabı parçanın içinde, kulağında.

## Nasıl çalışır

```
akor MIDI → akor/tonalite analizi → strateji + outside → perde dizisi → rol etiketi + skor → MIDI / arayüz
```

Her rastgele karar tek bir seed'den önceden çekilen tablodan gelir; bu yüzden aynı seed aynı riff'i verir ve outside
yükseldikçe aynı iskelete tension notaları eklenir. Bir akor, stratejiye göre ilk akorun şeklini kendi seslerine
uyarlayarak tekrar edebilir (motif tekrarı).

## Sınırlar

- Ritim yok; ızgara yer tutucu.
- Tonalite tahmin edilir (ilk akor ağırlıklı). Yanlışsa `--key` ile düzelt.
- Gitar katmanı (perde/tel haritası, oynanabilirlik) yok; yalnızca perde aralığı sınırı var.
- Uyum skoru sezgiseldir.

## Proje yapısı

```
riffgen/
├── io_midi.py     MIDI okuma/yazma
├── analysis.py    akor segmentasyonu, akor ve tonalite tespiti
├── generator.py   stratejiler, outside kontrolü, çeşitlilik filtresi
├── scoring.py     rol etiketleri ve uyum skoru
├── report.py      report.txt / candidates.json
├── gui.py         yerel web sunucusu
├── index.html     arayüz (piano roll + ses önizleme)
├── i18n.py        İngilizce/Türkçe metinler
└── cli.py         komut satırı
tests/             python -m pytest
```

## Test

```bash
pip install pytest
python -m pytest
```

## Lisans

[MIT](LICENSE)
