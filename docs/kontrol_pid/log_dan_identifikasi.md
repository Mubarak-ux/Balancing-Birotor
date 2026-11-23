# Log Uji PID dan Identifikasi Model

Riwayat 7 uji PID di alat (18-11-2026) dan model rig yang dicocokkan dari data itu. Pengukuran
terbaru (23-11-2026) untuk k, τ, dan T_delay ada di
[`../pengukuran/detail_pengukuran.md`](../pengukuran/detail_pengukuran.md).

| Bagian | Isi |
|---|---|
| 1 | Log uji: gain, hasil, temuan, dan perbaikan tiap uji. Gain terpilih Kp 3 / Ki 2 / Kd 1 |
| 2 | Identifikasi model (k, lag motor, delay) dan tuning robust dari simulasi |

---

## Bagian 1. Log uji PID hardware (18-11-2026)

F-max 15 % kecuali disebut lain. Data di folder `data/2026-11-18_uji_pid/`.

| # | File | Gain Kp/Ki/Kd | Hasil | Temuan → perbaikan |
|---|---|---|---|---|
| 1 | `hw_20261118_171405_percobaanPID` | 3 / 1,5 / 1 | Osilasi ±3,6°, periode 1,1 s | Loop PID turun ke **25 Hz** (ledcWrite memblokir) → tulis ESC di task core 0, loop kembali 500 Hz. Getaran accel 0,21 g → filter τ 0,7 s, DLPF 21 Hz |
| – | (F-max 10 %) | – | Motor nyala, batang diam | Bias 11 % > F-max → koreksi 0. Bias jadi tengah rentang (8+Fmax)/2 |
| 2 | `hw_20261118_172326_testPID_2` | 1,5 / 0,6 / 1 | Motor kiri lambat, batang tertahan 14 s di +31° walau perintah 15/8 % | Desync start ESC → **soft-start** + pembatas laju 40 %/s. Integral windup → I-zone. Torsi tetap → **Trim** |
| 3 | `hw_20261118_175551_strat_trim` | 1,5 / 0,6 / 1 | Soft-start berhasil. Sp 0: std 2,9° → 2,2° setelah trim | – |
| 3b | `hw_20261118_175628_-10` | 1,5 / 0,6 / 1 | Overshoot 60 % (+10), ~100 % (−10), settling 6–8 s | Identifikasi: plant **tidak stabil** (k < 0) → Kp naik, I-zone 3° |
| 4 | `hw_20261118_180422_starttrimke2` | 2,5 / 2 / 1 | Sp 0: std 2,3° → 1,8° setelah trim (trim ≈ −13) | – |
| 4b | `hw_20261118_180513_-_10kedua` | 2,5 / 2 / 1 | **+10: rata 9,9°, std 0,45°**, overshoot 2,9°. −10: tertahan di −17° | I-zone 3° menahan integral saat \|e\| > 3° → I-zone 6°, gain robust 2 / 1,5 / 1 |

| 5 | `hw_20261118_181415_trimke3` | 2 / 1,5 / 1 | Sp 0: std 1,8° (sebelum trim) / 2,4° (sesudah, trim ≈ −10) | Osilasi ~2° tidak berubah walau gain diganti → kemungkinan besar dari gangguan fisik (pusat massa, turbulensi), bukan gain |
| 5b | `hw_20261118_181451_-_10_ketiga` | 2 / 1,5 / 1 | +10: rata 10,7°, std 2,1°, overshoot 5,9°. **−10: tertahan di −22,4°** | Integral **mati** di luar I-zone 6° (error 12°) → integral di luar zona kini **diperlambat 50 %**, bukan dimatikan. Torsi jatuh sisi negatif lebih besar (perlu u ≈ +10 % di −22° vs −11 % di 0°) |
| 6 | `hw_20261118_182146_setpoint_-_10keempat` | 2 / 1,5 / 1 (integral 50 % di luar zona) | **−10 tercapai**: rata −9,1° (3 s terakhir), std 1,4°. +10: rata 10,6°, std 1,7°. Overshoot: +10 → 17,1°, −10 → −22,1°. Settling ~9 s | Error tunak teratasi. Sisa: overshoot besar (terutama sisi negatif) & goyangan ~1,5° → perbaikan fisik / uji Kp 2,5 |
| 7 | `hw_20261118_184438_-_10PID3_2_1` | **3 / 2 / 1** | 0: rata +0,3°, std 0,55°. **+10: rata 9,6°, std 0,40°, lewat 4,9°, tenang 2,3 s.** −10: rata −10,2°, std 0,76°, lewat 9,3°, masuk ±1,5° ~3 s. +20: rata 20,2°, std 0,51°, lewat 10,8°. −20 (step 40°): rata −19,8°, std 1,3°, sempat ke batas mekanik | **Gain terbaik sejauh ini** → jadi default. Sisa: overshoot sisi negatif & step besar (torsi jatuh sisi negatif) |

