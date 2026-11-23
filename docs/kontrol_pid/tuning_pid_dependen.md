# Tuning PID Dependen: Serah Terima dan Rencana Kerja

Laptop rig (GUI, ESP32) mengukur parameter dan merekam data. Laptop Simulink membuat model dan
mencari gain. Dokumen ini berisi dua bagian:

| Bagian | Isi | Dibaca oleh |
|---|---|---|
| I | **Paket serah terima**: parameter plant, isian blok, uji ketahanan, pembanding. Cukup untuk mulai | Laptop Simulink (mulai dari sini) |
| II | Rencana kerja detail: urutan pengukuran, format data, pedoman blok dan rumus, langkah tuning, checklist | Kedua laptop |

Rujukan "bagian N" di dalam Bagian I dan Bagian II menunjuk nomor bagian di dalam bagian itu sendiri.

---

## Bagian I. Paket serah terima (ringkas, mulai dari sini)

23 November 2026. Dari laptop rig (GUI, ESP32) ke laptop Simulink.
Rincian dan data ada di berkas rujukan (bagian 9). Halaman ini cukup untuk mulai membuat model dan tuning.

### 1. Plant dan tujuan

Rig twin rotor 1-DOF pitch, dua motor di kiri dan kanan poros. **Plant open-loop tidak stabil**
(k < 0, satu pole real positif), jadi PID wajib untuk menahan batang. Tugas laptop Simulink:
cari **Kp, Ti, Td** (PID dependen) yang stabil di seluruh rentang parameter di bawah dan lebih
baik dari gain rig saat ini (bagian 6).

### 2. Parameter plant

| Parameter | Nominal | Rentang uji | Satuan | Status |
|---|---|---|---|---|
| `L` (poros → motor) | 0,25 | – | m | Terukur |
| `J` (momen inersia) | 0,0140 | – | kg·m² | Hitungan, tetap dipakai |
| `b` (redaman poros) | 0,033 | – | N·m·s/rad | Uji ayunan lama (k masih positif), belum diukur ulang |
| `k` (kekakuan sudut) | **−0,05** | −0,03 … −0,07 | N·m/rad | Terukur 23-11, titik agak menyebar (gesekan poros) |
| `τ` (lag motor + baling-baling) | **0,17** | 0,15 … 0,19 | s | Estimasi awal, perlu rekaman step |
| `T_delay` (ESC, komunikasi, filter IMU) | **0,07** | 0,06 … 0,085 | s | Estimasi awal, perlu rekaman step |
| `F(u)` thrust per motor | 0,1241·u − 0,316 | – | N, u = throttle % | Berlaku 8 sampai 15 %. `F1 = F2` (motor sejenis) |
| Batas sudut mekanik | ±33 | – | ° | Terukur |

### 3. Persamaan dan isian blok

Semua dalam satuan firmware: sudut dalam derajat, keluaran PID `u` dalam persen (±100).

```
J·θ̈ = L·(F2 − F1) − b·θ̇ − k·θ + c0
G(s) = θ/ΔF = L / (J·s² + b·s + k) = 0,25 / (0,014·s² + 0,033·s − 0,05)
```

Pole plant nominal: **+1,05 dan −3,41 rad/s** (real, satu tidak stabil, waktu 2× lipat 0,66 s).

| Blok | Isi |
|---|---|
| Setpoint | Step dalam derajat, rentang ±20°. Firmware **belum punya filter setpoint** |
| PID dependen | `Kp·(1 + 1/(Ti·s) + Td·s)`. Pakai D pada pengukuran (sama dengan firmware, yang memakai laju gyro). Batas ±100, anti-windup clamping |
| Gain u → ΔF | **0,008687** N per % u (F-max 15 %, koreksi ±3,5 %). ΔF = F2 − F1 |
| Motor | `1/(τ·s + 1)` diikuti Transport Delay `T_delay` |
| Plant | `L / (J·s² + b·s + k)`, keluaran θ dalam rad, lalu × 180/π ke derajat |
| Gangguan | Step kecil di ΔF sebelum plant, misalnya 0,08 N (setara torsi 0,02 N·m). Torsi tetap `c0` = 0,013 N·m setara ΔF 0,052 N |

Konversi Kp: `Kp[N/rad] = Kp_fw / 2,009`, dengan `Kp_fw` dalam %/°.

### 4. Uji ketahanan yang diminta

Gain hasil tuning harus stabil dan tidak terlalu berayun di **12 kombinasi ujung**:
`k ∈ {−0,03, −0,05, −0,07}` × `τ ∈ {0,15, 0,19}` × `T_delay ∈ {0,06, 0,085}`.

