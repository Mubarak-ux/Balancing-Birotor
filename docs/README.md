# Dokumentasi

README utama (instalasi, cara menjalankan, struktur kode) ada di **[`../README.md`](../README.md)**.

## Mulai dari mana?

| Saya ingin… | Buka |
|---|---|
| Melihat semua angka hasil pengukuran alat | [`pengukuran/ringkasan_pengukuran.md`](pengukuran/ringkasan_pengukuran.md) |
| Tahu bagaimana k, b, F, τ, atau T_delay diukur | [`pengukuran/detail_pengukuran.md`](pengukuran/detail_pengukuran.md) |
| Mengirim parameter ke laptop Simulink dan tuning PID dependen | [`kontrol_pid/tuning_pid_dependen.md`](kontrol_pid/tuning_pid_dependen.md) (Bagian I) |
| Tahu struktur kontrol firmware, pengaman, dan gain sekarang | [`kontrol_pid/README.md`](kontrol_pid/README.md) |
| Melihat riwayat uji PID dan identifikasi model | [`kontrol_pid/log_dan_identifikasi.md`](kontrol_pid/log_dan_identifikasi.md) |
| Membandingkan VERSI 1 (Blender) dan VERSI 2 (Processing) | [`versi2.md`](versi2.md) |

## Susunan folder

```
docs/
├── README.md                  # indeks ini
├── versi2.md                  # komparasi VERSI 1 vs VERSI 2
├── strukturPY.txt             # pohon direktori proyek
├── pengukuran/
│   ├── ringkasan_pengukuran.md   # semua angka, status, log sesi
│   ├── detail_pengukuran.md      # F, b, k, tau/T_delay: metode dan data
│   └── menghitung_J.png, rumus_awal_momen_inersia.png   # catatan hitungan J
├── kontrol_pid/
│   ├── README.md                 # struktur kontrol firmware, pengaman, gain
│   ├── tuning_pid_dependen.md    # serah terima (Bagian I) + rencana kerja (Bagian II)
│   ├── log_dan_identifikasi.md   # log 7 uji PID + identifikasi model
│   └── blok_diagram_pid*.svg     # diagram blok
├── assets/                    # foto tampak alat
└── referensi/skill_antislop/  # catatan skill anti-AI-slop (bukan bagian proyek kontrol)
```

## Data rekaman

CSV rekaman ada di `../data/` (tidak ikut git), dikelompokkan per sesi:

| Folder | Isi | Sumber untuk |
|---|---|---|
| `data/2026-11-09_11_uji_awal/` | Uji baca IMU dan uji ayunan | `detail_pengukuran.md`, Bagian 2 |
| `data/2026-11-18_uji_pid/` | 10 rekaman uji PID | `kontrol_pid/log_dan_identifikasi.md` |
| `data/2026-11-23_uji_sudut_motor_mati/` | Tahan batang 5°, 10°, 15° motor mati | `detail_pengukuran.md`, Bagian 3 |
| `data/2026-11-23_uji_k_pid_tunak/` | PID tunak 0°, 5°, 10°, −5° | `detail_pengukuran.md`, Bagian 3 dan 4 |

Rekaman baru dari GUI tersimpan di `data/`; pindahkan ke folder sesi bila perlu. Skrip analisisnya ada di
`../analisis/` (`hitung_k.py`, `hitung_tau_delay.py`).
