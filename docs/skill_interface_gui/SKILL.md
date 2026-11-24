---
name: gui-panel-instrumen
description: Membuat atau mengubah antarmuka desktop PySide6 + pyqtgraph bergaya "panel instrumen laboratorium" seperti GUI Balancing Propeller (app/). Pakai skill ini SEBELUM menulis kode Qt/QSS apa pun di proyek ini, saat menambah kartu/panel/tombol/grafik/dialog baru, saat membuat GUI baru yang harus serupa tampilannya (praktikum kontrol, monitoring sensor, telemetri serial), atau saat diminta "samakan gaya dengan GUI BP", "tambah panel", "buat dashboard kontrol", "rapikan tampilan".
---

# Skill: Antarmuka Panel Instrumen (PySide6)

Gaya GUI ini: **panel instrumen laboratorium, Swiss/fungsional**. Latar biru
langit lembut, panel putih, garis tipis 1 px, **sudut tegas (radius 0)**, satu
warna aksen. Data harus terbaca cepat; hiasan tidak boleh ada.

Kode acuan:

| Berkas | Isi |
|---|---|
| `app/config.py` | Token warna & font (satu-satunya sumber warna) |
| `app/theme.py` | Stylesheet global `QSS` + `STATUS_COLORS` |
| `app/main.py` | Setup `QApplication`: Fusion, palet terang paksa, font, splash |
| `app/widgets/controls.py` | `Card`, `Section`, `Param`, `ParamBox`, `Readout`, `GainBox`, `Metric` |
| `app/widgets/dialogs.py` | `NoticeDialog`, `confirm()`, `notify()` (pengganti QMessageBox) |
| `app/widgets/beam_view.py` | Visual 2D custom dengan `QPainter` |
| `app/main_window.py` | Tata letak jendela, grafik, tab, tabel |

---

## 1. Aturan inti (wajib)

1. **Warna hanya dari `config.py`.** Jangan menulis hex baru di widget. Kalau
   perlu warna baru, tambahkan konstanta bernama di `config.py` dengan komentar
   fungsinya.
