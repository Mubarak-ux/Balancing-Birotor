# Detail Pengukuran

Rincian metode, data, dan perhitungan tiap parameter plant. Ringkasan semua angka ada di
[`ringkasan_pengukuran.md`](ringkasan_pengukuran.md); dokumen ini dibuka bila perlu rinciannya.

| Bagian | Parameter | Hasil |
|---|---|---|
| 1 | Gaya dorong F | `F(u) = 0,1241·u − 0,316` N, 8 sampai 15 % |
| 2 | Redaman b | 0,033 N·m·s/rad (uji ayunan 11-11, k masih positif) |
| 3 | Kekakuan sudut k | −0,05 N·m/rad (−0,03 … −0,07), tidak stabil alami |
| 4 | Lag motor τ dan T_delay | τ 0,15 … 0,19 s, T_delay 0,06 … 0,085 s |

---

## Bagian 1. Gaya dorong F (Fmax / Fmin)

**Status:** batas throttle ditetapkan (week 2) dan **F sudah terukur dengan timbangan** di 3 titik
(8 %, 10 %, 15 %). Titik 11 % dan seluruh rentang 8–15 % didapat dari interpolasi.

---

### 1. Batas throttle hasil uji slider (week 2)

Uji dengan slider Tes Motor di GUI (firmware `esp32_pid`, ESC sudah dikalibrasi
1000–2000 µs, PWM 50 Hz).

| Besaran | Throttle | Pulsa ESC | Duty (50 Hz) |
|---|---|---|---|
| **Fmin** | 8 % | 1080 µs | 5,40 % |
| **Fmax** | 15 % | 1150 µs | 5,75 % |

Rumus: `pulsa = 1000 + 10 × throttle%` (µs), `duty = pulsa / 20 000`.
Motor hanya boleh bergerak di rentang **8 % – 15 %**.

---

### 2. Rencana penggunaan (BUKAN week 2)

| Minggu | Isi |
|---|---|
| **Week 2 (sekarang)** | Tentukan batas Fmin/Fmax, ukur kurva thrust. **Belum ada PID.** |
| **Week 3** | Titik setimbang (bias) kedua motor = **±11 %**. PID menambah/mengurangi selisih di sekitar 11 %, keluaran dijepit ke **8 % – 15 %**. |

Titik tengah rentang = (8 + 15) / 2 = 11,5 %; dibulatkan **11 %** untuk week 3.
Motor tidak bisa menghasilkan thrust negatif, jadi bias 11 % memberi ruang naik dan turun.
Perlu anti-windup pada integral saat keluaran menyentuh 8 % atau 15 %.

---

### 3. Data pengukuran (timbangan)

Bacaan timbangan = massa ekuivalen dorongan; `F = m × g`, `g = 9,81 m/s²`.

| Throttle (%) | Pulsa (µs) | Massa terbaca (kg) | **F (N)** |
|---|---|---|---|
| 8  | 1080 | 0,070 | **0,687** |
| 10 | 1100 | 0,093 | **0,912** |
| 15 | 1150 | 0,158 | **1,550** |

Hitungan: `0,070 × 9,81 = 0,687`; `0,093 × 9,81 = 0,912`; `0,158 × 9,81 = 1,550` N.

> **Asumsi (perlu dikonfirmasi):** angka di atas adalah bacaan bersih (sudah dikurangi
> bacaan motor mati / ditare) dan merupakan satu motor. Belum dicatat: motor kiri atau
> kanan, dan tegangan power supply saat uji.

---

### 4. Kurva F(throttle) — fit

Data hampir **linear** dalam rentang 8–15 % (di sini rasio `F/u²` tidak konstan:
0,0107; 0,0091; 0,0069, jadi model kuadrat murni dari nol tidak cocok).

Kemiringan antar titik: 8→10 % = 0,113 N/% ; 10→15 % = 0,128 N/%.

