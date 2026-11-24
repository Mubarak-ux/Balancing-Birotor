# Ringkasan Tuning PID Dependen: Rig Balancing Birotor

23 November 2026 (disesuaikan dengan kondisi rig dan GUI saat ini)

## 0. Kondisi saat ini

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

## 1. Pembagian tugas

Laptop ini memegang rig: GUI, viewer Processing, firmware ESP32, pengukuran, dan logging. Tugasnya melengkapi data pengukuran hardware sebagai syarat tuning PID dependen, lalu memasukkan gain hasil tuning ke GUI dan hardware. Laptop teman memegang Simulink: model plant, simulasi, tuning PID dependen, dan identifikasi dengan SIT. Data dan gain bolak-balik di antara keduanya sampai rig stabil dan model cocok dengan data.

| Laptop | Yang dikerjakan | Yang diserahkan ke laptop lain |
| --- | --- | --- |
| Laptop ini (rig, GUI) | Firmware ESP32, pengukuran syarat tuning, logging CSV, mencoba gain di rig lewat GUI | Parameter terukur (tanda k, besar k, b, τ, T_delay) dan file CSV |
| Laptop teman (Simulink) | Model plant, simulasi closed-loop, tuning PID dependen, identifikasi SIT | Gain Kp, Ti, Td dalam satuan fisik dan satuan firmware |

Bentuk PID yang dipakai di kedua laptop sama, yaitu PID dependen:

$$
G_c(s) = K_p\left(1 + \frac{1}{T_i s} + T_d s\right)
$$

## 2. Bagian A: pengukuran di hardware (laptop ini)

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

### A1. Keamanan dan tanda (throttle rendah, batang ditahan)

1. **Uji PWM ke ESC.** Lakukan arming, naikkan throttle perlahan, lalu pastikan motor berhenti saat perintah 0. Catat lebar pulsa saat arming dan saat motor mulai berputar.
2. **Pemetaan motor.** ESC 1 di sisi kiri (CW, IO26, propeller 1045R) dan ESC 2 di sisi kanan (CCW, IO25, propeller 1045), sesuai slide. Posisi propeller sudah dicek dan benar.
3. **Uji tanda.** Naikkan sedikit motor kanan. Sisi kanan harus naik dan IMU harus membaca θ positif. Kalau terbalik, tukar tandanya di firmware, bukan di persamaan.
4. **Cek IMU.** Saat batang mendatar, bacaan harus 0° (catat offset-nya). Laju gyro harus positif saat θ bertambah, karena suku D diambil dari gyro.

### A2. Parameter model (motor mati, kecuali uji 8)

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

### A3. Menyusul setelah PID stabil

9. **Lag motor τ dan tundaan T_delay.** PID sudah stabil, jadi rekam respons step kecil (format di bagian 3), lalu hitung dengan `python analisis/hitung_tau_delay.py data/R2_*.csv --k -0.05` (atau fit di SIT). Skrip mencocokkan model ke data lewat prediksi jangka pendek (jendela 0,2 s) dengan J, b, k diketahui, dan mencetak hasilnya untuk k nominal dan k ±0,02. Estimasi awal dari rekaman k_sp (batang ditahan, eksitasi kecil): τ ≈ 0,18 s dan T_delay ≈ 0,08 s, hampir tidak berubah untuk k −0,03 sampai −0,07. Skrip cenderung membaca 0,01 sampai 0,03 s terlalu besar (sisi aman). T_delay mencakup refresh ESC 50 Hz, komunikasi, dan filter IMU. Perbaiki dengan rekaman step R2. Perkiraan dari fit loop tertutup data 18-11 (`identifikasi_model.md`): τ = 0,10 sampai 0,15 s dan T_delay = 0,03 sampai 0,05 s.

### Lembar catat hasil ukur

| Besaran | Nilai | Satuan | Catatan |
| --- | --- | --- | --- |
| Lebar pulsa arming |  | µs |  |
| Lebar pulsa motor mulai berputar |  | µs |  |
| Offset IMU saat mendatar |  | ° |  |
| Tanda F1/F2 | benar |  | u > 0 menaikkan motor kanan, sudut + = kanan naik |
| Tanda k | < 0 (dugaan) |  | dari identifikasi data PID, uji motor mati belum diulang |
| \|k\| |  | N·m/rad | sudut θ1, θ2 dan bacaan m1, m2 |
| b |  | N·m·s/rad | lama atau di-fit ulang |