Hasil perhitungan cepat saya (pole polinomial, Padé orde 3, tanpa saturasi dan tanpa filter D,
perlu dicek ulang di Simulink):

- **Gain rig sekarang (Kp 3 / Ki 2 / Kd 1) stabil di ke-12 kombinasi.** Pole dominan terburuk
  −0,38 rad/s (k = −0,03, τ = 0,19, T_delay = 0,085), artinya lambat mengendap.
- **Kp batas bawah**: Kp > |k|/L = 0,2 N/rad, atau sekitar 0,4 di firmware. Dengan lag, batas bawah
  praktis sekitar 0,45 (nominal) sampai 0,60 (terburuk) di firmware.
- **Kp batas atas** (PD, Td = 0,33 s): sekitar 4,5 di firmware untuk nominal dan 3,75 untuk sudut
  terburuk (τ = 0,19, T_delay = 0,085, k = −0,07). Jadi gain rig (Kp 3) sudah cukup dekat ke batas
  atas di sudut terburuk. Suku D memperlebar batas ini, tetapi sensor ber-noise membatasinya.

### 5. Kriteria

- θ akhir sama dengan setpoint (offset hilang, jadi Ki > 0).
- Overshoot dan waktu tenang lebih baik dari pembanding (bagian 6).
- `u` tidak menempel di ±100 terlalu lama.
- Stabil di 12 kombinasi ujung (bagian 4).

### 6. Pembanding: gain rig saat ini

| Bentuk | Nilai |
|---|---|
| Firmware / GUI (paralel) | Kp 3,0 %/° · Ki 2,0 %/(°·s) · Kd 1,0 %/(°/s) |
| Dependen | Kp ≈ 1,49 N/rad · Ti = 1,5 s · Td = 0,33 s |

Hasil di rig (uji ke-7, 18-11-2026):

| Setpoint | Rata-rata akhir | Std | Lewat setpoint | Tenang ±1,5° |
|---|---|---|---|---|
| 0° | +0,3° | 0,55° | 1,3° | – |
| +10° | +9,6° | 0,40° | 4,9° | 2,3 s |
| −10° | −10,2° | 0,76° | 9,3° | ~3 s |
| +20° | +20,2° | 0,51° | 10,8° | 3,7 s |

Sisa masalah: overshoot besar di sisi negatif dan pada step besar. Simulasi di GUI
(`app/sim_backend.py`, sudah memakai parameter di atas) memberi lewat setpoint 4,0° (+10°) dan 8,2° (−10°),
cukup dekat sebagai pembanding.

### 7. Batas yang perlu diingat saat memilih gain

| Hal | Batas |
|---|---|
| Slider GUI | Kp 0 sampai 5, Ki 0 sampai 3, Kd 0 sampai 1,5 (satuan firmware) |
| Konversi ke firmware | `Ki = Kp_fw / Ti`, `Kd = Kp_fw · Td`. **GUI sudah menghitung ini otomatis**: isi Kp, Ti, Td dan Ki, Kd mengikuti |
| Jadi | `Kp_fw/Ti ≤ 3` dan `Kp_fw·Td ≤ 1,5` (contoh: Kp_fw 4,02 dan Td 0,4 memberi Kd 1,61, melebihi batas) |
| Integral firmware | Penuh bila \|e\| < 6°, diperlambat 50 % di luar zona, berhenti saat u jenuh |
| Lain-lain | Loop 500 Hz, ESC hanya membaca 50 Hz, laju throttle dibatasi 40 %/s per motor |

### 8. Yang tidak ada di model dan yang belum pasti

- **Gesekan statis poros** sekitar 0,02 N·m (sebesar torsi gravitasi di rentang 10°). Respons rig
  akan sedikit berbeda dari simulasi linier, misalnya berhenti di sudut yang meleset.
- **Sisi sudut negatif** lebih tidak stabil (k efektif sekitar −0,09 menurut data lama). Nilainya belum terukur andal.
  Nilai k di atas berlaku untuk sisi positif dan sekitar nol.
- **Torsi tetap `c0` = 0,013 N·m** tidak ada di plant dan cukup diserap integrator (setara trim u ≈ −6 % di 0°).
- **`b`** belum diukur ulang untuk k < 0. Pengaruhnya kecil ke hasil tuning.
- **`τ` dan `T_delay`** masih estimasi dari rekaman batang ditahan. Skrip cenderung membacanya
  0,01 sampai 0,03 s terlalu besar (sisi aman). Rekaman step akan memperbaikinya.