Regresi linear (kuadrat terkecil, tiga titik):

```
F(u) = 0,1241 · u − 0,316        [N],  u = throttle (%),  berlaku 8 % ≤ u ≤ 15 %
```

| u (%) | F terukur (N) | F fit (N) | selisih (N) |
|---|---|---|---|
| 8  | 0,687 | 0,677 | +0,010 |
| 10 | 0,912 | 0,925 | −0,013 |
| 15 | 1,550 | 1,546 | +0,004 |

Galat fit ≤ 0,013 N (< 1,5 %). Persamaan ini **hanya untuk 8–15 %**; jangan diekstrapolasi
(mis. ke 0 % atau 100 %, karena sebenarnya ada deadband dan kurvanya melengkung).

#### Nilai yang dipakai

| Parameter | Throttle | F (N) | Keterangan |
|---|---|---|---|
| **Fmin** | 8 %  | **0,69** | terukur |
| **Fbias** | 11 % | **≈ 1,05** | dari fit (interpolasi, belum diukur langsung) |
| **Fmax** | 15 % | **1,55** | terukur |

---

### 5. Dampak ke rig (pitch, pivot di tengah)

Torsi: `τ = L·(F1 − F2)`, `L = 0,25 m`, `J = 0,0140 kg·m²`.

| Kasus | ΔF (N) | τ (N·m) | α = τ/J (rad/s²) |
|---|---|---|---|
| Satu motor 15 %, lainnya 8 % (maksimum) | 0,863 | 0,216 | ≈ 15,4 |
| Dari bias 11 %: satu motor ke 15 %, lainnya ke 8 % | F1 = 1,55, F2 = 0,69 | 0,216 | ≈ 15,4 |
| Dorong-tarik simetris dari bias 11 % (batas bawah, 8 %) | ±0,36 per motor, ΔF = 0,72 | 0,180 | ≈ 12,9 |

Bias 11 % hanya punya ruang turun 3 % (≈ 0,36 N) tetapi naik 4 % (≈ 0,50 N);
untuk perintah simetris PID sebaiknya dijepit ±0,36 N ≈ ±3 % dari bias.

Catatan: `Fmax = 8,0 N` di `Params` (`sim_backend.py`) adalah tebakan untuk 100 %.
Untuk rentang kerja 8–15 % pakai tabel bagian 4. Percepatan 15 rad/s² ≈ 880°/s²
jauh lebih besar daripada gerak yang dibutuhkan; ini memberi margin untuk PID.

---

### 6. Catatan

- F1 dan F2 pasti sedikit berbeda; ukur motor kedua dengan prosedur yang sama dan
  simpan terpisah (pertimbangkan koreksi selisih di week 3).
- F bergantung pada tegangan power supply dan arus; catat dan pertahankan kondisi sama saat PID.
- Titik 11 % masih interpolasi: ukur langsung bila memungkinkan untuk mengunci bias.
- Arah dan posisi saat uji timbangan (aliran udara, ground effect dari meja) bisa menggeser F.

---

## Bagian 2. Redaman poros b

**Metode:** uji ayunan bebas (motor mati, tanpa beban), fit
`θ(t) = off + A·e^(−αt)·cos(ω_d·t + φ)`.
**Data:** `data/2026-11-09_11_uji_awal/hw_20261111_211524` (14,15 s, ~136 Hz, dua gangguan).

---

### 1. Rumus

Dari `J·θ̈ + b·θ̇ + k·θ = 0` → `b = 2·J·α`

dengan `J = 0,0140 kg·m²`, sehingga **`b = 0,0280 × α`**.

> Manual (dua puncak searah): `b = 2·J·ln(A₁/A₂) / Δt`

---

### 2. Hasil

| Event | α (1/s) | R² | b |
|---|---|---|---|
| Dorongan 1 (−4,8°) | 1,3378 | 0,922 | 0,0375 |
| Dorongan 2 (+14,4°) | 1,1335 | 0,969 | 0,0317 |
| **Berbobot (1/σ²)** | — | — | **0,0328 ± 0,0004** |