### Gain terpilih

Default GUI sekarang **Kp 3,0 / Ki 2,0 / Kd 1,0** (uji ke-7), I-zone 6° + integral 50 % di luar zona, F-max 15 %.
Prosedur: start + trim di 0°, lalu step 0 → +10 → 0 → −10 → 0 (tiap 8 s).

---

## Bagian 2. Identifikasi model rig dari data PID

**Metode:** simulasi loop tertutup (PID firmware yang sama, setpoint & trim dari
CSV) dicocokkan ke sudut terukur dengan Nelder-Mead.
**Data** (`data/2026-11-18_uji_pid/`): `hw_20261118_175628_-10.csv` (Kp 1,5 / Ki 0,6 / Kd 1,0) dan
`hw_20261118_180513_-_10kedua.csv` (Kp 2,5 / Ki 2,0 / Kd 1,0).

### Model

```
J·θ̈ = L·g_F·(F2 − F1) − b·θ̇ − k·θ + c0
F_i  : orde-1 (lag τ) + delay, dari throttle lewat F(u) = 0,1241·u − 0,316 N
```

J = 0,0140 kg·m², b = 0,033 N·m·s/rad, L = 0,25 m (dari pengukuran sebelumnya).

### Hasil

| Parameter | Fit data Kp 1,5 | Fit gabungan 2 data | Satuan |
|---|---|---|---|
| **k** | −0,081 | −0,054 | N·m/rad |
| τ (lag motor + baling) | 0,15 | 0,10 | s |
| delay | 0,05 | 0,03 | s |
| g_F (skala thrust) | 1,09 | 0,74 | – |
| RMS error sudut | 2,3 | 2,5 | ° |

Validasi: dengan gain 1,5/0,6/1,0 model memberi overshoot ~60 % dan settling
~7,5 s untuk step 10°, sama dengan data.

### Interpretasi

- **k negatif → batang tidak stabil alami** (seperti pendulum terbalik): makin
  miring, makin kuat jatuh ke sisi itu. Cocok dengan batang yang selalu diam di
  batas mekanik (±31–33°) saat motor mati.
- Uji ayunan 11-11 (`docs/pengukuran/detail_pengukuran.md`, Bagian 2) memberi k = +0,039 (stabil). Kemungkinan
  susunan rig berubah sejak itu (ESP32/kabel di atas poros menaikkan pusat massa).
  Perlu dicek ulang.
- Parameter berbeda antar data (k −0,05..−0,08, g_F 0,7..1,1) → tuning dibuat
  **robust**: gain diuji pada beberapa varian model (τ ×1,6, delay +40 ms) plus
  noise sensor dan torsi turbulen acak.

### Tuning robust (simulasi, step 0 → +10 → −10°)

| Kp/Ki/Kd, I-zone | Error tunak maks | Std sudut | Overshoot maks |
|---|---|---|---|
| 2,5 / 2,0 / 1,0, 3° (uji ke-4) | 3,9° | 0,89° | 7,2° |
| **2,0 / 1,5 / 1,0, 6°** | **0,2°** | **0,48°** | **4,8°** |
| 2,0 / 0,8 / 1,0, tanpa I-zone | 0,2° | 0,46° | 6,9° |

- I-zone 3° menahan error tunak sampai ~4° (integral tidak jalan jika |e| > 3°).
- Kp 2,5 menambah osilasi; Kp 2,0 paling tenang di semua varian model.
- Osilasi kecil (~0,5°) tetap ada di model karena turbulensi/variasi thrust; tidak
  realistis mengharapkan sudut benar-benar diam.

### Cara paling efektif mengurangi osilasi (fisik)

Turunkan/seimbangkan pusat massa batang (pindahkan PCB/kabel ke bawah atau dekat
poros) agar k mendekati 0 atau positif, dan seimbangkan baling-baling.