2. **Satu aksen saja: `ACCENT` (azure #0369A1)**, untuk setpoint dan aksi utama.
   Warna lain wajib bermakna status:
   - `GREEN` = aktif/aman, `AMBER` = peringatan/terbatas, `RED` = bahaya/stop/batas
   - `PURPLE` khusus suku D dan laju sudut (ω) di grafik
   - `MUTED` = idle/teks sekunder
3. **`border-radius: 0` di mana-mana.** Tanpa gradien, bayangan, glassmorphism,
   emoji, atau ikon dekoratif.
4. **Gaya lewat `objectName` + QSS global**, bukan `setStyleSheet` inline.
   Inline hanya untuk nilai dinamis (mis. warna angka berubah sesuai status)
   atau widget mandiri seperti `GainBox`/`Metric`/dialog.
5. **Garis, bukan kotak.** Pemisah = garis 1 px `BORDER`; judul seksi = garis
   tinta `INK` 1 px; tab = garis bawah 2 px aksen.
6. **Angka pakai font angka.** Pembacaan besar: `TITLE_FONT` (Helvetica/Arial
   bold). Spinbox, tabel, chip status: `MONO` (Consolas).
7. **Teks UI berbahasa Indonesia**, judul kartu & label kecil HURUF KAPITAL
   dengan letter-spacing 1.0–1.2. Istilah teknis boleh tetap Inggris (Setpoint,
   Load mass, overshoot).
8. **Setiap kontrol punya tooltip** yang menjelaskan rumus/satuan/shortcut.
9. **Palet terang dipaksa** (`_light_palette()` di `main.py`) supaya dark mode
   Windows tidak merusak tabel/header native. Jangan dihapus.

---

## 2. Token desain

```python
# app/config.py
BG = "#F2F6FB"        # latar jendela
SURFACE = "#F8FAFD"   # header & strip
CARD = "#FFFFFF"      # panel
CARD_ALT = "#F4F8FC"  # baris selang-seling / tile / disabled
BORDER = "#D7E1EC"    # garis tipis
INK = TEXT = RULE = "#16263A"   # tinta utama
MUTED = "#64748B"
ACCENT = "#0369A1";  ACCENT_DARK = "#075985"
AMBER = "#B45309";   AMBER_SOFT = "#FDF3E3"
GREEN = "#15803D";   RED = "#C0392B";   PURPLE = "#7C3AED"
MONO = "Consolas"
TITLE_FONT = "'Helvetica', 'Arial', sans-serif"
SUB_FONT = "'Plus Jakarta Sans', 'Segoe UI', sans-serif"   # dari app/assets/fonts
```

Skala tipografi (px):

| Peran | Ukuran | Bobot | Font |
|---|---|---|---|
| Teks dasar | 12 | normal | Segoe UI |
| Judul aplikasi | 15 | 700 | Segoe UI |
| Judul kartu / section | 10 | 700, KAPITAL | Segoe UI |
| Label parameter | 11 | 600 | Segoe UI |
| Judul readout | 9 | 700, KAPITAL, `MUTED` | Segoe UI |
| Angka readout besar / kecil | 24 / 17 | 700 | TITLE_FONT |
| Nilai metrik | 15 | 700 | Consolas |
| Spinbox, tabel, chip | 10–11 | — | Consolas |

Jarak: margin kartu `14,10,14,12`, spasi isi kartu 8, antar kartu 10,
margin body jendela 14/12, splitter handle 8 px.

---

## 3. Struktur jendela

```
┌──────────────────────────────────────────────────────────────────────┐
│ Header (54px, SURFACE): [BP] Judul [KELOMPOK] sub · anggota  (●pill) [Primary] │
├──────────────────────────────────────────────────────────────────────┤
│ TopStrip (CARD): logo afiliasi ..................... [STATUS CHIP]   │
├──────────────────────────────────────────────┬───────────────────────┤
│ Splitter vertikal (kiri, stretch 1)          │ ScrollArea panel      │
│ ┌───────────────────────┬──────────────────┐ │ (340–560 px)          │
│ │ Visual 2D (QPainter)  │ Card grafik      │ │  Card Sumber data     │
│ │ ReadoutBar 5 kolom    │ (selalu tampil)  │ │  Card Toggle (Hero)   │
│ └───────────────────────┴──────────────────┘ │  Card Kontrol PID     │
│ ┌──────────────────────────────────────────┐ │  Card Masukan         │
│ │ Card Telemetri: QTabWidget (documentMode)│ │  Card Performa        │
│ │  Respons | Suku PID | Error & ω | Log |… │ │  Grid tombol aksi     │
│ └──────────────────────────────────────────┘ │  stretch              │
└──────────────────────────────────────────────┴───────────────────────┘
```

Aturan tata letak:
- Root `QVBoxLayout` margin 0 spasi 0: header → topstrip → body.
- Semua pembagi area = `QSplitter` dengan `setChildrenCollapsible(False)`,
  stretch factor eksplisit, dan **state disimpan** via `QSettings`
  (`saveState()`/`restoreState()` di `closeEvent` dan akhir `__init__`).
- Panel kanan selalu di `QScrollArea` (`setWidgetResizable(True)`), lebar
  minimum = `panel.minimumSizeHint().width() + lebar scrollbar`.
- Jendela dibuka `showMaximized()`.
- Hierarki informasi: **(1) readout & chip status → (2) kartu → (3) `Section`
  lipat** untuk pengaturan jarang dipakai.

---

## 4. Komponen siap pakai

Selalu pakai komponen di `app/widgets/controls.py` sebelum membuat yang baru.

```python
from .widgets.controls import Card, Section, Param, ParamBox, Readout, GainBox, Metric

# Kartu: judul KAPITAL + subjudul kanan + garis tinta. Isi ke card.body.
card = Card("Kontrol PID", "Kp · Ti · Td")
card.head.addWidget(tombol_kecil)          # tombol di header (mis. gembok)

# Parameter slider + spinbox tersinkron (sinyal changed(float))
kp = Param("Kp", 0, 5, 3.0, 0.05, "%/°", dec=2)
kp.changed.connect(self.on_gains)
kp.set_value_silent(2.5)                   # ubah tanpa memicu sinyal
kp.set_locked(True)                        # nonaktifkan input

# Parameter tanpa slider (jarang diubah), opsi centang "∞"
ti = ParamBox("Ti", 0.1, 30, 1.5, 0.1, "s", 2, off_label="∞")

# Pembacaan besar (strip readout); warna angka dinamis lewat set()
ro = Readout("Sudut θ", "°", tooltip="Sudut batang terukur")
ro.set(f"{th:+.2f}", AMBER if abs(err) > 3 else None)

# Kotak gain turunan (hanya baca), kuning jika dibatasi
box = GainBox("Ki", "%/(°·s)", "Ki = Kp / Ti")
box.set("2.000", limit=False)

# Tile metrik (grid 2 kolom)
m = Metric("Overshoot", tooltip="Mp = ...");  m.set("4.2 %")

# Seksi lipat tingkat-3 (grid 4 kolom)
sec = Section("Lanjutan", expanded=False)
sec.add(widget, row=0)                     # colspan default 4
```

Untuk widget baru: buat kelas di `controls.py`, beri `setObjectName(...)`,
tambahkan aturan QSS di `theme.py`, ekspor di `widgets/__init__.py`.

---

## 5. Tombol (objectName → peran)

| objectName | Tampilan | Pakai untuk |
|---|---|---|
| *(default)* | putih, garis `BORDER`, hover garis `INK` | aksi biasa |
| `Primary` | isi `INK`, hover `ACCENT` | aksi utama dalam kartu (Hubungkan, Pause, Catat) |
| `Hero` | isi `ACCENT`, 13px bold, padding besar | **satu** aksi terpenting di layar (Mulai PID) |
| `HeroStop` | isi `RED` | keadaan "berjalan" dari tombol Hero |
| `Danger` | garis & teks `RED`, hover isi merah | Reset, Stop motor, Rekam |
| `Warning` | garis `ACCENT`, teks `ACCENT_DARK` | aksi yang mengubah keadaan (step setpoint) |
| `Lock` | kecil, mono; checked = isi `AMBER` | gembok/kunci input |
| `SectionHead` | teks rata kiri + garis atas | kepala `Section` |

Ganti peran tombol saat runtime harus me-repolish:

```python
btn.setObjectName("HeroStop")
btn.style().unpolish(btn); btn.style().polish(btn)
```

Tombol aksi di panel kanan disusun dalam `QGridLayout` 2 kolom spasi 7;
tombol lebar penuh pakai `colspan=2`.

---

## 6. Status & umpan balik

- **Chip status** (`StatusChip`, TopStrip kanan): teks KAPITAL format
  `MODE · KEADAAN`, warna teks dan garis = warna status.
  `chip.setStyleSheet(f"color:{c}; border:1px solid {c};")`. Ubah hanya bila
  `(teks, warna)` berubah (cache di `self._chip_state`).
- **Pill koneksi** (`Pill` di header): `●` berwarna + teks mono.
- **Label keterangan** (`EventLabel`): teks `MUTED` 11px, `setWordWrap(True)`.
- **Dialog**: jangan pakai `QMessageBox`. Pakai
  `confirm(parent, level, judul, pesan, points=[...])` / `notify(...)`,
  `level` ∈ `info | warn | danger` (warna aksen, label `INFO/PERINGATAN/BAHAYA`,
  tanpa bingkai OS, garis tinta 2 px).

---

## 7. Grafik pyqtgraph

```python
pg.setConfigOptions(antialias=False, background=PLOT_BG, foreground=MUTED)

pl = pg.PlotWidget(background=PLOT_BG)
pl.setLabel("left", "Sudut θ", "°");  pl.setLabel("bottom", "Waktu", "s")
for ax in ("left", "bottom"):
    pl.getAxis(ax).setPen(pg.mkPen(BORDER)); pl.getAxis(ax).setTextPen(pg.mkPen(MUTED))
pl.hideButtons(); pl.setMenuEnabled(False); pl.showGrid(x=True, y=True, alpha=0.10)
pl.setXLink(plot_utama)                    # semua grafik waktu ditautkan sumbu-x

leg = pl.addLegend(offset=(12, 8), labelTextSize="8pt")
leg.setBrush(pg.mkBrush(255, 255, 255, 225)); leg.setPen(pg.mkPen(BORDER))

c = pl.plot(pen=pg.mkPen(INK, width=2), name="θ aktual")
c.setDownsampling(auto=True, method="peak"); c.setClipToView(True)
```

Konvensi pena:

| Sinyal | Pena |
|---|---|
| Nilai aktual / P / motor kiri | `INK`, 1.8–2 |
| Setpoint | `ACCENT`, 1.6, `DashLine` |
| Data mentah | `#BCC9D8`, 1 |
| I | `GREEN`, 1.8 |
| D / ω / motor kanan | `PURPLE`, 1.8 (motor kanan: `DashLine`) |
| Error | `RED`, 1.8 |
| Total u | `#8DA0B5`, 1.4, `DashLine` |
| Batas mekanik / batas maks | `RED`, 1, `DotLine` |
| Batas min | `MUTED`, 1, `DotLine` |
| Garis nol | `#C9D5E2`, 1 |
| Penanda event | `InfiniteLine` vertikal `AMBER` dash 1.2 |
| Pita toleransi | `LinearRegionItem` brush aksen alpha 22, zValue -10 |

Grafik selalu di dalam `Card`, atau di tab `QTabWidget` (`setDocumentMode(True)`)
yang dibungkus `Card`. Update data via timer `PreciseTimer` 20 ms (50 Hz),
buffer `collections.deque(maxlen=...)`.

---

## 8. Tabel

```python
tbl = QtWidgets.QTableWidget(0, len(headers))
tbl.setHorizontalHeaderLabels(headers)
tbl.verticalHeader().setVisible(False)
tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
tbl.setSelectionMode(QAbstractItemView.NoSelection)
tbl.setAlternatingRowColors(True); tbl.setShowGrid(False)
tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
```
Kolom 0 rata kiri, sisanya rata tengah; `scrollToBottom()` setelah tambah baris.
Header tabel bergaris bawah tinta (sudah di QSS).

---

## 9. Visual custom (QPainter)

Ikuti `BeamView`: `WA_OpaquePaintEvent`, isi latar `BG`, area gambar putih
dengan grid "kertas milimeter" `#EEF3F9` tiap 35 px, garis `BORDER`, objek
utama `INK`, setpoint `ACCENT`, batas `RED`. Skala dihitung dari ukuran widget
(`S = min(W/…, H/…)`) agar responsif. Interaksi (klik) dipancarkan sebagai
`Signal`, bukan memanggil logika langsung.

---

## 10. Setup aplikasi baru (kerangka)

```python
app = QtWidgets.QApplication(sys.argv)
for fn in os.listdir(fdir):                       # app/assets/fonts
    QtGui.QFontDatabase.addApplicationFont(os.path.join(fdir, fn))
app.setStyle("Fusion")
app.setPalette(_light_palette())                  # lihat app/main.py
app.setStyleSheet(QSS)                            # dari app/theme.py
```
Impor berat (pyqtgraph, numpy) dilakukan setelah splash tampil.
Windows: set `AppUserModelID` agar ikon taskbar benar.

---

## 11. Checklist sebelum selesai

- [ ] Tidak ada hex baru di luar `config.py` (kecuali abu-abu yang sudah dipakai di `theme.py`)
- [ ] Tidak ada `border-radius` > 0, gradien, bayangan, emoji
- [ ] Warna non-aksen hanya untuk makna status
- [ ] Hanya satu tombol `Hero` yang terlihat
- [ ] Widget baru punya `objectName` + aturan QSS, bukan inline statis
- [ ] Judul kartu/readout KAPITAL; angka pakai TITLE_FONT/MONO; satuan ditulis
- [ ] Tooltip ada pada setiap kontrol/readout baru
- [ ] Splitter baru ikut disimpan/dipulihkan di `QSettings`
- [ ] Panel kanan tetap bisa digulir dan tidak terpotong di lebar minimum
- [ ] Dialog memakai `confirm`/`notify`, bukan `QMessageBox`
- [ ] Teks Indonesia konsisten; perubahan nilai lewat kode memakai `set_value_silent`