## 3. Format data log (dikirim ke laptop teman)

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

## 4. Bagian B: Simulink (laptop teman)

Model Simulink dibuat dalam satuan firmware (derajat dan u_pid ±100). Gain hasil tuning dikonversi ke bentuk paralel yang dipakai firmware (Kp, Ki, Kd) sebelum dimasukkan ke GUI. Rumusnya ada di bagian "Konversi ke gain firmware".

### Rangkaian blok

1. **Step** sebagai setpoint dalam derajat, diikuti **filter setpoint** berupa Transfer Fcn 1/(0,4s + 1). Firmware `esp32_pid` belum punya filter ini, jadi untuk membandingkan dengan rig, hilangkan filter (atau tambahkan filter yang sama di firmware).
2. **PID Controller (2DOF)** dengan Form = Ideal. Atur setpoint weight b = 1 dan c = 0, supaya D diambil dari pengukuran (tipe B, sama seperti firmware yang memakai laju gyro). Batas output ±100 dengan anti-windup clamping. Firmware juga memperlambat integral 50 % saat |e| ≥ 6° (I-zone) dan menghentikannya saat keluaran jenuh.
3. **Gain 0,008687** untuk mengubah u_pid menjadi ΔF (N).
4. **Transfer Fcn motor** 1/(τs + 1), diikuti **Transport Delay** sebesar T_delay.
5. **Sum gangguan**: tambahkan step kecil, misalnya 0,08 N, untuk uji gangguan.
6. **Transfer Fcn plant** dengan numerator [L] dan denominator [J b k]. Output-nya θ dalam rad.
7. **Gain 180/π** untuk mengubah θ ke derajat. Hasilnya diumpankan balik ke PID dan ditampilkan di Scope bersama u_pid.

### Parameter yang diisi

| Parameter | Nilai sementara | Satuan | Status |
| --- | --- | --- | --- |
| J | 0,0140 | kg·m² | Hitungan manual, tetap dipakai (tidak diukur ulang) |
| L | 0,25 | m | Terukur |
| b | 0,033 | N·m·s/rad | Dari uji ayunan 11-11 (motor mati). Ganti dengan hasil uji 7 |
| k | −0,054 sampai −0,081 | N·m/rad | Identifikasi data PID 18-11. Ganti dengan hasil uji 5 dan 6 |
| τ | 0,10 sampai 0,15 | s | Fit data PID 18-11, diperbaiki setelah SIT |
| T_delay | 0,03 sampai 0,05 | s | Fit data PID 18-11, diperbaiki setelah SIT |
| Gain u_pid ke ΔF | 0,008687 | N per satuan u_pid | Dari fit thrust motor 1 (F1 = F2 diasumsikan), berlaku untuk F-max 15 % (koreksi ±3,5 %). Kalau F-max diubah, hitung ulang: 2 × 0,1241 × (F-max − 8)/2 / 100 |

### Isian blok PID (bentuk Ideal = dependen)

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

### Konversi ke gain firmware (Kp, Ki, Kd)

Firmware dan GUI memakai bentuk paralel: u = Kp·e + Ki·∫e + Kd·(−laju gyro), dengan Kp dalam %/°, Ki dalam %/(°·s), dan Kd dalam %/(°/s). Dari PID dependen:

$$
K_i = \frac{K_{p,fw}}{T_i} \qquad\qquad K_d = K_{p,fw} \, T_d
$$

| Sumber | Kp (fw) | Ti (s) | Td (s) | Ki (fw) | Kd (fw) |
| --- | --- | --- | --- | --- | --- |
| Gain terbaik di rig (uji ke-7) | 3,0 | 1,5 | 0,33 | 2,0 | 1,0 |
| Titik awal Simulink (bagian "Langkah tuning") | 4,02 | 3 | 0,4 | 1,34 | 1,61 |

Batas slider di GUI: Kp 0 sampai 5, Ki 0 sampai 3, Kd 0 sampai 1,5. Titik awal Simulink memberi Kd 1,61, di atas batas slider. Pakai Td ≤ 0,37 s atau naikkan batas slider Kd.

### Rumus pegangan (lag motor diabaikan, Kp dalam N/rad)

Persamaan karakteristik closed-loop dengan PID dependen:

$$
J s^3 + (b + K_p L T_d)\, s^2 + (k + K_p L)\, s + \frac{K_p L}{T_i} = 0
$$