- **Thrust motor kiri dan kanan** diasumsikan sama.

### 9. Berkas rujukan

| Berkas | Isi |
|---|---|
| `docs/pengukuran/ringkasan_pengukuran.md` | Ringkasan semua pengukuran proyek |
| `docs/pengukuran/detail_pengukuran.md` | Pengukuran k (Bagian 3) dan τ, T_delay (Bagian 4): metode, data, ketidakpastian |
| Dokumen ini, Bagian II | Pedoman blok Simulink dan langkah tuning |
| `data/2026-11-23_uji_k_pid_tunak/`, `data/2026-11-23_uji_sudut_motor_mati/` | Rekaman CSV (tidak ikut git, kirim manual) |

### 10. Yang diminta kembali

1. **Kp, Ti, Td** (satuan fisik N/rad dan s) beserta konversinya ke **Kp, Ki, Kd firmware**.
2. Jalur tuning yang dipakai dan alasannya, plus filter setpoint bila dipakai (konstanta waktunya).
3. Plot step setpoint dan step gangguan di nominal dan di kombinasi ujung terburuk.
4. Catatan kombinasi parameter mana yang paling sensitif.

Setelah gain masuk, laptop rig merekam step (0 → 5 → 0 → −5 → 0°) dan gangguan, lalu mengirim CSV
untuk memperbaiki τ dan T_delay.

---

## Bagian II. Rencana kerja dan pedoman detail

23 November 2026 (disesuaikan dengan kondisi rig dan GUI saat ini)

### 0. Kondisi saat ini

| Hal | Kondisi |
| --- | --- |
| Gain terbaik di rig | Kp 3 / Ki 2 / Kd 1 (uji ke-7, 18-11-2026), bentuk paralel di firmware. Setara Kp ≈ 1,49 N/rad, Ti = 1,5 s, Td = 0,33 s |
| Hasil gain itu | Di 0°: std 0,55°. Step +10°: rata 9,6°, lewat 4,9°, tenang 2,3 s. Step −10°: lewat 9,3°, tenang ~3 s. Sisa masalah: overshoot sisi negatif dan step besar |
| Plant | Tidak stabil alami, k = −0,054 sampai −0,081 N·m/rad (dari data PID). Uji motor mati terakhir (11-11) memberi k = +0,039, sebelum ESP32 dan kabel dipasang, jadi uji 5 dan 6 perlu diulang |
| Motor | Kiri = CW (IO26, ESC 1, propeller 1045R), kanan = CCW (IO25, ESC 2) |
| Rentang kerja | Throttle 8 sampai 15 % (F-max 15 %), bias 11,5 %, koreksi ±3,5 % |
| Torsi tetap | Perlu trim u ≈ −10 sampai −13 % agar diam di 0° (tombol Trim di GUI) |
| Batas mati sudut | Di GUI sekarang default MATI. Nyalakan sebelum uji berisiko (slider 29 sampai 33°) |
| Filter setpoint | Belum ada di firmware `esp32_pid`: setpoint langsung step |

### 1. Pembagian tugas

Laptop ini memegang rig: GUI, viewer Processing, firmware ESP32, pengukuran, dan logging. Tugasnya melengkapi data pengukuran hardware sebagai syarat tuning PID dependen, lalu memasukkan gain hasil tuning ke GUI dan hardware. Laptop teman memegang Simulink: model plant, simulasi, tuning PID dependen, dan identifikasi dengan SIT. Data dan gain bolak-balik di antara keduanya sampai rig stabil dan model cocok dengan data.

| Laptop | Yang dikerjakan | Yang diserahkan ke laptop lain |
| --- | --- | --- |
| Laptop ini (rig, GUI) | Firmware ESP32, pengukuran syarat tuning, logging CSV, mencoba gain di rig lewat GUI | Parameter terukur (tanda k, besar k, b, τ, T_delay) dan file CSV |
| Laptop teman (Simulink) | Model plant, simulasi closed-loop, tuning PID dependen, identifikasi SIT | Gain Kp, Ti, Td dalam satuan fisik dan satuan firmware |

Bentuk PID yang dipakai di kedua laptop sama, yaitu PID dependen:

$$
G_c(s) = K_p\left(1 + \frac{1}{T_i s} + T_d s\right)
$$

### 2. Bagian A: pengukuran di hardware (laptop ini)

Kerjakan berurutan. Uji 1 sampai 4 adalah syarat keamanan sebelum PID dinyalakan. Uji 5 sampai 8 menentukan jalur tuning dan angka model.

