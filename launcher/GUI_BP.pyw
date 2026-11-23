"""Pintu masuk 'GUI BP' tanpa jendela konsol (dipakai oleh shortcut desktop)."""

import os
import sys
import traceback

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # akar proyek
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

try:
    from app.main import run
    sys.exit(run(initial_mode="hw"))
except SystemExit:
    raise
except Exception:
    # pythonw tidak punya konsol: simpan error ke berkas & tampilkan kotak pesan
    log = os.path.join(BASE_DIR, "gui_bp_error.log")
    with open(log, "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0, f"GUI BP gagal dibuka.\nRincian ada di:\n{log}", "GUI BP", 0x10)
    except Exception:
        pass
    sys.exit(1)