Batas bawah Kp (berlaku kalau k < 0) dan batas bawah Ti (dari kriteria Routh):

$$
K_p > \frac{|k|}{L} \qquad\qquad T_i > \frac{J \, K_p L}{(b + K_p L T_d)(k + K_p L)}
$$

Batas atas Kp datang dari lag dan tundaan motor. Untuk P saja nilainya sekitar 0,75 sampai 1,16 N/rad. Suku D memperlebar batas ini.

### Langkah tuning

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

### Yang dicek di Scope

- θ akhir sama dengan setpoint (offset hilang).
- Overshoot dan waktu settling.
- u_pid tidak menempel di ±100 terlalu lama.
- Hasil tetap stabil di semua kombinasi k, τ, T_delay ujung bawah dan ujung atas.

## 5. Membawa gain ke rig (laptop ini)

Gain dari Simulink dikonversi dulu ke Kp, Ki, Kd firmware (bagian "Konversi ke gain firmware"), lalu dimasukkan lewat slider atau kotak angka di GUI (buka gembok KUNCI di kartu Kontrol PID). Jangan mulai dengan Kp yang lebih kecil dari hasil simulasi: kalau k < 0, Kp terlalu kecil justru membuat batang jatuh.

### Pengaman yang harus aktif sebelum uji

Status di firmware `esp32_pid` dan GUI saat ini:

- [x] D diambil dari gyro (tipe B): u = trim + Kp·e + I − Kd·laju gyro
- [x] Saturasi u_pid ±100 dan anti-windup (I berhenti bertambah saat output jenuh, diperlambat 50 % saat |e| ≥ 6°)
- [ ] Filter setpoint: belum ada (setpoint langsung step)
- [x] Batas sudut: motor mati kalau |θ| melebihi batas mati (slider 29 sampai 33°). Default GUI sekarang MATI, jadi aktifkan lagi sebelum uji berisiko. PID hanya mau mulai kalau |θ| ≤ 30° saat batas mati aktif
- [x] Failsafe: motor 0 kalau tidak ada perintah GUI > 0,5 s atau data IMU putus > 50 ms
- [x] Soft-start 0 → 8 % dalam 1 s, tahan 0,7 s, lalu PID. Laju throttle dibatasi 40 %/s per motor
- [ ] Tombol E-stop fisik: belum ada. Yang tersedia: TURN OFF di GUI, STOP MOTOR, dan failsafe di atas

### Urutan uji di rig

1. Connect ke ESP32, tahan batang dekat 0°, lalu tekan TURN ON. Firmware menaikkan throttle sendiri (soft-start sampai bias 11,5 %), jadi tidak perlu dinaikkan manual. Lepas batang setelah PID aktif.
2. Kalau sudah tenang di 0°, tekan Trim di GUI (nilai I sekarang) supaya torsi tetap terkompensasi, lalu beri step kecil 3 sampai 5° dari kotak Setpoint dan rekam sebagai R2.
3. Rekam R3 (validasi) dengan pola step yang berbeda, lalu R4 (gangguan).
4. Kirim semua CSV ke laptop teman. Awasi suhu motor dan ESC di setiap sesi.

### Gejala dan obat

| Gejala | Yang diubah |
| --- | --- |
| Batang jatuh | Kp terlalu kecil, atau tanda F1/F2 atau IMU terbalik |
| Getar cepat | Td atau Kp terlalu besar |
| Ayunan lambat | Td terlalu kecil |
| Offset tidak hilang | Ti terlalu besar, atau I belum aktif. Di rig juga cek Trim, dan ingat integral diperlambat 50 % saat |e| ≥ 6° |
| Overshoot besar setelah step | Ti terlalu kecil, atau filter setpoint diperlambat |
| Hasil rig jauh beda dari Simulink | Model belum cocok: perbarui k, b, τ, T_delay lewat SIT |

## 6. Checklist serah terima

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

- [ ] Masukkan gain akhir ke GUI, uji di rig, dan catat hasilnya di `log_uji_pid.md`
- [ ] Perbarui `ringkasan_pengukuran.md` dengan k, b, τ, dan T_delay yang baru

**Laptop teman (penutup)**

- [ ] Identifikasi SIT dari R2, validasi dengan R3
- [ ] Perbarui τ, T_delay, dan model di Simulink, lalu sempurnakan gain
- [ ] Perbarui model dan slide