#### **`b ≈ 0,033 ± 0,002 N·m·s/rad`** (rentang wajar 0,031 – 0,038)

---

### 3. Poin kunci

- **`J` dan `b` tak bisa dipisah** dari satu uji ayunan — hanya `b/J = 2α` yang terukur.
  Jadi `b` proporsional terhadap `J` (pakai `J` hasil hitungan, bukan ukur langsung).
- **Jangan** pakai `b` ini untuk mencari `J` → hasilnya melingkar.
- `b` hanya mencakup **gesekan poros**; redaman aerodinamis saat baling-baling berputar belum termasuk.
- Tebakan lama 0,02 terlalu kecil (~1,7×).
- `DEFAULT_GAINS` dituning dengan `b = 0,02` → **perlu tuning ulang PID**.

---

### 3a. Cek ulang (2026-11-18)

Data `hw_20261111_211524` difit ulang dengan model yang sama, J = 0,0140 kg·m².

| Event | α (1/s) | ω_d (rad/s) | R² | b = 2·J·α |
|---|---|---|---|---|
| Dorongan 2 (+14,4°), jendela 5 s | 1,158 | 1,187 | 0,970 | **0,0324** |
| Dorongan 1 (−4,8°), jendela 5 s | 1,612 | 1,397 | 0,929 | 0,0451 |

- **Rumus `b = 2·J·α` benar** untuk sistem teredam kurang (`θ̈ + (b/J)θ̇ + (k/J)θ = 0`, α = laju peluruhan amplop).
- Dorongan 2 (amplitudo besar, R² 0,970) cocok dengan angka lama (α 1,13 → b 0,032).
- Dorongan 1 (amplitudo kecil, −4,8°) **sensitif ke jendela fit**: α berkisar 1,34–1,61, sehingga b 0,037–0,045. Maka rentang wajar b sebaiknya dilonggarkan: **0,032 – 0,045**; nilai pakai tetap **b ≈ 0,033** (berpatokan pada event 2).
- **Parameter baru dari F tidak mengubah `b`:** `b` berasal dari uji ayunan (motor mati), tidak bergantung pada F atau throttle 8–15 %. J = 0,0140 juga tidak berubah.

**Konstanta pemulih (hasil sampingan).** Dari event 2: `ω_n² = ω_d² + α² = 2,75`, jadi
`k = J·ω_n² ≈ 0,039 N·m/rad`, damping ratio `ζ = α/ω_n ≈ 0,70`.
Bila k berasal dari pusat massa di bawah pivot: `l = k/(m·g) = 0,039/(0,393·9,81) ≈ 10 mm`.
Torsi pemulih pada sudut 33° (batas mekanik) ≈ 0,022 N·m, sekitar **10 %** dari torsi maksimum motor
(0,216 N·m, lihat Bagian 1 di dokumen ini). Kecil tapi tidak nol; asumsi `l = 0` di simulasi
sedikit mengabaikannya.

---

### 4. Langkah lanjut (opsional)

Ukur `J` langsung lewat **bandul bifilar** `J = T²·m·g·d² / (4π²·L)`,
lalu hitung ulang `b = 2·J_ukur·α` dengan `α` yang sama.

---

## Bagian 3. Kekakuan sudut k

**Tanggal:** 23-11-2026. **Skrip:** `analisis/hitung_k.py`.
**Data:** `data/2026-11-23_uji_sudut_motor_mati/` dan `data/2026-11-23_uji_k_pid_tunak/`.

**Hasil: k ≈ −0,05 N·m/rad (rentang pakai −0,03 sampai −0,07). Tanda negatif berarti batang tidak stabil alami.**

---

### 1. Model dan arti k

```
J·θ̈ = L·(F2 − F1) − b·θ̇ − k·θ + c0
```