Daftar kerja laptop ini, dikerjakan lewat GUI (mode Hardware) dan ESP32:

| Uji | Status | Yang masih dikerjakan | Alat bantu di GUI |
| --- | --- | --- | --- |
| 1 sampai 4 | Terpenuhi | Catat offset IMU saat batang mendatar | Pembacaan sudut, tombol Kalibrasi gyro dan Nol-kan (0°) |
| 5 | Belum | Uji lepas batang motor mati, tentukan tanda k | Rekam (CSV) dan pembacaan sudut |
| 6 | Belum (perlu kalau k ≠ 0) | Ukur k lewat PID tunak di 0°, 5°, 10° (gain 3 / 2 / 1 hanya sebagai penahan), lalu `python analisis/hitung_k.py` | TURN ON, Rekam (CSV) |
| 7 | Belum (perlu kalau k ≠ 0) | Rekam R1 gerak bebas untuk fit b dan k | Rekam (CSV), motor mati |
| 8 | Dilewati | Tidak diukur: kedua motor sejenis, jadi F1 = F2 dengan F = 0,1241·u − 0,316 N | – |
| 9 | Estimasi awal ada | τ dan T_delay dihitung dengan `python analisis/hitung_tau_delay.py` dari rekaman PID. Rekam R2 (step) untuk memperbaiki, lalu R3 dan R4 setelah gain dari laptop teman masuk | Rekam (CSV), TURN ON |

Status: uji 1 sampai 4 sudah terpenuhi, dibuktikan 7 uji PID di rig (18-11-2026, sudut + = sisi kanan naik). Uji 5 sampai 8 belum dikerjakan ulang, dan sementara b memakai nilai lama.

#### A1. Keamanan dan tanda (throttle rendah, batang ditahan)

1. **Uji PWM ke ESC.** Lakukan arming, naikkan throttle perlahan, lalu pastikan motor berhenti saat perintah 0. Catat lebar pulsa saat arming dan saat motor mulai berputar.
2. **Pemetaan motor.** ESC 1 di sisi kiri (CW, IO26, propeller 1045R) dan ESC 2 di sisi kanan (CCW, IO25, propeller 1045), sesuai slide. Posisi propeller sudah dicek dan benar.
3. **Uji tanda.** Naikkan sedikit motor kanan. Sisi kanan harus naik dan IMU harus membaca θ positif. Kalau terbalik, tukar tandanya di firmware, bukan di persamaan.
4. **Cek IMU.** Saat batang mendatar, bacaan harus 0° (catat offset-nya). Laju gyro harus positif saat θ bertambah, karena suku D diambil dari gyro.

#### A2. Parameter model (motor mati, kecuali uji 8)

5. **Uji k.** Lepas batang dari sudut kecil (sekitar 10°) tanpa motor menyala, lalu amati.

| Yang terlihat | Tanda k | Jalur tuning |
| --- | --- | --- |
| Berayun lalu kembali ke mendatar | k > 0 | B (empiris), plant stabil |
| Diam di sudut tempat dilepas | k ≈ 0 | A (analitik, lambda) |
| Terus jatuh sampai mentok | k < 0 | B (empiris), plant tak stabil |

Dugaan saat ini: k < 0 (batang diam di batas mekanis ±31 sampai 33° saat motor mati), jadi jalur B. Konfirmasi dengan uji ini setelah ESP32 dan kabel terpasang.

6. **Besar k** (lewati kalau k ≈ 0). Batang tidak bisa diam sendiri kalau k < 0 (di 15° batang jatuh ke batas mekanik), jadi batang ditahan oleh PID dan yang dibaca adalah torsi motor saat batang sudah diam. PID hanya penahan, jadi pakai gain yang sudah terbukti stabil (3 / 2 / 1). Gain ini bukan hasil tuning dependen. Saat batang diam, percepatan dan laju sudut nol, sehingga torsi motor sama dengan torsi gravitasi batang:

$$
L\,(F_2 - F_1) = k\,\theta - c_0
$$

   Langkahnya:

   1. Hidupkan PID (TURN ON), setpoint 0°. Tunggu sampai diam (sekitar 8 detik), lalu Rekam 8 sampai 10 detik. Beri label, misalnya `k_sp0`.
   2. Ulangi untuk setpoint 5° dan 10°. Kalau mau, tambah −5°. Satu file per sudut, tiap kali tunggu sampai diam dulu.
   3. Jalankan: `python analisis/hitung_k.py data/k_sp0.csv data/k_sp5.csv data/k_sp10.csv`

   Skrip mengambil 8 detik terakhir tiap rekaman (batang bergoyang sekitar 1°, jadi perlu rata-rata panjang), menghitung torsi dari throttle kiri dan kanan (F = 0,1241·u − 0,316 N, L = 0,25 m), lalu mencocokkan garis torsi terhadap sudut. Kemiringannya adalah k, dan perpotongannya adalah c0. Yang dipakai adalah sudut aktual, bukan setpoint. Skrip memberi peringatan kalau batang belum diam, u hampir jenuh, atau throttle menyentuh F-max.

   Catatan: k di sisi sudut negatif lebih besar (lebih tidak stabil) daripada di sisi positif, jadi laporkan sisi yang diukur bersama nilainya. Skrip menampilkan k sisi + dan sisi − terpisah kalau titiknya cukup. Cara dengan timbangan (m·g·Ls) tidak dipakai karena gesekan poros membuat batang berhenti di sudut yang tidak konsisten.

7. **Redaman b.** Kalau k ≈ 0, b lama (0,033 N·m·s/rad) masih bisa dipakai. Kalau k ≠ 0, rekam CSV gerak bebas batang dari sudut kecil dengan motor mati, lalu kirim ke laptop teman untuk di-fit ulang dengan k dimasukkan.
8. **Thrust motor kedua.** Dilewati. Kedua motor sejenis (A2212 2200 KV, ESC dan propeller sama), jadi dipakai F1 = F2 = 0,1241·u − 0,316 N. Selisih kecil antara motor kiri dan kanan (motor kiri sekitar 1 % throttle lebih tinggi) sudah terserap oleh trim, jadi tidak memengaruhi model plant.

$$
F = \text{bacaan (g)} \times 0{,}00981 \times \frac{L_s}{L}
$$

#### A3. Menyusul setelah PID stabil

9. **Lag motor τ dan tundaan T_delay.** PID sudah stabil, jadi rekam respons step kecil (format di bagian 3), lalu hitung dengan `python analisis/hitung_tau_delay.py data/R2_*.csv --k -0.05` (atau fit di SIT). Skrip mencocokkan model ke data lewat prediksi jangka pendek (jendela 0,2 s) dengan J, b, k diketahui, dan mencetak hasilnya untuk k nominal dan k ±0,02. Estimasi awal dari rekaman k_sp (batang ditahan, eksitasi kecil): τ ≈ 0,18 s dan T_delay ≈ 0,08 s, hampir tidak berubah untuk k −0,03 sampai −0,07. Skrip cenderung membaca 0,01 sampai 0,03 s terlalu besar (sisi aman). T_delay mencakup refresh ESC 50 Hz, komunikasi, dan filter IMU. Perbaiki dengan rekaman step R2. Perkiraan dari fit loop tertutup data 18-11 (`log_dan_identifikasi.md`, Bagian 2): τ = 0,10 sampai 0,15 s dan T_delay = 0,03 sampai 0,05 s.

#### Lembar catat hasil ukur

| Besaran | Nilai | Satuan | Catatan |
| --- | --- | --- | --- |
| Lebar pulsa arming |  | µs |  |
| Lebar pulsa motor mulai berputar |  | µs |  |
| Offset IMU saat mendatar |  | ° |  |
| Tanda F1/F2 | benar |  | u > 0 menaikkan motor kanan, sudut + = kanan naik |
| Tanda k | < 0 (dugaan) |  | dari identifikasi data PID, uji motor mati belum diulang |
| \|k\| |  | N·m/rad | sudut θ1, θ2 dan bacaan m1, m2 |
| b |  | N·m·s/rad | lama atau di-fit ulang |

### 3. Format data log (dikirim ke laptop teman)

Satu rekaman = satu file CSV. Rekam dari GUI (tombol Rekam di panel Sumber data, mode Hardware). ESP32 mengirim data 100 Hz (setiap 10 ms), dan GUI menyimpan satu baris per paket. Untuk SIT, input-nya `u` dan output-nya `sudut_deg`.

Format CSV GUI saat ini:

```csv
# label,R2_step_Kp3_Ki2_Kd1
# port,COM7,baud,115200
# dimulai,2026-11-23 10:15:00
t_s,sudut_esp_f2_deg,dibalik,offset_deg,sudut_deg,beban_g,posisi_beban_cm,baris_mentah
0.0100,3.21,0,3.200,0.010,0,0.0,"*,0.00,3.21,0.40,-0.010,0.020,0.990,30.1,497,1,1.8,11.55,11.45,5.40,0.00,-3.60,#"
```

