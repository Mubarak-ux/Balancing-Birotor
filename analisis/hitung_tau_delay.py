"""Hitung lag motor (tau) dan tundaan (T_delay) dari rekaman PID (CSV rekaman GUI).

Model (sama dengan docs/kontrol_pid/log_dan_identifikasi.md, Bagian 2):

    J*th'' = s*L*(F_kanan - F_kiri) - b*th' - k*th + c0
    F_i    = lag orde-1 (tau) dari F(throttle_i) yang ditunda T_delay

J, b, k, L diambil sebagai diketahui (pilih lewat opsi). Throttle kiri/kanan
yang tercatat di CSV dipakai sebagai masukan; sudut dan laju gyro terukur
dipakai sebagai pembanding.

Metode: prediksi jangka pendek (multiple shooting). Batang tidak stabil
(k < 0), jadi simulasi satu rekaman penuh akan menyimpang. Sebagai gantinya,
tiap jendela pendek (default 0,2 s) dimulai dari sudut dan laju terukur,
diintegrasi dengan masukan throttle, lalu dibandingkan dengan data. Pasangan
(tau, T_delay) dicari di grid; c0 dihitung otomatis. Ketidakpastian dari
bootstrap antar jendela.

Pakai:
    python analisis/hitung_tau_delay.py data/a.csv data/b.csv ...
    python analisis/hitung_tau_delay.py data/*.csv --k -0.05 --b 0.033

Catatan ketelitian (diuji pada data simulasi dengan nilai sebenarnya diketahui):
data tanpa gangguan memberi hasil tepat; dengan torsi turbulen dan noise sensor,
tau dan T_delay cenderung terbaca lebih besar 0,01 sampai 0,03 s dari nilai
sebenarnya (sisi aman untuk tuning). Simpangan baku bootstrap yang dicetak hanya
mengukur sebaran antar jendela, bukan bias ini.

Rekaman harus berisi PID aktif dan perubahan torsi yang cukup (step setpoint
atau goyangan). Rekaman batang diam saja tidak memberi informasi tau/T_delay.
"""

import argparse
import csv
import os
import sys

import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from app.sim_backend import Params                      # L, F(u): sama dengan GUI/firmware

DT = 0.01                                               # s, grid seragam (data 100 Hz)
STEP_EVAL = 5                                           # bandingkan tiap 5 langkah (0,05 s)
W_OMEGA = 0.2                                           # s, bobot galat laju (deg/s -> deg)


def thrust(pct):
    """F(u) = KF*u - F0 untuk u >= 8 %, selain itu 0 (vektor)."""
    pct = np.asarray(pct, dtype=float)
    return np.where(pct >= Params.Fmin_pct, np.maximum(0.0, Params.KF * pct - Params.F0), 0.0)


def baca(path):
    t, th, om, on, thl, thr = [], [], [], [], [], []
    dibalik = 0
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.reader(f):
            if not r or r[0].startswith("#") or r[0] == "t_s" or len(r) < 8 or r[4] == "":
                continue
            p = r[7].strip().split(",")
            if len(p) < 17 or p[0] != "*":
                continue
            v = p[1:]
            try:
                t.append(float(r[0])); th.append(float(r[4])); om.append(float(v[2]))
                on.append(float(v[8])); thl.append(float(v[10])); thr.append(float(v[11]))
                dibalik = int(r[2])
            except ValueError:
                continue
    return dict(t=np.array(t), th=np.array(th), om=np.array(om), on=np.array(on),
                thl=np.array(thl), thr=np.array(thr), s=-1.0 if dibalik else 1.0)


def siapkan(path, horizon, stride, skip):
    """Resample ke grid seragam dan tentukan jendela prediksi."""
    d = baca(path)
    if len(d["t"]) < 100:
        return None
    t0, t1 = d["t"][0], d["t"][-1]
    t = np.arange(t0, t1, DT)
    s = d["s"]
    out = dict(name=os.path.basename(path), t=t, s=s)
    out["th"] = np.radians(np.interp(t, d["t"], d["th"]))                  # rad, bingkai tampilan
    out["om"] = np.radians(s * np.interp(t, d["t"], d["om"]))              # rad/s
    out["thl"] = np.interp(t, d["t"], d["thl"])
    out["thr"] = np.interp(t, d["t"], d["thr"])
    on = np.interp(t, d["t"], d["on"]) > 0.5
    k3 = np.ones(3) / 3
    out["th_s"] = np.convolve(out["th"], k3, mode="same")                  # awal jendela: sedikit dihaluskan
    out["om_s"] = np.convolve(out["om"], k3, mode="same")
    H = int(round(horizon / DT))
    starts = np.arange(int(skip / DT), len(t) - H - 1, int(round(stride / DT)))
    ok = np.array([on[i - 1:i + H + 1].all() for i in starts], dtype=bool)
    out["starts"], out["H"] = starts[ok], H
    # eksitasi: variasi cepat torsi perintah (buang tren lambat 1 s)
    Fc = s * Params.L * (thrust(out["thr"]) - thrust(out["thl"]))
    slow = np.convolve(Fc, np.ones(100) / 100, mode="same")
    out["excite"] = float(np.std((Fc - slow)[100:-100])) if len(Fc) > 300 else 0.0
    return out