`k` adalah kekakuan sudut dari gravitasi (pusat massa batang terhadap poros). Konvensi:
θ positif = sisi kanan naik, u > 0 menaikkan motor kanan.

| k | Arti | Pole plant (J = 0,0140, b = 0,033) |
|---|---|---|
| > 0 | Batang kembali ke mendatar, berayun | Pasangan kompleks (bila k > 0,019) |
| < 0 | Batang jatuh menjauhi mendatar | Dua pole **real**, satu positif (tidak stabil) |

Untuk k < 0 tidak ada pole kompleks. Batang tidak berayun tetapi jatuh secara eksponensial.

### 2. Langkah A: tahan batang, motor mati (tanda k)

Batang ditahan di sudut sekitar 5°, 10°, dan 15° tanpa motor, lalu dilepas. Rekaman IMU
(`hw_20261123_1330..1333`, sekitar 6 sampai 8 detik tiap rekaman).

| Rekaman | Sudut awal | Sudut akhir | Perilaku |
|---|---|---|---|
| sudut5 | 4,98° | 8,97° | Bergeser sendiri 5° → 9° dalam 1,2 s, lalu diam |
| sudut5kedua | 5,21° | 5,50° | Diam (std 0,06°) |
| sudut5ketiga | 5,45° | 5,44° | Diam (std 0,016°) |
| sudut5keempat | 5,24° | 6,14° | Loncat 0,9° dalam 0,6 s, lalu diam |
| sudut10 | 10,02° | 10,03° | Diam (std 0,006°) |
| sudut15 | 15,18° | 30,75° | Diam sekitar 2 s, lalu jatuh ke batas mekanik dalam 1,4 s |

Kesimpulan:

- **k negatif.** Di 15° batang jatuh ke batas mekanik, sesuai identifikasi dari data PID.
- **Gesekan poros nyata.** Di 5° dan 10° batang tertahan walau torsi gravitasi tidak nol, dan sudut
  berhentinya berbeda tiap ulangan (5,4 sampai 9,0°). Dari k dan c0 di bawah, torsi dorong di 10°
  sekitar 0,021 N·m masih tertahan, sedangkan di 15° sekitar 0,026 N·m sudah jatuh. Jadi
  gesekan statis poros kira-kira 0,02 N·m, hampir sama besar dengan efek k di rentang 10°.
- Rekaman ini **tidak bisa dipakai menghitung besar k** (motor mati, tidak ada torsi yang terbaca,
  bacaan timbangan tidak dicatat).

### 3. Langkah B: PID tunak (besar k)

#### Prinsip

Batang dengan k < 0 tidak bisa diam sendiri, jadi PID dipakai sebagai **penahan**. Gain yang
dipakai 3 / 2 / 1 (gain yang sudah terbukti stabil), bukan hasil tuning dependen. Saat batang diam
(percepatan dan laju nol), torsi motor sama dengan torsi gravitasi batang:

```
L·(F2 − F1) = k·θ − c0
```

Kemiringan torsi motor terhadap sudut adalah `k`, perpotongannya `−c0`. Torsi dihitung dari throttle
kiri dan kanan yang tercatat (`F = 0,1241·u − 0,316` N, `L = 0,25 m`, F1 = F2 dengan fit yang sama).
Gain PID tidak ikut hitungan, jadi cara ini tidak melingkar dengan tuning.

#### Data

PID aktif sejak detik pertama, setpoint 0°, 5°, 10°, −5°. Seluruh rekaman (8 sampai 10 s) dipakai.

| Rekaman | θ rata-rata | std θ | u rata-rata | Torsi motor |
|---|---|---|---|---|
| k_sp−5 | −4,88° | 0,74° | −6,01 % | −0,0127 N·m |
| k_sp0 | +0,01° | 0,98° | −3,20 % | −0,0067 N·m |
| k_sp5 | +5,08° | 0,89° | −7,91 % | −0,0169 N·m |
| k_sp10 | +10,14° | 0,80° | −10,27 % | −0,0217 N·m |

