"""Hitung kekakuan sudut k dari rekaman PID tunak (CSV rekaman GUI, mode Hardware).

Ide: saat PID menahan batang diam di sudut theta, torsi motor sama dengan torsi
gravitasi batang (percepatan = 0, laju = 0):

    L * (F_kanan - F_kiri) = k * theta - c0

Jadi dari beberapa rekaman diam di sudut berbeda (mis. 0, 5, 10 derajat),
kemiringan torsi motor terhadap sudut = k, dan c0 (torsi tetap) ikut keluar.
Gain PID yang dipakai tidak masuk hitungan; PID hanya penahan.

Pakai:
    python analisis/hitung_k.py data/a.csv data/b.csv data/c.csv
    python analisis/hitung_k.py data/*.csv --window 3 --skip 0

Tiap file = satu sudut. Yang dipakai hanya `--window` detik terakhir (default 8 s; batang
sudah tunak). Setpoint tidak perlu diketahui: yang dipakai sudut aktual.
"""

import argparse
import csv
import math
import os
import sys

import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from app.sim_backend import Params, thrust_n          # L, F(u): sama dengan GUI/firmware

# indeks field di baris mentah firmware (setelah tanda '*'):
# 0 sudut_lain, 1 sudut, 2 laju, 3 ax, 4 ay, 5 az, 6 suhu, 7 loop_hz,
# 8 pid_on, 9 u, 10 throttle_kiri, 11 throttle_kanan, 12 P, 13 I, 14 D
F_PID_ON, F_U, F_THR_L, F_THR_R, F_I = 8, 9, 10, 11, 13


def baca(path):
    """Kembalikan dict array: t, th, pid_on, u, thl, thr, i, dibalik."""
    t, th, on, u, thl, thr, ii = [], [], [], [], [], [], []
    dibalik = 0
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.reader(f):
            if not r or r[0].startswith("#") or r[0] == "t_s" or len(r) < 8:
                continue
            if r[4] == "":
                continue                                    # baris teks / terpotong
            p = r[7].strip().split(",")
            if len(p) < 17 or p[0] != "*":
                continue
            v = p[1:]
            try:
                t.append(float(r[0])); th.append(float(r[4]))
                on.append(float(v[F_PID_ON])); u.append(float(v[F_U]))
                thl.append(float(v[F_THR_L])); thr.append(float(v[F_THR_R]))
                ii.append(float(v[F_I])); dibalik = int(r[2])
            except ValueError:
                continue
    return dict(t=np.array(t), th=np.array(th), on=np.array(on), u=np.array(u),
                thl=np.array(thl), thr=np.array(thr), i=np.array(ii), dibalik=dibalik)


def titik_tunak(path, window, skip, fmax):
    d = baca(path)
    if len(d["t"]) < 20:
        return None, "data terlalu sedikit"
    t_end = d["t"][-1] - skip
    m = (d["t"] >= t_end - window) & (d["t"] <= t_end)
    if m.sum() < 20:
        return None, "jendela tunak terlalu pendek"
    th, t = d["th"][m], d["t"][m]
    sg = -1.0 if d["dibalik"] else 1.0                      # tanda sama dengan GUI
    F_l = np.array([thrust_n(x) for x in d["thl"][m]])
    F_r = np.array([thrust_n(x) for x in d["thr"][m]])
    torsi = sg * Params.L * float(np.mean(F_r - F_l))       # N.m, bingkai tampilan
    slope = float(np.polyfit(t, th, 1)[0])
    if d["on"][m].min() < 0.5:
        return None, "PID tidak aktif di jendela tunak (rekaman motor mati? tidak dipakai)"
    warn = []
    if abs(slope) > 0.3:
        warn.append(f"sudut masih bergeser {slope:+.2f} deg/s (belum tunak)")
    if th.std() > 1.0:
        warn.append(f"sudut bergoyang std {th.std():.2f} deg")
    if np.abs(d["u"][m]).max() > 95:
        warn.append("u hampir jenuh (+-100)")
    if d["thr"][m].max() >= fmax - 0.05 or d["thl"][m].max() >= fmax - 0.05:
        warn.append(f"throttle menyentuh F-max {fmax:g} %")
    return dict(file=os.path.basename(path), theta=float(th.mean()), std=float(th.std()),
                slope=slope, u=float(np.mean(d["u"][m])), torsi=torsi, warn=warn), None


def fit(points):
    th = np.radians([p["theta"] for p in points])
    tq = np.array([p["torsi"] for p in points])
    A = np.vstack([th, np.ones_like(th)]).T
    (k, c), *_ = np.linalg.lstsq(A, tq, rcond=None)
    res = tq - A @ np.array([k, c])
    ss_tot = float(((tq - tq.mean()) ** 2).sum())
    r2 = 1 - float((res ** 2).sum()) / ss_tot if ss_tot > 0 else float("nan")
    return float(k), float(c), r2, float(np.abs(res).max())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="CSV rekaman GUI, satu per sudut")
    ap.add_argument("--window", type=float, default=8.0, help="detik terakhir yang dipakai (default 8; batang bergoyang ~1 deg jadi perlu rata-rata panjang)")
    ap.add_argument("--skip", type=float, default=0.0, help="detik paling akhir yang dibuang (default 0)")
    ap.add_argument("--fmax", type=float, default=15.0, help="F-max saat rekam, untuk peringatan jenuh")
    args = ap.parse_args()

    pts, gagal = [], []
    for f in args.files:
        p, err = titik_tunak(f, args.window, args.skip, args.fmax)
        (pts if p else gagal).append(p or (f, err))

    print(f"L = {Params.L} m, F(u) = {Params.KF}*u - {Params.F0} N (8..15 %)\n")
    print(f"{'file':40s} {'theta':>8s} {'std':>6s} {'u':>7s} {'torsi':>10s}")
    for p in pts:
        print(f"{p['file'][:40]:40s} {p['theta']:+8.2f} {p['std']:6.2f} {p['u']:+7.2f} {p['torsi']:+10.4f}")
        for w in p["warn"]:
            print(f"    ! {w}")
    for f, err in gagal:
        print(f"{os.path.basename(f)}: dilewati ({err})")

    if len(pts) < 2 or max(p["theta"] for p in pts) - min(p["theta"] for p in pts) < 2.0:
        print("\nButuh minimal 2 sudut berbeda (selisih >= 2 deg) untuk menghitung k.")
        return 1
    k, c, r2, rmax = fit(pts)
    print(f"\nk  = {k:+.4f} N.m/rad   ({'tidak stabil alami' if k < 0 else 'stabil alami'})")
    per_u = Params.L * Params.KF * (args.fmax - 8) / 100        # N.m per 1 % u
    print(f"c0 = {-c:+.4f} N.m      (torsi tetap; u tunak di 0 deg ~ {c / per_u:+.1f} %)")
    print(f"R^2 = {r2:.3f}, galat torsi maks = {rmax:.4f} N.m, {len(pts)} titik")
    pos = [p for p in pts if p["theta"] > 0.5]
    neg = [p for p in pts if p["theta"] < -0.5]
    if len(pos) >= 2:
        print(f"k sisi +  = {fit(pos)[0]:+.4f} N.m/rad")
    if len(neg) >= 2:
        print(f"k sisi -  = {fit(neg)[0]:+.4f} N.m/rad")
    if len(pts) == 2:
        print("Catatan: hanya 2 titik, garis lewat tepat kedua titik (tanpa cek lurus). Tambah titik bila bisa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