def sapuan(rec, taus, tds, J, b, k):
    """Untuk tiap (T_delay, tau): jumlah S_aa, S_ap, S_pp per jendela.
    Residu = a - c0*p, a = data - prediksi(c0=0), p = sensitivitas terhadap c0."""
    t, s, L = rec["t"], rec["s"], Params.L
    starts, H = rec["starts"], rec["H"]
    nw, nT, nD = len(starts), len(taus), len(tds)
    Saa = np.zeros((nD, nT, nw)); Sap = np.zeros_like(Saa); Spp = np.zeros_like(Saa)
    alpha = 1.0 - np.exp(-DT / taus)                                       # (nT,)
    j_eval = np.arange(STEP_EVAL - 1, H, STEP_EVAL)
    th_m = rec["th"][starts[:, None] + j_eval[None, :] + 1]                # (nw, ne)
    om_m = rec["om"][starts[:, None] + j_eval[None, :] + 1]
    for di, td in enumerate(tds):
        thl = np.interp(t - td, t, rec["thl"]); thr = np.interp(t - td, t, rec["thr"])
        Fc = s * L * (thrust(thr) - thrust(thl))                           # N.m, perintah tertunda
        Y = np.empty((len(t), nT)); Y[0] = Fc[0]
        for n in range(1, len(t)):
            Y[n] = Y[n - 1] + alpha * (Fc[n] - Y[n - 1])                   # lag orde-1, vektor atas tau
        # state: (2 jalan c0 = 0 dan 1, nw, nT)
        th = np.broadcast_to(rec["th_s"][starts][None, :, None], (2, nw, nT)).copy()
        om = np.broadcast_to(rec["om_s"][starts][None, :, None], (2, nw, nT)).copy()
        c0 = np.array([0.0, 1.0])[:, None, None]
        pth, pom = [], []
        for j in range(H):
            tq = Y[starts + j, :][None, :, :]                              # (1, nw, nT)
            om = om + DT * (tq + c0 - b * om - k * th) / J
            th = th + DT * om
            if (j + 1) % STEP_EVAL == 0:
                pth.append(th.copy()); pom.append(om.copy())
        pth = np.stack(pth, axis=-1); pom = np.stack(pom, axis=-1)         # (2, nw, nT, ne)
        a_th = th_m[:, None, :] - pth[0]; a_om = om_m[:, None, :] - pom[0]
        p_th = pth[1] - pth[0]; p_om = pom[1] - pom[0]
        # gabung galat sudut (deg) dan galat laju terbobot (deg)
        r2d = 180.0 / np.pi
        a = np.concatenate([a_th * r2d, a_om * r2d * W_OMEGA], axis=-1)
        p = np.concatenate([p_th * r2d, p_om * r2d * W_OMEGA], axis=-1)
        Saa[di] = (a * a).sum(-1).transpose(1, 0)
        Sap[di] = (a * p).sum(-1).transpose(1, 0)
        Spp[di] = (p * p).sum(-1).transpose(1, 0)
    return Saa, Sap, Spp


