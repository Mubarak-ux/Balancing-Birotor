# Kontrol PID Hardware (Week 3)

Dokumentasi PID di alat asli (firmware `firmware/esp32_pid`): struktur kontrol, pengaman, dan gain.
Angka pengukuran ada di `docs/pengukuran/ringkasan_pengukuran.md`.

| File | Isi |
|---|---|
| [`tuning_pid_dependen.md`](tuning_pid_dependen.md) | **Mulai di sini untuk tuning.** Bagian I: paket serah terima ke laptop Simulink. Bagian II: rencana kerja, pedoman blok, langkah tuning |
| [`log_dan_identifikasi.md`](log_dan_identifikasi.md) | Bagian 1: log 7 uji PID 18-11. Bagian 2: identifikasi model rig dan tuning robust |

---

## Struktur kontrol (firmware `esp32_pid`)

```
e  = setpoint − sudut
u  = trim + Kp·e + I − Kd·(laju gyro)          (u dalam %, −100..100)
I += Ki·e·dt        jika |e| < 6°   (I-zone)
I += 0,5·Ki·e·dt    jika |e| ≥ 6°   (diperlambat, tidak dimatikan)
                    dan hanya jika keluaran tidak jenuh
bias = (8 + Fmax)/2,   R = (Fmax − 8)/2         (Fmax 15 → 11,5 ± 3,5 %)
kiri  = bias − u/100·R,   kanan = bias + u/100·R   (dibatasi 40 %/s per motor)
```

- Sudut + = sisi kanan naik. u > 0 → motor kanan naik.
- Loop IMU + PID 500 Hz; penulisan PWM ESC di task terpisah (core 0).
- Filter komplementer τ = 0,7 s, DLPF IMU 21 Hz (meredam getaran baling-baling).

## Pengaman

| Pengaman | Nilai |
|---|---|
| Soft-start | 0 → 8 % dalam 1 s, tahan 0,7 s, baru PID |
| Failsafe heartbeat GUI | > 0,5 s tanpa perintah → motor 0 |
| Batas mati sudut | 29–33° (slider), bisa dimatikan |
| Data IMU putus | > 50 ms → motor 0 |
| F-max (batas PID) | 8–20 % (default 15), terkunci + konfirmasi. Tes motor manual tidak dibatasi F-max (0–100 %) |

## Gain saat ini

| Kp (%/°) | Ki (%/(°·s)) | Kd (%/(°/s)) | I-zone |
|---|---|---|---|
| **3,0** | **2,0** | **1,0** | **6°** (luar zona 50 %) |

### Input di GUI: PID dependen

Kartu **Kontrol PID** di GUI memakai bentuk dependen: yang diisi **Kp**, **Ti** (s), dan **Td** (s).
**Ki dan Kd dihitung otomatis**:

```
Ki = Kp / Ti        (centang ∞ pada Ti = tanpa integral, Ki = 0)
Kd = Kp · Td
```

Dengan Ti dan Td tetap, cukup mengubah Kp dan Ki serta Kd ikut berubah. Nilai awal sama dengan gain
rig (Kp 3, Ti 1,5 s, Td 0,33 s, setara 3 / 2 / 1). Firmware membatasi Kp ≤ 5, Ki ≤ 3, Kd ≤ 1,5; GUI ikut
membatasi dan menampilkan peringatan kuning bila hasil hitungan melebihi batas, supaya angka di GUI
sama dengan yang diterima alat. Gembok KUNCI mengunci ketiga kotak. Hasil tuning dari Simulink
(Kp, Ti, Td) bisa langsung dimasukkan tanpa konversi manual.

Cara pakai trim: setelah batang tenang di 0°, tekan **Trim ← nilai I sekarang**.