Isi kolom `baris_mentah` (urutan field setelah tanda `*`): sudut lain, sudut, laju gyro (°/s), ax, ay, az, suhu, loop Hz, pid_on, u (%), throttle kiri (%), throttle kanan (%), suku P, I, D.

Yang perlu diperhatikan untuk SIT:

- Kolom setpoint **tidak ada** di CSV. Catat jadwal step (waktu dan nilainya) di label atau nama file.
- Throttle motor tercatat dalam persen (kiri dan kanan), bukan lebar pulsa µs. Pulsa dihitung dengan `1000 + 10 × throttle%`.
- Setpoint di GUI dibatasi ±20°.

Nama file atau label sebaiknya menyebut jenis rekaman dan gain-nya, misalnya `R2_step_Kp3_Ki2_Kd1`.

| Kode | Rekaman | Kondisi | Dipakai untuk |
| --- | --- | --- | --- |
| R1 | Gerak bebas | Motor mati, batang dilepas dari sudut kecil | Fit b dan k |
| R2 | Step setpoint | PID stabil, setpoint 0 → 5 → 0 → −5 → 0°, tiap tahap 5 sampai 8 s (uji ke-7 memakai ±10° dan ±20°, tiap 8 s) | Estimasi τ, T_delay, dan model SIT |
| R3 | Validasi | Sama seperti R2 tetapi pola atau besar step berbeda | Mengecek model SIT (jangan dipakai untuk fit) |
| R4 | Gangguan | PID stabil, batang didorong sedikit atau diberi beban kecil di satu sisi | Menguji ketahanan gain |

### 4. Bagian B: Simulink (laptop teman)

Model Simulink dibuat dalam satuan firmware (derajat dan u_pid ±100). Gain hasil tuning dikonversi ke bentuk paralel yang dipakai firmware (Kp, Ki, Kd) sebelum dimasukkan ke GUI. Rumusnya ada di bagian "Konversi ke gain firmware".

#### Rangkaian blok

1. **Step** sebagai setpoint dalam derajat, diikuti **filter setpoint** berupa Transfer Fcn 1/(0,4s + 1). Firmware `esp32_pid` belum punya filter ini, jadi untuk membandingkan dengan rig, hilangkan filter (atau tambahkan filter yang sama di firmware).
2. **PID Controller (2DOF)** dengan Form = Ideal. Atur setpoint weight b = 1 dan c = 0, supaya D diambil dari pengukuran (tipe B, sama seperti firmware yang memakai laju gyro). Batas output ±100 dengan anti-windup clamping. Firmware juga memperlambat integral 50 % saat |e| ≥ 6° (I-zone) dan menghentikannya saat keluaran jenuh.
3. **Gain 0,008687** untuk mengubah u_pid menjadi ΔF (N).
4. **Transfer Fcn motor** 1/(τs + 1), diikuti **Transport Delay** sebesar T_delay.
5. **Sum gangguan**: tambahkan step kecil, misalnya 0,08 N, untuk uji gangguan.
6. **Transfer Fcn plant** dengan numerator [L] dan denominator [J b k]. Output-nya θ dalam rad.
7. **Gain 180/π** untuk mengubah θ ke derajat. Hasilnya diumpankan balik ke PID dan ditampilkan di Scope bersama u_pid.

#### Parameter yang diisi

| Parameter | Nilai sementara | Satuan | Status |
| --- | --- | --- | --- |
| J | 0,0140 | kg·m² | Hitungan manual, tetap dipakai (tidak diukur ulang) |
| L | 0,25 | m | Terukur |
| b | 0,033 | N·m·s/rad | Dari uji ayunan 11-11 (motor mati). Ganti dengan hasil uji 7 |
| k | −0,054 sampai −0,081 | N·m/rad | Identifikasi data PID 18-11. Ganti dengan hasil uji 5 dan 6 |
| τ | 0,10 sampai 0,15 | s | Fit data PID 18-11, diperbaiki setelah SIT |
| T_delay | 0,03 sampai 0,05 | s | Fit data PID 18-11, diperbaiki setelah SIT |
| Gain u_pid ke ΔF | 0,008687 | N per satuan u_pid | Dari fit thrust motor 1 (F1 = F2 diasumsikan), berlaku untuk F-max 15 % (koreksi ±3,5 %). Kalau F-max diubah, hitung ulang: 2 × 0,1241 × (F-max − 8)/2 / 100 |

#### Isian blok PID (bentuk Ideal = dependen)