def cari(recs, taus, tds, J, b, k, boot, seed):
    parts = [sapuan(r, taus, tds, J, b, k) for r in recs]
    Saa = np.concatenate([p[0] for p in parts], axis=-1)                   # (nD, nT, nW)
    Sap = np.concatenate([p[1] for p in parts], axis=-1)
    Spp = np.concatenate([p[2] for p in parts], axis=-1)
    c0 = Sap.sum(-1) / np.maximum(Spp.sum(-1), 1e-12)                      # c0 optimal tiap grid
    c0 = np.clip(c0, -0.05, 0.05)
    C = Saa - 2 * c0[..., None] * Sap + (c0 ** 2)[..., None] * Spp         # biaya per jendela
    tot = C.sum(-1)
    di, ti = np.unravel_index(np.argmin(tot), tot.shape)
    best = dict(tau=taus[ti], td=tds[di], c0=float(c0[di, ti]), cost=float(tot[di, ti]), nw=C.shape[-1])
    # bootstrap antar jendela
    rng = np.random.default_rng(seed)
    nW = C.shape[-1]
    flat = C.reshape(-1, nW)
    bt, bd = [], []
    for _ in range(boot):
        cnt = np.bincount(rng.integers(0, nW, nW), minlength=nW)
        g = np.argmin(flat @ cnt)
        i, j = np.unravel_index(g, tot.shape)
        bd.append(tds[i]); bt.append(taus[j])
    best["tau_sd"], best["td_sd"] = float(np.std(bt)), float(np.std(bd))
    best["rms"] = float(np.sqrt(best["cost"] / (nW * (2 * (recs[0]["H"] // STEP_EVAL)))))
    # pembanding: tanpa lag dan tanpa delay (sudut terkecil di grid)
    base = tot[0, 0]
    best["rms_base"] = float(np.sqrt(base / (nW * (2 * (recs[0]["H"] // STEP_EVAL)))))
    return best, tot


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="CSV rekaman GUI dengan PID aktif")
    ap.add_argument("--k", type=float, default=-0.05, help="k (N.m/rad), default -0,05")
    ap.add_argument("--b", type=float, default=0.033, help="b (N.m.s/rad), default 0,033")
    ap.add_argument("--J", type=float, default=0.0140, help="J (kg.m^2), default 0,0140")
    ap.add_argument("--horizon", type=float, default=0.2, help="panjang jendela prediksi (s), default 0,2")
    ap.add_argument("--stride", type=float, default=0.1, help="jarak antar jendela (s)")
    ap.add_argument("--skip", type=float, default=0.5, help="buang detik awal tiap rekaman (s)")
    ap.add_argument("--tau-max", type=float, default=0.40)
    ap.add_argument("--td-max", type=float, default=0.15)
    ap.add_argument("--boot", type=int, default=200, help="jumlah bootstrap")
    ap.add_argument("--no-sweep", action="store_true", help="jangan uji k +-0,02")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    recs = []
    for f in args.files:
        r = siapkan(f, args.horizon, args.stride, args.skip)
        if r is None or len(r["starts"]) < 5:
            print(f"{os.path.basename(f)}: dilewati (data kurang atau PID tidak aktif)")
            continue
        recs.append(r)
    if not recs:
        print("Tidak ada rekaman yang bisa dipakai.")
        return 1

    print(f"J={args.J}  b={args.b}  L={Params.L}  F(u)={Params.KF}*u-{Params.F0}  horizon={args.horizon}s\n")
    print(f"{'rekaman':36s} {'jendela':>8s} {'eksitasi':>10s}")
    for r in recs:
        print(f"{r['name'][:36]:36s} {len(r['starts']):8d} {r['excite']:10.4f} N.m")
    if max(r["excite"] for r in recs) < 0.003:
        print("\n! Eksitasi torsi kecil: batang hampir diam. tau/T_delay tidak bisa ditentukan dengan baik."
              "\n  Rekam step setpoint (0 -> 5 -> 0 -> -5 -> 0).")

    taus = np.arange(0.02, args.tau_max + 1e-9, 0.01)
    tds = np.arange(0.0, args.td_max + 1e-9, 0.005)
    ks = [args.k] if args.no_sweep else [args.k, args.k + 0.02, args.k - 0.02]
    print(f"\n{'k':>8s} {'tau (s)':>16s} {'T_delay (s)':>16s} {'c0 (N.m)':>10s} {'rms (deg)':>10s} {'rms tanpa lag':>14s}")
    for kk in ks:
        best, _ = cari(recs, taus, tds, args.J, args.b, kk, args.boot, args.seed)
        tag = " <- nominal" if kk == args.k else ""
        print(f"{kk:+8.3f} {best['tau']:7.3f} +-{best['tau_sd']:.3f} {best['td']:8.3f} +-{best['td_sd']:.3f}"
              f" {best['c0']:+10.4f} {best['rms']:10.2f} {best['rms_base']:14.2f}{tag}")
    edge = []
    if best["tau"] >= taus[-1] - 1e-9 or best["tau"] <= taus[0] + 1e-9:
        edge.append("tau")
    if best["td"] >= tds[-1] - 1e-9:
        edge.append("T_delay")
    if edge:
        print(f"\n! {', '.join(edge)} menempel di batas grid; perlebar dengan --tau-max / --td-max atau cek data.")
    print("\ntau = lag motor+baling-baling (orde-1). T_delay = tundaan gabungan (ESC 50 Hz, komunikasi, filter IMU).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
