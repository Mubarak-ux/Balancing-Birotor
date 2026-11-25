"""Preset gain PID dependen (Kp, Ti, Td) di data/pid_preset.json.

File ini ikut di-commit ke Git supaya preset bisa dipakai bersama di laptop
lain. Preset bawaan ada di kode (tidak ditulis ke file, tidak bisa dihapus).

Format file:
    {"versi": 1, "preset": [{"nama": "...", "kp": 3.0, "ti": 1.5, "td": 0.333,
                             "dibuat": "2026-11-25 14:02"}]}
ti = null berarti integral dimatikan (Ti = tak hingga, Ki = 0).
"""

import json
import os
import shutil
import time

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PRESET_PATH = os.path.join(DATA_DIR, "pid_preset.json")

# Rentang sama dengan input di GUI (Kp 0..5, Ti 0,1..30 s, Td 0..2 s).
KP_RANGE = (0.0, 5.0)
TI_RANGE = (0.1, 30.0)
TD_RANGE = (0.0, 2.0)

# Gain terbaik di rig: uji ke-7 (18-11-2026), paralel Kp 3 / Ki 2 / Kd 1.
# Td = 1/3 persis supaya Kd = Kp*Td = 1,000.
BUILTIN = [
    {"nama": "Uji-7 rig (bawaan)", "kp": 3.0, "ti": 1.5, "td": 1.0 / 3.0, "bawaan": True},
]


def _in(v, rng):
    return isinstance(v, (int, float)) and rng[0] <= v <= rng[1]


def valid(p):
    return (isinstance(p, dict) and isinstance(p.get("nama"), str) and p["nama"].strip()
            and _in(p.get("kp"), KP_RANGE) and _in(p.get("td"), TD_RANGE)
            and (p.get("ti") is None or _in(p.get("ti"), TI_RANGE)))


def load():
    """Kembalikan (daftar preset pengguna, pesan galat atau None).
    File belum ada = daftar kosong tanpa galat. Entri yang rusak dilewati."""
    if not os.path.exists(PRESET_PATH):
        return [], None
    try:
        with open(PRESET_PATH, "r", encoding="utf-8") as f:
            doc = json.load(f)
        items = doc.get("preset", []) if isinstance(doc, dict) else []
    except (OSError, ValueError) as e:
        return [], f"{os.path.basename(PRESET_PATH)} tidak bisa dibaca: {e}"
    good = [{"nama": p["nama"].strip(), "kp": float(p["kp"]),
             "ti": None if p.get("ti") is None else float(p["ti"]),
             "td": float(p["td"]), "dibuat": p.get("dibuat", "")}
            for p in items if valid(p)]
    skipped = len(items) - len(good)
    err = f"{skipped} preset di file tidak valid dan dilewati." if skipped else None
    return good, err


def save(presets):
    """Tulis daftar preset pengguna. File lama yang rusak dicadangkan dulu ke
    pid_preset.rusak.json supaya isinya tidak hilang. Kembalikan pesan galat
    atau None."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(PRESET_PATH):
            try:
                with open(PRESET_PATH, "r", encoding="utf-8") as f:
                    json.load(f)
            except ValueError:
                shutil.copyfile(PRESET_PATH, PRESET_PATH.replace(".json", ".rusak.json"))
        doc = {"versi": 1,
               "preset": [{"nama": p["nama"], "kp": round(p["kp"], 4),
                           "ti": None if p["ti"] is None else round(p["ti"], 4),
                           "td": round(p["td"], 4), "dibuat": p.get("dibuat", "")}
                          for p in presets]}
        tmp = PRESET_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, PRESET_PATH)       # ganti atomik: file tidak setengah tertulis
        return None
    except OSError as e:
        return str(e)


def now_text():
    return time.strftime("%Y-%m-%d %H:%M")


def same_gains(p, kp, ti, td, tol=1e-3):
    """True bila preset p sama dengan gain (kp, ti, td). ti None = integral mati."""
    if abs(p["kp"] - kp) > tol or abs(p["td"] - td) > tol:
        return False
    if p["ti"] is None or ti is None:
        return p["ti"] is None and ti is None
    return abs(p["ti"] - ti) <= tol