Makin besar sudut positif, torsi penahan makin negatif, sesuai k < 0.

#### Hasil

| Cara hitung | k (N·m/rad) | c0 (N·m) |
|---|---|---|
| Semua 4 titik (R² 0,58) | −0,043 | +0,0126 |
| Sisi positif saja (0°, 5°, 10°) | −0,055 | – |
| Regresi per detik, 32 titik | −0,046 ± 0,019 (2 SE) | – |

- **Nilai pakai: k = −0,05 N·m/rad.** Rentang uji ketahanan: −0,03 sampai −0,07.
- **c0 = +0,013 N·m**, setara u ≈ −6 % di 0° (trim). Cocok dengan c0 = 0,012 dari identifikasi
  τ dan T_delay (Bagian 4 di dokumen ini), dua metode berbeda.
- R² hanya 0,58 karena titik tidak jatuh rapi di satu garis: torsi di 0° terlalu tinggi sekitar
  0,005 N·m dan titik −5° tidak searah dengan sisi positif. Penyebab utama: gesekan poros
  (bagian 2) yang membuat torsi penahan bergantung arah kedatangan batang. Sisi sudut negatif
  juga diduga lebih tidak stabil (model alat memakai k tambahan −0,04 di sisi itu), jadi nilai
  sisi negatif belum bisa dipercaya.

#### Pole plant dan batas Kp

| k | Pole plant | Waktu 2× lipat | Kp min = \|k\|/L (N/rad, satuan firmware) |
|---|---|---|---|
| −0,03 | +0,70 dan −3,06 | 0,99 s | 0,12 (0,24) |
| **−0,05** | **+1,05 dan −3,41** | **0,66 s** | **0,20 (0,40)** |
| −0,07 | +1,35 dan −3,71 | 0,51 s | 0,28 (0,56) |

### 4. Pembanding

| Sumber | k (N·m/rad) | Kondisi |
|---|---|---|
| Uji ayunan 11-11 | +0,039 | Sebelum ESP32 dan kabel dipasang (pusat massa lebih rendah) |
| Identifikasi data PID 18-11 | −0,054 sampai −0,081 | Fit loop tertutup, ikut menyerap skala thrust |
| **PID tunak 23-11 (ini)** | **−0,05 (±0,02)** | Pengukuran langsung, bergantung F(u) |

Tanda berubah dari +0,039 menjadi negatif karena pusat massa batang naik setelah komponen
dipasang di atas poros.

### 5. Keterbatasan dan cara memperbaiki

- Nilai bergantung pada kalibrasi thrust F(u) (satu motor diukur, F1 = F2 diasumsikan).
- Gesekan poros menyebar hasil. Kurangi dengan merekam tiap sudut dua kali, sekali didekati dari
  bawah dan sekali dari atas, lalu rata-ratakan.
- Perluas rentang sudut ke ±15° (PID masih bisa menahan) supaya sinyal k tiga kali lebih besar
  dari gesekan.
- Cara timbangan (m·g·Ls) tidak dipakai: gesekan poros membuat batang berhenti di sudut yang
  tidak konsisten (bagian 2).

### 6. Cara mengulang

```
# 1. TURN ON (gain 3 / 2 / 1), setpoint 0, tunggu diam ~8 s, Rekam 8-10 s (label k_sp0)
# 2. Ulangi untuk 5, 10, -5 (dan 15, -10 bila mau)
python analisis/hitung_k.py data/2026-11-23_uji_k_pid_tunak/*.csv
```

Satu file per sudut. Skrip memakai `--window` detik terakhir (default 8) dan memberi peringatan
bila batang belum diam, u hampir jenuh, atau throttle menyentuh F-max. Setpoint tidak perlu
diketahui; yang dipakai sudut aktual. Rekaman dengan PID mati dilewati. Skrip divalidasi pada
simulasi dengan parameter sebelum 23-11 (k sebenarnya −0,065, hasil −0,066 untuk titik 0°, 5°, 10°).