| Kolom di blok | Diisi | Contoh |
| --- | --- | --- |
| P | Kp dalam satuan firmware | 4,02 |
| I | 1/Ti (bukan Ti) | Ti = 3 s → 0,333 |
| D | Td | 0,4 |
| N | Koefisien filter D | 20 sampai 50 |

Konversi Kp dari satuan fisik ke satuan firmware:

$$
K_{p,fw} = K_p \times \frac{\pi/180}{0{,}008687} \approx 2{,}009 \, K_p
$$

#### Konversi ke gain firmware (Kp, Ki, Kd)

Firmware dan GUI memakai bentuk paralel: u = Kp·e + Ki·∫e + Kd·(−laju gyro), dengan Kp dalam %/°, Ki dalam %/(°·s), dan Kd dalam %/(°/s). Dari PID dependen:

$$
K_i = \frac{K_{p,fw}}{T_i} \qquad\qquad K_d = K_{p,fw} \, T_d
$$

| Sumber | Kp (fw) | Ti (s) | Td (s) | Ki (fw) | Kd (fw) |
| --- | --- | --- | --- | --- | --- |
| Gain terbaik di rig (uji ke-7) | 3,0 | 1,5 | 0,33 | 2,0 | 1,0 |
| Titik awal Simulink (bagian "Langkah tuning") | 4,02 | 3 | 0,4 | 1,34 | 1,61 |

Batas slider di GUI: Kp 0 sampai 5, Ki 0 sampai 3, Kd 0 sampai 1,5. Titik awal Simulink memberi Kd 1,61, di atas batas slider. Pakai Td ≤ 0,37 s atau naikkan batas slider Kd.

#### Rumus pegangan (lag motor diabaikan, Kp dalam N/rad)

Persamaan karakteristik closed-loop dengan PID dependen:

$$
J s^3 + (b + K_p L T_d)\, s^2 + (k + K_p L)\, s + \frac{K_p L}{T_i} = 0
$$

Batas bawah Kp (berlaku kalau k < 0) dan batas bawah Ti (dari kriteria Routh):

$$
K_p > \frac{|k|}{L} \qquad\qquad T_i > \frac{J \, K_p L}{(b + K_p L T_d)(k + K_p L)}
$$

Batas atas Kp datang dari lag dan tundaan motor. Untuk P saja nilainya sekitar 0,75 sampai 1,16 N/rad. Suku D memperlebar batas ini.

#### Langkah tuning

**Jalur A (k ≈ 0), lambda tuning:**

$$
T_d = \frac{J}{b} \approx 0{,}42 \text{ s} \qquad K_p = \frac{b}{L\,\lambda} \qquad \lambda \approx 0{,}5 \text{ sampai } 1 \text{ s} \qquad T_i \approx 3 \text{ s}
$$

**Jalur B (k < 0 atau k > 0), empiris.** Ubah satu parameter dalam satu waktu.

1. Mulai dari PD (Ti = ∞, atau I = 0 di blok) dengan Kp sekitar 3 sampai 4 kali Kp minimum (sekitar 1,0 N/rad, atau 2,0 di firmware) dan Td = 0,4 s.
2. Atur Td: naikkan kalau masih berayun lambat, turunkan kalau mulai bergetar cepat.
3. Tambah I mulai dari Ti = 3 s, lalu perkecil pelan-pelan sampai offset hilang tanpa overshoot berlebih.
4. Naikkan Kp bertahap untuk kecepatan, berhenti sebelum muncul getaran.
5. Uji gangguan 0,08 N dan cek simpangannya.

Titik awal dari simulasi sebelumnya: Kp = 2,0 N/rad (4,02 di firmware), Ti = 3 s, Td = 0,4 s, filter setpoint 0,4 s. Hasilnya overshoot 18 sampai 24% dan settling sekitar 7,6 s.

Pembanding di rig saat ini: Kp 3 / Ki 2 / Kd 1 di firmware (Kp ≈ 1,49 N/rad, Ti = 1,5 s, Td = 0,33 s) tanpa filter setpoint. Hasil tuning Simulink dianggap berhasil kalau lebih baik dari ini, yaitu overshoot lebih kecil, terutama di sisi negatif dan step besar, dengan waktu tenang tetap sekitar 2 sampai 3 s.

#### Yang dicek di Scope

- θ akhir sama dengan setpoint (offset hilang).
- Overshoot dan waktu settling.
- u_pid tidak menempel di ±100 terlalu lama.
- Hasil tetap stabil di semua kombinasi k, τ, T_delay ujung bawah dan ujung atas.

### 5. Membawa gain ke rig (laptop ini)