---

## Bagian 4. Lag motor τ dan tundaan T_delay

**Tanggal:** 23-11-2026. **Skrip:** `analisis/hitung_tau_delay.py`.
**Data:** `data/2026-11-23_uji_k_pid_tunak/` (rekaman PID, batang ditahan).

**Hasil awal: τ ≈ 0,18 s dan T_delay ≈ 0,08 s. Nilai pakai: τ 0,15 sampai 0,19 s, T_delay 0,06 sampai 0,085 s.**
Perbaiki dengan rekaman step R2.

---

### 1. Arti parameter

Torsi motor tidak muncul seketika setelah perintah throttle. Model:

```
F_i(t) = lag orde-1 (τ) dari F(throttle_i(t − T_delay))
J·θ̈  = L·(F2 − F1) − b·θ̇ − k·θ + c0
```

| Parameter | Isi | Sumber penyusun |
|---|---|---|
| `τ` | Lag motor + baling-baling (putaran naik/turun) | Inersia rotor dan baling-baling, respons ESC |
| `T_delay` | Tundaan murni gabungan | Refresh ESC 50 Hz (rata-rata sekitar 10 ms), pengiriman perintah, filter IMU (DLPF 21 Hz) |

Keduanya membatasi Kp maksimum: makin besar τ + T_delay, makin cepat loop jadi tidak stabil.

### 2. Metode: prediksi jangka pendek

Batang tidak stabil (k < 0), jadi simulasi satu rekaman penuh akan menyimpang dari data. Sebagai gantinya:

1. Rekaman di-resample ke grid 100 Hz.
2. Tiap jendela pendek (0,2 s, geser 0,1 s) dimulai dari sudut dan laju gyro terukur.
3. Jendela diintegrasi memakai model di atas dengan throttle kiri dan kanan yang tercatat sebagai
   masukan (J, b, k, L diketahui).
4. Prediksi sudut dan laju dibandingkan dengan data. `c0` dihitung otomatis (linier).
5. Grid τ (0,02 sampai 0,40 s) × T_delay (0 sampai 0,15 s) dicari yang galatnya terkecil.
   Sebaran dari bootstrap antar jendela.

PID tidak ikut model. Throttle yang tercatat sudah hasil kontrol, jadi gain PID tidak perlu diketahui.

### 3. Validasi pada data simulasi

Simulasi (`app/sim_backend.py` dengan parameter sebelum 23-11: k = −0,065, c0 = 0,024) dengan nilai sebenarnya diketahui. Refresh ESC 50 Hz
pada simulasi menambah sekitar 0,01 s ke T_delay sebenarnya.

| Kondisi data | τ sebenarnya | T_delay efektif | Hasil τ | Hasil T_delay |
|---|---|---|---|---|
| Tanpa noise dan gangguan | 0,15 | 0,05 | 0,16 | 0,040 |
| Noise sensor saja | 0,15 | 0,05 | 0,16 | 0,040 |
| Torsi turbulen saja | 0,15 | 0,05 | 0,18 | 0,060 |
| Noise + turbulen (horizon 0,2 s) | 0,15 | 0,05 | 0,17 | 0,055 |
| Noise + turbulen, nilai lain | 0,08 | 0,03 | 0,09 | 0,045 |

Tiga baris pertama memakai horizon 0,4 s, dua baris terakhir horizon 0,2 s (default skrip sekarang).