Gain dari Simulink (Kp, Ti, Td) langsung dimasukkan ke kartu Kontrol PID di GUI, karena Ki = Kp/Ti dan Kd = Kp·Td dihitung otomatis (bagian "Konversi ke gain firmware" menjelaskan rumusnya) (buka gembok KUNCI dulu). Jangan mulai dengan Kp yang lebih kecil dari hasil simulasi: kalau k < 0, Kp terlalu kecil justru membuat batang jatuh.

#### Pengaman yang harus aktif sebelum uji

Status di firmware `esp32_pid` dan GUI saat ini:

- [x] D diambil dari gyro (tipe B): u = trim + Kp·e + I − Kd·laju gyro
- [x] Saturasi u_pid ±100 dan anti-windup (I berhenti bertambah saat output jenuh, diperlambat 50 % saat |e| ≥ 6°)
- [ ] Filter setpoint: belum ada (setpoint langsung step)
- [x] Batas sudut: motor mati kalau |θ| melebihi batas mati (slider 29 sampai 33°). Default GUI sekarang MATI, jadi aktifkan lagi sebelum uji berisiko. PID hanya mau mulai kalau |θ| ≤ 30° saat batas mati aktif
- [x] Failsafe: motor 0 kalau tidak ada perintah GUI > 0,5 s atau data IMU putus > 50 ms
- [x] Soft-start 0 → 8 % dalam 1 s, tahan 0,7 s, lalu PID. Laju throttle dibatasi 40 %/s per motor
- [ ] Tombol E-stop fisik: belum ada. Yang tersedia: TURN OFF di GUI, STOP MOTOR, dan failsafe di atas

#### Urutan uji di rig

1. Connect ke ESP32, tahan batang dekat 0°, lalu tekan TURN ON. Firmware menaikkan throttle sendiri (soft-start sampai bias 11,5 %), jadi tidak perlu dinaikkan manual. Lepas batang setelah PID aktif.
2. Kalau sudah tenang di 0°, tekan Trim di GUI (nilai I sekarang) supaya torsi tetap terkompensasi, lalu beri step kecil 3 sampai 5° dari kotak Setpoint dan rekam sebagai R2.
3. Rekam R3 (validasi) dengan pola step yang berbeda, lalu R4 (gangguan).
4. Kirim semua CSV ke laptop teman. Awasi suhu motor dan ESC di setiap sesi.

#### Gejala dan obat

| Gejala | Yang diubah |
| --- | --- |
| Batang jatuh | Kp terlalu kecil, atau tanda F1/F2 atau IMU terbalik |
| Getar cepat | Td atau Kp terlalu besar |
| Ayunan lambat | Td terlalu kecil |
| Offset tidak hilang | Ti terlalu besar, atau I belum aktif. Di rig juga cek Trim, dan ingat integral diperlambat 50 % saat |e| ≥ 6° |
| Overshoot besar setelah step | Ti terlalu kecil, atau filter setpoint diperlambat |
| Hasil rig jauh beda dari Simulink | Model belum cocok: perbarui k, b, τ, T_delay lewat SIT |

### 6. Checklist serah terima

**Laptop ini → laptop teman (putaran 1)**

- [ ] Hasil uji 1 sampai 4 (semua aman, tanda sudah benar)
- [ ] Tanda k dari uji 5
- [ ] Nilai |k| beserta θ1, θ2, m1, m2 dan Ls dari uji 6
- [ ] b lama dipakai, atau file R1 untuk fit ulang

**Laptop teman → laptop ini**

- [ ] Jalur tuning yang dipakai (A atau B)
- [ ] Kp, Ti, Td, dan hasil konversinya ke Kp, Ki, Kd firmware, beserta konstanta waktu filter setpoint (kalau dipakai, firmware perlu ditambah)
- [ ] Plot Simulink step dan gangguan sebagai pembanding

**Laptop ini → laptop teman (putaran 2)**

- [ ] File R2, R3, R4 beserta gain yang dipakai saat merekam
- [ ] Catatan gejala yang terlihat di rig

**Laptop ini (penutup)**

- [ ] Masukkan gain akhir ke GUI, uji di rig, dan catat hasilnya di `log_dan_identifikasi.md`
- [ ] Perbarui `ringkasan_pengukuran.md` dengan k, b, τ, dan T_delay yang baru

**Laptop teman (penutup)**

- [ ] Identifikasi SIT dari R2, validasi dengan R3
- [ ] Perbarui τ, T_delay, dan model di Simulink, lalu sempurnakan gain
- [ ] Perbarui model dan slide