Kesimpulan: tanpa gangguan hasilnya hampir tepat. Dengan torsi turbulen, τ dan T_delay terbaca
**0,01 sampai 0,03 s lebih besar** dari sebenarnya, karena kontroler bereaksi terhadap gangguan yang
tidak ada di model (bias identifikasi loop tertutup). Itu sisi aman untuk tuning. Horizon 0,2 s dipilih
karena bias terkecil (horizon 0,4 s sampai 0,5 s bias makin besar). Simpangan baku bootstrap yang
dicetak skrip hanya sebaran antar jendela, bukan bias ini.

### 4. Hasil pada data alat

Rekaman k_sp0, k_sp5, k_sp10, k_sp−5 (PID 3 / 2 / 1, J = 0,0140, b = 0,033). Jumlah jendela 81 sampai 94 per
rekaman. Eksitasi torsi (variasi cepat) 0,008 sampai 0,012 N·m, kecil karena batang hanya ditahan.

| k | τ (s) | T_delay (s) | c0 (N·m) | Galat rms (°-ekuivalen) | Tanpa lag dan delay |
|---|---|---|---|---|---|
| **−0,05 (nominal)** | **0,18 ± 0,02** | **0,080 ± 0,009** | +0,0116 | 0,54 | 0,88 |
| −0,03 | 0,19 ± 0,02 | 0,080 ± 0,010 | +0,0125 | 0,55 | 0,89 |
| −0,07 | 0,16 ± 0,02 | 0,085 ± 0,009 | +0,0107 | 0,57 | 0,91 |

- Hasil **hampir tidak bergantung pada k**: ketidakpastian k (±0,02) tidak mengganggu langkah ini.
- Model dengan lag dan delay menurunkan galat prediksi dari 0,88 ke 0,54 (sekitar 40 %).
- **c0 = 0,012 N·m** cocok dengan c0 dari pengukuran k (0,013 N·m), dua metode berbeda.
- Setelah dikoreksi bias 0,01 sampai 0,03 s (bagian 3): τ sekitar 0,15 sampai 0,18 s dan
  T_delay sekitar 0,05 sampai 0,08 s. Nilai pakai yang disarankan: **τ = 0,15 sampai 0,19 s,
  T_delay = 0,06 sampai 0,085 s**, dengan uji ketahanan di kedua ujung.

### 5. Pembanding

| Sumber | τ (s) | T_delay (s) |
|---|---|---|
| Identifikasi data PID 18-11 (`../kontrol_pid/log_dan_identifikasi.md`, Bagian 2) | 0,10 sampai 0,15 | 0,03 sampai 0,05 |
| **Skrip ini, rekaman k_sp 23-11** | **0,16 sampai 0,19** | **0,080 sampai 0,085** |

Selisih dengan identifikasi lama wajar: data lama memakai gain berbeda, memfit k dan skala thrust
bersamaan, dan bias metode ini sekitar 0,01 sampai 0,03 s.

### 6. Keterbatasan dan langkah lanjut

- **Eksitasi kecil.** Rekaman k_sp adalah batang ditahan, bukan step. Rekam R2:
  PID aktif (3 / 2 / 1), setpoint 0 → 5 → 0 → −5 → 0°, tiap tahap sekitar 8 detik. Perubahan setpoint
  menggerakkan motor lebih kuat dan cepat sehingga τ dan T_delay lebih tajam.
- **Asumsi F1 = F2** dengan F = 0,1241·u − 0,316 N. Skala thrust yang meleset ikut menggeser τ.
- **Gesekan poros dan sisi sudut negatif** tidak ada di model linier.
- Nilai ini dipakai di plant Simulink (transfer function motor 1/(τs + 1) dan Transport Delay).

### 7. Cara mengulang

```
python analisis/hitung_tau_delay.py data/<sesi>/R2_*.csv --k -0.05
```

Opsi: `--b`, `--J` (default 0,033 dan 0,0140), `--horizon` (default 0,2 s), `--no-sweep` (lewati
uji k ±0,02), `--tau-max`, `--td-max`. Skrip memberi peringatan bila eksitasi torsi terlalu kecil atau
hasil menempel di batas grid.
