"""Jendela utama aplikasi."""

import collections
import math
import os
import re
import threading
import time

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

from .hw_stream import TelemetryStream
from .config import (ACCENT, AMBER, BORDER, GREEN, INK, MUTED, PLOT_BG,
                     PURPLE, RED)
from .metrics import (COL_D, COL_F1, COL_F2, COL_I, COL_MEAS, COL_P, COL_SP,
                      COL_T, COL_TH, COL_U, COL_W, DASH, METRIC_KEYS, compute_metrics)
from .hw_backend import (DATA_DIR, HAVE_SERIAL, HardwareBackend, list_ports,
                         looks_like_esp)
from .processing_launcher import start_processing
from .sim_backend import SimBackend
from .widgets.beam_view import BeamView
from .widgets.controls import Card, GainBox, Metric, Param, ParamBox, Readout, Section
from .widgets.dialogs import confirm, notify

Qt = QtCore.Qt

# ----------------------------------------------------------------------------
# IDENTITAS KELOMPOK 
# ----------------------------------------------------------------------------
GROUP_NAME = "Kelompok 1"
MEMBERS = [
    ("Mirza Pramiandra Bhirawa", "25/561291/SV/26548"),
    ("Iqbal Rasshid Mubarak", "25/567537/SV/27187"),
    ("Muhammad Ikhwan Ghozy", "25/562030/SV/26722"),
]

# ----------------------------------------------------------------------------
# SKENARIO UJI OTOMATIS
#   (nama, kondisi awal, perubahan)
#   kondisi awal : dict(sp=derajat, load=(massa_kg, posisi_m))
#   perubahan    : ("sp", derajat) atau ("load", (massa_kg, posisi_m))
# Tiap skenario: state di-reset -> fase "settle" dengan kondisi awal ->
# perubahan diterapkan -> fase "ukur" -> metrik dicatat.
# Semua fase dihitung dalam WAKTU SIMULASI, jadi aman saat di-pause.
# ----------------------------------------------------------------------------
SCENARIOS = [
    ("Step 0\u00b0 \u2192 +10\u00b0", dict(sp=0.0), ("sp", 10.0)),
    ("Step 0\u00b0 \u2192 \u221210\u00b0", dict(sp=0.0), ("sp", -10.0)),
    ("Step +10\u00b0 \u2192 0\u00b0", dict(sp=10.0), ("sp", 0.0)),
    ("Beban 50 g @ 10 cm", dict(sp=0.0), ("load", (0.05, 0.10))),
    ("Beban 100 g @ 10 cm", dict(sp=0.0), ("load", (0.10, 0.10))),
    ("Lepas beban 50 g @ 10 cm", dict(sp=0.0, load=(0.05, 0.10)), ("load", (0.0, 0.10))),
]
SCN_SETTLE_S = 4.0    # detik simulasi sebelum perubahan diterapkan
SCN_MEASURE_S = 8.0   # detik simulasi pengukuran setelah perubahan

SP_LIMIT = 20.0       # batas slider setpoint (derajat)
SP_STEP = 5.0         # besar tombol step setpoint
SETTLING_CRIT = 0.02  # kriteria settling 2 %

METRIC_TIPS = {
    "overshoot": "Overshoot maksimum (Mp) relatif terhadap besar step:\n"
                 "Mp = (\u03b8 puncak \u2212 \u03b8 akhir) / |step| \u00d7 100 %\n"
                 "Hanya untuk step setpoint.",
    "rise": "Rise time (tr): waktu respons naik dari 10 % ke 90 % besar step.\n"
            "Hanya untuk step setpoint.",
    "peak_time": "Peak time (tp): waktu dari event sampai puncak respons.\n"
                 "Step setpoint: puncak overshoot (\u2014 jika tidak ada overshoot).\n"
                 "Gangguan beban: saat deviasi terbesar.",
    "settling": "Settling time (ts): waktu sampai |e| tetap di dalam band toleransi.\n"
                "Step setpoint: band \u00b12 % dari besar step.\n"
                "Gangguan beban: band \u00b10.5\u00b0.\n"
                "e dihaluskan (moving average 0.2 s) agar noise sensor\n"
                "tidak membuat respons dianggap belum settle.\n"
                "Band ditampilkan sebagai area biru di grafik Response.",
    "error": "Steady-state error (ess): rata-rata e = setpoint \u2212 \u03b8 selama\n"
             "1 s terakhir. Muncul setelah 2 s sejak event.",
    "deviation": "Deviasi puncak: |e| maksimum setelah gangguan beban.\n"
                 "Hanya untuk gangguan beban.",
}
METRIC_TITLES = {
    "overshoot": "Overshoot (Mp)",
    "rise": "Rise time (tr)",
    "peak_time": "Peak time (tp)",
    "settling": "Settling 2% (ts)",
    "error": "Steady error (ess)",
    "deviation": "Peak deviation",
}
METRIC_COLORS = {
    "overshoot": ACCENT, "rise": ACCENT, "peak_time": ACCENT,
    "settling": PURPLE, "error": GREEN, "deviation": RED,
}


class PanelScroll(QtWidgets.QScrollArea):
    """Scroll area panel kanan: hanya gulir vertikal.

    Lebar minimumnya selalu mengikuti isi panel (dihitung ulang setiap tata
    letak isi berubah, mis. kartu hardware muncul, tombol TURN ON -> TURN OFF,
    teks status bertambah). Jadi isi tidak pernah lebih lebar dari area
    tampilnya dan scrollbar horizontal tidak muncul."""

    MIN_W, MAX_W = 340, 560

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMinimumWidth(self.MIN_W)
        self.setMaximumWidth(self.MAX_W)
        self._sync_pending = False

    def setWidget(self, w):
        super().setWidget(w)
        w.installEventFilter(self)
        self.sync_width()

    def eventFilter(self, obj, ev):
        if obj is self.widget() and ev.type() == QtCore.QEvent.LayoutRequest \
                and not self._sync_pending:
            self._sync_pending = True
            QtCore.QTimer.singleShot(0, self.sync_width)
        return super().eventFilter(obj, ev)

    def sync_width(self):
        self._sync_pending = False
        w = self.widget()
        if w is None:
            return
        # ruang scrollbar vertikal selalu disisakan (bisa muncul kapan saja)
        need = (w.minimumSizeHint().width()
                + self.verticalScrollBar().sizeHint().width()
                + 2 * self.frameWidth() + 2)
        # dibatasi MAX_W: satu widget yang kelewat lebar tidak boleh
        # mendorong panel keluar layar (mis. saat jendela fullscreen)
        self.setMinimumWidth(min(self.MAX_W, max(self.MIN_W, need)))
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAsNeeded if need > self.MAX_W else Qt.ScrollBarAlwaysOff)


# ----------------------------------------------------------------------------
# JENDELA UTAMA
# ----------------------------------------------------------------------------
class MainWindow(QtWidgets.QMainWindow):
    # Gain awal mode hardware (%/deg, %/(deg.s), %/(deg/s)). Dari model terukur
    # (J, b, k, F(throttle), bias tengah rentang, ESC 50 Hz). Data PID nyata
    # 18-11-2026 (Kp 3/Ki 1.5/Kd 1) berosilasi +/-3.6 deg, periode 1.1 s ->
    # cocok dengan lag motor+baling ~0.3-0.5 s + delay ~80 ms (bukan 0.1 s).
    # Gain default hardware: dipilih dari uji di alat (18-11-2026) dengan
    # firmware esp32_pid (loop 500 Hz, soft-start, I-zone 6 deg + integral 50 %
    # di luar zona). Lihat docs/kontrol_pid/.
    HW_GAINS = (3.0, 2.0, 1.0)

    TICK_MS = 20            # 50 Hz refresh UI
    WINDOW_S = 8.0          # rentang grafik (detik)
    EVENT_MAX_S = 60.0      # maksimum data yang disimpan per event
    PROP_IDLE_DPS = 900.0   # deg/s, putaran idle
    PROP_GAIN_DPS = 260.0   # deg/s per Newton thrust
    PROP_WRAP = 360000.0    # harus sinkron dengan NetworkIMU.PROP_WRAP_PERIOD
    MAX_CATCHUP_S = 0.1     # batas langkah simulasi per tick jika UI tersendat

    # hasil start_processing() dari thread latar -> thread GUI
    _open3d_done = QtCore.Signal(bool, str)

    def __init__(self, seed=None, initial_mode="hw"):
        super().__init__()
        self.setWindowTitle("Balancing Propeller")
        self._open3d_waits = 0
        self._open3d_done.connect(self._on_open3d_done)
        self._calibrating = False   # kalibrasi gyro ESP32 sedang berjalan
        self.sim = SimBackend(seed=seed)
        self.hw = HardwareBackend()
        self.be = self.sim          # backend aktif (sim / hw)
        self.mode = "sim"
        self._last_rec_msg = ""
        self.paused = False
        self.pid_locked = True     # gain PID terkunci agar tidak tergeser tak sengaja

        # buffer grafik (pendek, hanya jendela WINDOW_S) dan buffer event
        # (panjang, seluruh respons sejak event) dipisah supaya metrik
        # tidak rusak saat data lama terbuang.
        plot_len = int(self.WINDOW_S * 1000 / self.TICK_MS * 1.25)
        self.hist = collections.deque(maxlen=plot_len)
        self.thr_hist = collections.deque(maxlen=plot_len)   # (throttle kiri, kanan) %
        self.ev_buf = []
        self.ev_max = int(self.EVENT_MAX_S * 1000 / self.TICK_MS)

        self.frame = 0
        self.event = None          # (kind, t0)
        self.pend = None           # event yang menunggu debounce
        self._last_metrics = None
        self._conn_state = None
        self._t_last = None        # perf_counter tick terakhir
        self._acc = 0.0            # akumulator waktu nyata (detik)
        self._ylim = None

        self.debounce = QtCore.QTimer(self, singleShot=True)
        self.debounce.timeout.connect(self._commit_event)

        self.stream = TelemetryStream(on_impulse=self.trigger_impulse)
        self.stream.extra = {"mode": "sim"}
        self.prop1_rot = 0.0
        self.prop2_rot = 0.0

        self.scn = None            # state skenario yang sedang berjalan
        self.scn_queue = []

        root = QtWidgets.QWidget()
        rv = QtWidgets.QVBoxLayout(root)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)
        rv.addWidget(self._build_header())
        rv.addWidget(self._build_topstrip())

        body = QtWidgets.QWidget()
        bl = QtWidgets.QHBoxLayout(body)
        bl.setContentsMargins(14, 12, 14, 14)
        bl.setSpacing(0)
        split = QtWidgets.QSplitter(Qt.Horizontal)
        split.addWidget(self._build_left())
        split.addWidget(self._build_panel())
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 0)
        split.setChildrenCollapsible(False)
        split.setSizes([1000, 380])
        self.main_split = split
        bl.addWidget(split)
        rv.addWidget(body, 1)
        self.setCentralWidget(root)

        self._build_shortcuts()
        self._refresh_step_btn()
        self._apply_pid_lock()
        self._apply_initial_mode(initial_mode)
        self._restore_ui_state()

        self.timer = QtCore.QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.timer.start(self.TICK_MS)

    # ------------------------------------------------------------------
    # ukuran jendela menyesuaikan layar
    # ------------------------------------------------------------------
    def show_fitted(self):
        self.showMaximized()            # selalu penuh layar saat dibuka

    def closeEvent(self, event):
        self._save_ui_state()
        if self.hw.is_open:
            self.hw.send_pid(False)
            self.hw.stop_motors()
        self.hw.stop_recording()
        self.hw.disconnect()
        self.stream.close()
        super().closeEvent(event)

    def _save_ui_state(self):
        try:
            settings = QtCore.QSettings("BalancingBirotor", "GUI")
            settings.setValue("top_split", self.top_split.saveState())
            settings.setValue("left_split", self.left_split.saveState())
            settings.setValue("main_split", self.main_split.saveState())
        except Exception:
            pass

    def _restore_ui_state(self):
        try:
            settings = QtCore.QSettings("BalancingBirotor", "GUI")
            val = settings.value("top_split")
            if val:
                self.top_split.restoreState(val)
            val = settings.value("left_split")
            if val:
                self.left_split.restoreState(val)
            val = settings.value("main_split")
            if val:
                self.main_split.restoreState(val)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # HEADER
    # ------------------------------------------------------------------
    def _build_header(self):
        hdr = QtWidgets.QFrame()
        hdr.setObjectName("Header")
        hdr.setFixedHeight(54)
        hl = QtWidgets.QHBoxLayout(hdr)
        hl.setContentsMargins(18, 8, 18, 8)
        hl.setSpacing(10)

        logo = QtWidgets.QLabel("BP")
        logo.setObjectName("Logo")
        logo.setFixedSize(30, 30)
        logo.setAlignment(Qt.AlignCenter)

        title = QtWidgets.QLabel("Balancing Propeller")
        title.setObjectName("AppTitle")

        group = QtWidgets.QLabel(GROUP_NAME)
        group.setObjectName("GroupTag")

        course = QtWidgets.QLabel("PSKD \u00b7 Praktikum Sistem Kontrol Dasar")
        course.setObjectName("AppSub")
        course.setMinimumWidth(0)
        course.setSizePolicy(QtWidgets.QSizePolicy.Ignored,
                             QtWidgets.QSizePolicy.Preferred)

        sep = QtWidgets.QFrame()
        sep.setFixedSize(1, 22)
        sep.setStyleSheet(f"background: {BORDER};")

        names = QtWidgets.QLabel("  \u00b7  ".join(n for n, _ in MEMBERS))
        names.setObjectName("GroupNames")
        names.setToolTip("\n".join(f"{i}. {n}  \u2014  {nim}"
                                   for i, (n, nim) in enumerate(MEMBERS, 1)))
        names.setMinimumWidth(0)
        names.setSizePolicy(QtWidgets.QSizePolicy.Ignored,
                            QtWidgets.QSizePolicy.Preferred)

        hl.addWidget(logo)
        hl.addWidget(title)
        hl.addWidget(group)
        hl.addSpacing(4)
        hl.addWidget(course, 1)
        hl.addWidget(sep)
        hl.addWidget(names, 2)

        pill = QtWidgets.QFrame()
        pill.setObjectName("Pill")
        pl = QtWidgets.QHBoxLayout(pill)
        pl.setContentsMargins(11, 5, 13, 5)
        pl.setSpacing(6)
        self.pill_dot = QtWidgets.QLabel("\u25cf")
        self.pill_dot.setObjectName("PillDot")
        host, port = self.stream.addr
        self.pill_txt = QtWidgets.QLabel("PROCESSING  \u00b7  connecting\u2026")
        self.pill_txt.setObjectName("PillText")
        pill.setToolTip(f"UDP {host}:{port}\n"
                        "Status berdasarkan balasan ACK dari BalancingPropellerIMU.pde.\n"
                        "Hijau = Processing benar-benar menerima data.")
        pl.addWidget(self.pill_dot)
        pl.addWidget(self.pill_txt)
        hl.addWidget(pill)

        self.btn_open3d = QtWidgets.QPushButton("Buka viewer 3D")
        self.btn_open3d.setObjectName("Primary")
        self.btn_open3d.setToolTip("Jalankan viewer 3D Processing (BalancingPropellerIMU).\n"
                                   "Kompilasi butuh beberapa detik; jendela 3D muncul sendiri.")
        self.btn_open3d.clicked.connect(self.open_3d_viewer)
        hl.addWidget(self.btn_open3d)

        wrap = QtWidgets.QWidget()
        wv = QtWidgets.QVBoxLayout(wrap)
        wv.setContentsMargins(0, 0, 0, 0)
        wv.setSpacing(0)
        wv.addWidget(hdr)
        return wrap

    # ------------------------------------------------------------------
    # util grafik
    # ------------------------------------------------------------------
    def _style_plot(self, pl):
        for ax in ("left", "bottom"):
            pl.getAxis(ax).setPen(pg.mkPen(BORDER))
            pl.getAxis(ax).setTextPen(pg.mkPen(MUTED))
        pl.hideButtons()
        pl.setMenuEnabled(False)
        pl.showGrid(x=True, y=True, alpha=0.10)

    def _make_event_marker(self, plot):
        """InfiniteLine vertikal yang menandai saat setpoint/beban berubah."""
        line = pg.InfiniteLine(angle=90, movable=False,
                               pen=pg.mkPen(AMBER, width=1.2, style=Qt.DashLine))
        line.setVisible(False)
        plot.addItem(line)
        return line

    @staticmethod
    def _make_legend(plot):
        leg = plot.addLegend(offset=(12, 8), labelTextSize="8pt")
        leg.setBrush(pg.mkBrush(255, 255, 255, 225))
        leg.setPen(pg.mkPen(BORDER))
        return leg

    @staticmethod
    def _curve(plot, **kw):
        c = plot.plot(**kw)
        c.setDownsampling(auto=True, method="peak")
        c.setClipToView(True)
        return c

    @staticmethod
    def _make_table(headers, stretch_col=None):
        tbl = QtWidgets.QTableWidget(0, len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        tbl.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        tbl.setAlternatingRowColors(True)
        tbl.setShowGrid(False)
        hh = tbl.horizontalHeader()
        hh.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        if stretch_col is not None:
            hh.setSectionResizeMode(stretch_col, QtWidgets.QHeaderView.ResizeToContents)
        return tbl

    @staticmethod
    def _append_row(tbl, values):
        row = tbl.rowCount()
        tbl.insertRow(row)
        for col, val in enumerate(values):
            item = QtWidgets.QTableWidgetItem(val)
            if col > 0:
                item.setTextAlignment(Qt.AlignCenter)
            tbl.setItem(row, col, item)
        tbl.scrollToBottom()

    # ------------------------------------------------------------------
    # KOLOM KIRI: animasi + tab telemetri / log / skenario
    # ------------------------------------------------------------------
    def _build_left(self):
        pg.setConfigOptions(antialias=False, background=PLOT_BG, foreground=MUTED)

        self.view = BeamView()
        self.view.impulse_requested.connect(self.trigger_impulse)
        self.view.setMinimumHeight(240)
        self.view.Fmax, self.view.L = 2.0, self.be.p.L
        self.view.LIMIT_DEG = math.degrees(self.be.p.stop)
        lim = self.view.LIMIT_DEG

        # ---------- Tab: Response (sudut) ----------
        self.p1 = pg.PlotWidget(background=PLOT_BG)
        self.p1.setLabel("left", "Sudut \u03b8", "\u00b0")
        self.p1.setLabel("bottom", "Waktu", "s")
        self._make_legend(self.p1)
        self.c_meas = self._curve(self.p1, pen=pg.mkPen("#BCC9D8", width=1), name="IMU mentah")
        self.c_th = self._curve(self.p1, pen=pg.mkPen(INK, width=2), name="\u03b8 aktual")
        self.c_sp = self._curve(self.p1, pen=pg.mkPen(ACCENT, width=1.6, style=Qt.DashLine),
                                name="Setpoint")
        # garis batas mekanik
        for y in (-lim, lim):
            self.p1.addLine(y=y, pen=pg.mkPen(RED, width=1, style=Qt.DotLine))
        # band toleransi settling
        self.band = pg.LinearRegionItem(values=(0, 0), orientation="horizontal",
                                        movable=False,
                                        brush=pg.mkBrush(3, 105, 161, 22),
                                        pen=pg.mkPen(ACCENT, width=0))
        self.band.setZValue(-10)
        self.band.setVisible(False)
        self.p1.addItem(self.band)
        self._set_angle_range(0.0)      # tanpa data -> rentang minimum +-25 deg

        # ---------- Tab: PID term breakdown ----------
        self.p3 = pg.PlotWidget(background=PLOT_BG)
        self.p3.setLabel("left", "Kontribusi", "%")
        self.p3.setLabel("bottom", "Waktu", "s")
        self.p3.setYRange(-110, 110)
        self.p3.setXLink(self.p1)
        self._make_legend(self.p3)
        self.c_pt = self._curve(self.p3, pen=pg.mkPen(INK, width=1.8), name="P")
        self.c_it = self._curve(self.p3, pen=pg.mkPen(GREEN, width=1.8), name="I")
        self.c_dt = self._curve(self.p3, pen=pg.mkPen(PURPLE, width=1.8), name="D")
        self.c_ut = self._curve(self.p3, pen=pg.mkPen("#8DA0B5", width=1.4, style=Qt.DashLine),
                                name="u total")

        # ---------- Tab: Error & kecepatan sudut ----------
        self.p4 = pg.PlotWidget(background=PLOT_BG)
        self.p4.setLabel("left", "Error e = sp \u2212 \u03b8", "\u00b0")
        self.p4.addLine(y=0, pen=pg.mkPen("#C9D5E2", width=1))
        self.p4.setXLink(self.p1)
        self.c_err = self._curve(self.p4, pen=pg.mkPen(RED, width=1.8))

        self.p5 = pg.PlotWidget(background=PLOT_BG)
        self.p5.setLabel("left", "\u03c9", "\u00b0/s")
        self.p5.setLabel("bottom", "Waktu", "s")
        self.p5.setXLink(self.p1)
        self.c_omega = self._curve(self.p5, pen=pg.mkPen(PURPLE, width=1.8))

        # ---------- Tab: Throttle tiap motor ----------
        self.p7 = pg.PlotWidget(background=PLOT_BG)
        self.p7.setLabel("left", "Throttle", "%")
        self.p7.setLabel("bottom", "Waktu", "s")
        self.p7.setXLink(self.p1)
        self._make_legend(self.p7)
        self.c_thr1 = self._curve(self.p7, pen=pg.mkPen(INK, width=1.8), name="Kiri (CW)")
        self.c_thr2 = self._curve(self.p7, pen=pg.mkPen(PURPLE, width=1.8, style=Qt.DashLine),
                                  name="Kanan (CCW)")
        # garis batas kerja PID: F-min 8 % dan F-max (hanya bermakna di hardware)
        self.ln_fmin = self.p7.addLine(y=8.0, pen=pg.mkPen(MUTED, width=1, style=Qt.DotLine))
        self.ln_fmax = self.p7.addLine(y=15.0, pen=pg.mkPen(RED, width=1, style=Qt.DotLine))

        plots = (self.p1, self.p3, self.p4, self.p5, self.p7)
        for pl in plots:
            self._style_plot(pl)
        self.event_markers = [self._make_event_marker(pl) for pl in plots]

        def stack(*widgets):
            w = QtWidgets.QWidget()
            lay = QtWidgets.QVBoxLayout(w)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(6)
            for x in widgets:
                lay.addWidget(x, 1)
            return w

        tabs = QtWidgets.QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(stack(self.p1), "Respons")
        tabs.addTab(stack(self.p3), "Suku PID")
        tabs.addTab(stack(self.p4, self.p5), "Error && \u03c9")
        tabs.addTab(self._build_tuning_log_tab(), "Log tuning")
        self._scn_tab_idx = tabs.addTab(self._build_scenario_tab(), "Skenario otomatis")
        self.tabs = tabs

        telemetry = Card("Telemetri", "jendela 10 s terakhir")
        telemetry.body.addWidget(tabs, 1)

        # Baris atas: animasi 2D (kiri) + grafik throttle tiap motor (kanan),
        # supaya throttle selalu terlihat tanpa pindah tab.
        thr_card = Card("Throttle motor", "kiri / kanan, %")
        thr_card.body.addWidget(self.p7, 1)
        thr_card.setMinimumWidth(260)
        top = QtWidgets.QSplitter(Qt.Horizontal)
        view_box = QtWidgets.QWidget()
        vb = QtWidgets.QVBoxLayout(view_box)
        vb.setContentsMargins(0, 0, 0, 0)
        vb.setSpacing(0)
        vb.addWidget(self.view, 1)
        vb.addWidget(self._build_readout())     # pembacaan utama di bawah visual 2D
        top.addWidget(view_box)
        top.addWidget(thr_card)
        top.setStretchFactor(0, 35)
        top.setStretchFactor(1, 65)
        top.setSizes([520, 980])
        top.setChildrenCollapsible(False)
        self.top_split = top

        left = QtWidgets.QSplitter(Qt.Vertical)
        left.addWidget(top)
        left.addWidget(telemetry)
        left.setSizes([380, 440])
        left.setStretchFactor(0, 4)
        left.setStretchFactor(1, 6)
        left.setChildrenCollapsible(False)
        self.left_split = left
        return left

    # ---- tab riwayat tuning ----
    def _build_tuning_log_tab(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(6, 8, 6, 6)
        lay.setSpacing(8)

        info = QtWidgets.QLabel("Simpan gain (Kp, Ti, Td dan hasil Ki, Kd) saat ini beserta metrik "
                                "respons terakhir untuk membandingkan hasil tuning.")
        info.setObjectName("EventLabel")
        info.setWordWrap(True)
        lay.addWidget(info)

        self.tuning_table = self._make_table(
            ["t", "Kp", "Ti", "Td", "Ki", "Kd", "Event", "Mp", "tr", "ts", "ess"], stretch_col=6)
        lay.addWidget(self.tuning_table, 1)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(7)
        b_log = QtWidgets.QPushButton("Catat gain saat ini")
        b_log.setObjectName("Primary")
        b_log.setToolTip("Simpan Kp/Ti/Td (dan Ki/Kd) saat ini + metrik respons terakhir (Ctrl+L)")
        b_log.clicked.connect(self.log_tuning)
        b_clear = QtWidgets.QPushButton("Bersihkan")
        b_clear.clicked.connect(lambda: self.tuning_table.setRowCount(0))
        row.addStretch(1)
        row.addWidget(b_clear)
        row.addWidget(b_log)
        lay.addLayout(row)
        return w

    # ---- tab skenario uji otomatis ----
    def _build_scenario_tab(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(6, 8, 6, 6)
        lay.setSpacing(8)

        top = QtWidgets.QHBoxLayout()
        top.setSpacing(7)
        self.scenario_status = QtWidgets.QLabel(
            f"Belum dijalankan  \u00b7  {len(SCENARIOS)} skenario, masing-masing "
            f"{SCN_SETTLE_S:.0f} s settle + {SCN_MEASURE_S:.0f} s ukur (waktu simulasi)")
        self.scenario_status.setObjectName("EventLabel")
        self.scenario_status.setWordWrap(True)
        self.btn_scn_run = QtWidgets.QPushButton("Jalankan semua")
        self.btn_scn_run.setObjectName("Primary")
        self.btn_scn_run.setToolTip("Jalankan semua skenario (F5)")
        self.btn_scn_run.clicked.connect(self.run_scenarios)
        self.btn_scn_stop = QtWidgets.QPushButton("Stop")
        self.btn_scn_stop.setObjectName("Danger")
        self.btn_scn_stop.setToolTip("Hentikan skenario (Esc)")
        self.btn_scn_stop.setEnabled(False)
        self.btn_scn_stop.clicked.connect(lambda: self.stop_scenarios("Dihentikan"))
        top.addWidget(self.scenario_status, 1)
        top.addWidget(self.btn_scn_stop)
        top.addWidget(self.btn_scn_run)
        lay.addLayout(top)

        self.scenario_table = self._make_table(
            ["Skenario", "Kp / Ti / Td", "Mp", "tr", "tp", "ts", "ess", "Deviasi"],
            stretch_col=0)
        lay.addWidget(self.scenario_table, 1)
        return w

    # ------------------------------------------------------------------
    # PANEL KANAN: kontrol
    # ------------------------------------------------------------------
    def _build_panel(self):
        # lebar mengikuti isi -> tanpa scrollbar horizontal (lihat PanelScroll)
        scroll = PanelScroll()

        panel = QtWidgets.QWidget()
        pv = QtWidgets.QVBoxLayout(panel)
        pv.setContentsMargins(10, 0, 4, 0)
        pv.setSpacing(10)

        pv.addWidget(self._build_source_card())

        # kartu sendiri untuk aksi utama mode hardware (disembunyikan di simulasi)
        self.power_card = Card("Toggle", "alat asli")
        self.power_card.body.addWidget(self.btn_pid_run)
        self.power_card.setVisible(False)
        pv.addWidget(self.power_card)

        controller = Card("Kontrol PID", "Kp \u00b7 Ti \u00b7 Td")
        # Tombol gembok di header kartu: kunci/buka slider gain PID.
        self.btn_pid_lock = QtWidgets.QPushButton()
        self.btn_pid_lock.setObjectName("Lock")
        self.btn_pid_lock.setCheckable(True)
        self.btn_pid_lock.setChecked(True)
        self.btn_pid_lock.setFixedWidth(54)
        self.btn_pid_lock.clicked.connect(self.toggle_pid_lock)
        controller.head.addWidget(self.btn_pid_lock)
        # Rentang slider disesuaikan dengan model terukur (docs/pengukuran/ringkasan_pengukuran.md):
        # di atas kira-kira Kp > 0.2 + 11.4*Kd sistem tidak stabil.
        # PID dependen: yang diisi Kp, Ti, Td. Ki = Kp/Ti dan Kd = Kp*Td mengikuti
        # otomatis, jadi cukup mengubah Kp. self.ki dan self.kd hanya memegang nilai
        # turunan (dipakai backend, log tuning, skenario) dan tidak ditampilkan.
        kp0, ti0, td0 = self._to_dependen(self.be.kp, self.be.ki, self.be.kd)
        self.kp = Param("Kp", 0, 5, kp0, 0.05, "%/\u00b0")
        self.ti = ParamBox("Ti", 0.1, 30.0, ti0 or 1.5, 0.1, "s", 2, off_label="\u221e")
        self.td = ParamBox("Td", 0.0, 2.0, td0, 0.01, "s", 3)
        self.ti.set_off_silent(ti0 is None)
        self.ki = Param("Ki", 0, 3, self.be.ki, 0.05, "%/(\u00b0\u00b7s)")
        self.kd = Param("Kd", 0, 1.5, self.be.kd, 0.05, "%/(\u00b0/s)")
        self.kp.setToolTip("Gain proporsional: u = Kp \u00b7 (e + \u222be dt / Ti \u2212 Td \u00b7 laju gyro)\n"
                           "Ubah Kp saja: Ki dan Kd ikut berubah (Ki = Kp/Ti, Kd = Kp\u00b7Td).\n"
                           "Gain terpilih di alat: Kp 3, Ti 1,5 s, Td 0,33 s")
        self.ti.setToolTip("Waktu integral Ti (s). Makin kecil, integral makin kuat.\n"
                           "Centang \u221e untuk mematikan integral (Ki = 0).")
        self.td.setToolTip("Waktu derivatif Td (s), D pada pengukuran (laju gyro).")
        # kotak pembacaan gain turunan (hanya baca)
        self.box_ki = GainBox("Ki", "%/(°·s)", "Gain integral, Ki = Kp / Ti (dihitung dari Kp dan Ti)")
        self.box_kd = GainBox("Kd", "%/(°/s)", "Gain derivatif, Kd = Kp · Td (dihitung dari Kp dan Td)")
        self.lb_dep = QtWidgets.QLabel()                 # pesan bila Ki/Kd dibatasi firmware
        self.lb_dep.setObjectName("EventLabel")
        self.lb_dep.setWordWrap(True)
        self.lb_dep.setVisible(False)
        for w in (self.kp, self.ti, self.td):
            controller.body.addWidget(w)
            w.changed.connect(self.on_gains)
        boxes = QtWidgets.QHBoxLayout()
        boxes.setSpacing(8)
        boxes.addWidget(self.box_ki, 1)
        boxes.addWidget(self.box_kd, 1)
        controller.body.addLayout(boxes)
        controller.body.addWidget(self.lb_dep)
        controller.body.addWidget(self.lim_box)      # indikator limit switch (hardware)
        self._refresh_dependen()
        pv.addWidget(controller)

        ref = Card("Masukan", "setpoint")
        self.sp = Param("Setpoint", -SP_LIMIT, SP_LIMIT, 0, 1, "\u00b0", 1)
        self.lm = Param("Load mass", 0, 500, 0, 10, "g", 0)
        self.lx = Param("Load position", 5, 15, 10, 1, "cm", 1)
        self.nz = Param("Noise (\u03c3)", 0, 2, self.be.noise, 0.05, "\u00b0")
        self.lx.setToolTip("Jarak beban dari poros (5 \u2013 15 cm, sisi kiri)")
        self.nz.setToolTip("Standar deviasi noise sensor IMU")
        self.sp.changed.connect(self.on_sp)
        self.lm.changed.connect(self.on_load)
        self.lx.changed.connect(self.on_load)
        self.nz.changed.connect(lambda v: setattr(self.be, "noise", v))
        for w in (self.sp, self.lm, self.lx, self.nz):
            ref.body.addWidget(w)
        pv.addWidget(ref)

        metrics = Card("Performa respons", "Karakteristik System")
        self.mt_event = QtWidgets.QLabel("Menunggu perubahan setpoint / beban")
        self.mt_event.setObjectName("EventLabel")
        self.mt_event.setWordWrap(True)
        metrics.body.addWidget(self.mt_event)

        mg = QtWidgets.QGridLayout()
        mg.setSpacing(7)
        self.metric_w = {}
        for i, key in enumerate(METRIC_KEYS):
            m = Metric(METRIC_TITLES[key], METRIC_COLORS[key], tooltip=METRIC_TIPS[key])
            self.metric_w[key] = m
            mg.addWidget(m, i // 2, i % 2)
        metrics.body.addLayout(mg)
        pv.addWidget(metrics)
        pv.addWidget(self.hw_adv_card)
        self.hw_adv_card.setVisible(False)

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(7)
        self.btn_pause = QtWidgets.QPushButton("Pause")
        self.btn_pause.setObjectName("Primary")
        self.btn_pause.setToolTip("Pause / lanjutkan simulasi (Space)")
        self.btn_pause.clicked.connect(self.toggle_pause)
        b_reset = QtWidgets.QPushButton("\u21ba  Reset")
        b_reset.setObjectName("Danger")
        b_reset.setToolTip("Reset simulasi, setpoint & beban ke default (Ctrl+R).\n"
                           "Gain PID dan noise tidak diubah.")
        b_reset.clicked.connect(self.reset)
        self.btn_int = b_int = QtWidgets.QPushButton("Reset Integral")
        b_int.setToolTip("Kosongkan akumulator integral PID (Ctrl+I)")
        b_int.clicked.connect(lambda: self.be.reset_integral())
        self.btn_step = QtWidgets.QPushButton(f"+{SP_STEP:.0f}\u00b0 Setpoint")
        self.btn_step.setObjectName("Warning")
        self.btn_step.setToolTip(f"Naikkan setpoint {SP_STEP:.0f}\u00b0 "
                                 f"(maks {SP_LIMIT:.0f}\u00b0)  (Ctrl+\u2191)")
        self.btn_step.clicked.connect(self.step_sp)

        self.btn_disturb = QtWidgets.QPushButton("Sentak gangguan (impuls)")
        self.btn_disturb.setToolTip("Beri sentakan gangguan torsi mendadak pada batang (Tombol D / Space di Processing)")
        self.btn_disturb.clicked.connect(lambda: self.trigger_impulse(2.5))

        grid.addWidget(self.btn_pause, 0, 0)
        grid.addWidget(b_reset, 0, 1)
        grid.addWidget(b_int, 1, 0)
        grid.addWidget(self.btn_step, 1, 1)
        grid.addWidget(self.btn_disturb, 2, 0, 1, 2)
        pv.addLayout(grid)

        pv.addStretch(1)
        scroll.setWidget(panel)
        self.panel_scroll = scroll
        return scroll

    # ------------------------------------------------------------------
    # SUMBER DATA: simulasi / hardware (ESP32 + IMU GY-521)
    #   Tahap 1: ESP32 hanya membaca IMU; motor belum dikendalikan.
    # ------------------------------------------------------------------
    def _build_source_card(self):
        card = Card("Sumber data", "simulasi / alat asli")

        self.cb_mode = QtWidgets.QComboBox()
        self.cb_mode.addItem("Simulasi", "sim")
        self.cb_mode.addItem("Hardware", "hw")
        self.cb_mode.currentIndexChanged.connect(
            lambda _: self.set_mode(self.cb_mode.currentData()))
        card.body.addWidget(self.cb_mode)

        # Mode hardware: blok koneksi selalu terlihat (tingkat 1-2),
        # pengaturan jarang dipakai dilipat dalam seksi (tingkat 3).
        self.hw_box = QtWidgets.QWidget()
        hv = QtWidgets.QVBoxLayout(self.hw_box)
        hv.setContentsMargins(0, 0, 0, 0)
        hv.setSpacing(4)

        # ---------------- koneksi (selalu terlihat) ----------------
        conn = QtWidgets.QWidget()
        g = QtWidgets.QGridLayout(conn)
        g.setContentsMargins(0, 0, 0, 0)
        g.setHorizontalSpacing(6)
        g.setVerticalSpacing(6)
        self.cb_port = QtWidgets.QComboBox()
        self.cb_port.setMinimumWidth(0)
        self.cb_port.setSizeAdjustPolicy(
            QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.cb_port.setToolTip("Port yang tampak seperti ESP32 (CP210x/CH340)\n"
                                "ditaruh paling atas, port Bluetooth di bawah.")
        # Nama port CH340/CP210x panjang -> combo boleh menyusut (teks dipotong)
        self.cb_port.setMinimumContentsLength(6)
        self.cb_port.setSizePolicy(QtWidgets.QSizePolicy.Ignored,
                                   QtWidgets.QSizePolicy.Fixed)
        b_refresh = QtWidgets.QPushButton("Scan")
        b_refresh.setToolTip("Scan ulang port COM")
        b_refresh.clicked.connect(self._refresh_ports)
        self.btn_conn = QtWidgets.QPushButton("Connect")
        self.btn_conn.setObjectName("Primary")
        self.btn_conn.setMinimumWidth(92)   # muat untuk "Disconnect"
        self.btn_conn.clicked.connect(self._toggle_connect)
        g.addWidget(self.cb_port, 0, 0, 1, 4)
        g.addWidget(b_refresh, 1, 0)
        g.addWidget(self.btn_conn, 1, 1, 1, 3)
        g.setColumnStretch(1, 1)
        g.setColumnStretch(3, 1)
        self.hw_status = QtWidgets.QLabel()
        self.hw_status.setObjectName("EventLabel")
        self.hw_status.setWordWrap(True)
        self.hw_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # jangan biarkan teks status (mis. pesan ESP32 panjang tanpa spasi)
        # menentukan lebar minimum panel kanan
        self.hw_status.setMinimumWidth(1)
        self.hw_status.setSizePolicy(QtWidgets.QSizePolicy.Ignored,
                                     QtWidgets.QSizePolicy.Preferred)
        g.addWidget(self.hw_status, 2, 0, 1, 4)
        hv.addWidget(conn)

        # tombol utama PID dibuat di sini, ditempatkan di kartu "Kontrol PID"
        self.pid_run = False
        self.btn_pid_run = QtWidgets.QPushButton("TURN ON")
        self.btn_pid_run.setObjectName("Hero")
        self.btn_pid_run.setToolTip("Kontrol sudut batang oleh ESP32 (firmware esp32_pid).\n"
                                    "Soft-start ~1,7 s, lalu motor bekerja di sekitar bias\n"
                                    "(8 + F-max)/2. Setpoint & Kp/Ki/Kd diambil dari panel.")
        self.btn_pid_run.clicked.connect(self._toggle_pid_run)
        self.btn_pid_run.setVisible(False)

        # Pengaturan tingkat 3 dikumpulkan di kartu terpisah (ditaruh di bawah
        # kartu PID & performa oleh _build_panel), hanya tampil di hardware.
        self.hw_adv_card = Card("Pengaturan alat", "setting")
        adv = self.hw_adv_card.body
        adv.setSpacing(0)

        # ---------------- seksi: penyetelan PID alat ----------------
        sec_pid = Section("Penyetelan PID alat", expanded=True)
        self.trim = Param("Trim", -60.0, 60.0, 0.0, 1.0, "%", 1)
        self.trim.setToolTip("Feedforward u (%) yang selalu ditambahkan ke keluaran PID.\n"
                             "Isi dengan nilai I saat batang sudah diam di setpoint\n"
                             "(tombol di bawah) agar respons tidak lambat/berayun.")
        self.trim.changed.connect(self._on_trim_changed)
        sec_pid.add(self.trim, 0)
        self.btn_trim_from_i = QtWidgets.QPushButton("Trim ← nilai I sekarang")
        self.btn_trim_from_i.setToolTip("Pindahkan nilai integral saat ini ke Trim, lalu nolkan\n"
                                        "integral. Pakai saat PID aktif dan batang sudah tenang.")
        self.btn_trim_from_i.clicked.connect(self._trim_from_integral)
        sec_pid.add(self.btn_trim_from_i, 1)
        # "Batas mati" sudut (software) dihapus dari GUI: batas fisik kini
        # ditangani limit switch hardware. GUI selalu mengirim cutoff_on = 0.
        adv.addWidget(sec_pid)

        # ---------------- seksi: sensor ----------------
        sec_sensor = Section("Sensor IMU")
        self.chk_inv = QtWidgets.QCheckBox("Balik arah sudut")
        self.chk_inv.setToolTip("Centang jika arah miring di layar berlawanan\n"
                                "dengan arah miring batang asli.")
        self.chk_inv.toggled.connect(self._on_mapping)
        self.btn_calib = QtWidgets.QPushButton("Kalibrasi gyro")
        self.btn_calib.setToolTip("Minta ESP32 menghitung ulang bias gyro (~2 s).\n"
                                  "DIAMKAN alat selama kalibrasi.")
        self.btn_calib.clicked.connect(self._calibrate_gyro)
        sec_sensor.add(self.chk_inv, 0, 0, 1, 2)
        sec_sensor.add(self.btn_calib, 0, 2, 1, 2)
        b_tare = QtWidgets.QPushButton("Nol-kan (0°)")
        b_tare.setToolTip("Jadikan posisi batang sekarang sebagai 0°.\n"
                          "Tahan batang dalam posisi datar dulu.")
        b_tare.clicked.connect(self._tare)
        b_untare = QtWidgets.QPushButton("Hapus offset")
        b_untare.clicked.connect(self._untare)
        sec_sensor.add(b_tare, 1, 0, 1, 2)
        sec_sensor.add(b_untare, 1, 2, 1, 2)
        # beban fisik: tidak dipakai di hardware (disembunyikan, tetap ada
        # karena dipakai _on_hw_load)
        self.chk_load = QtWidgets.QCheckBox("Beban fisik terpasang")
        self.chk_load.toggled.connect(self._on_hw_load)
        self.chk_load.setChecked(False)
        self.chk_load.setVisible(False)
        sec_sensor.add(self.chk_load, 2)
        adv.addWidget(sec_sensor)

        # ---------------- indikator limit switch ----------------
        # ditempatkan di bagian bawah kartu "Kontrol PID" oleh _build_panel
        # (hanya tampil di mode hardware). Limit aktif -> ESP32 mematikan PID.
        self.lim_box = QtWidgets.QWidget()
        lim_l = QtWidgets.QHBoxLayout(self.lim_box)
        lim_l.setContentsMargins(0, 4, 0, 0)
        lim_l.setSpacing(8)
        self.lbl_lim_ccw = QtWidgets.QLabel()
        self.lbl_lim_cw = QtWidgets.QLabel()
        for lb in (self.lbl_lim_cw, self.lbl_lim_ccw):     # CW kiri, CCW kanan
            lb.setAlignment(Qt.AlignCenter)
            lb.setMinimumHeight(28)
            lim_l.addWidget(lb, 1)
        tip = ("Limit switch {}. Biru = bebas, biru tua = tertekan / kabel putus,\n"
               "abu-abu = belum ada data. Saat tertekan, ESP32 mematikan PID dan motor.")
        self.lbl_lim_ccw.setToolTip(tip.format("CCW (IO32)"))
        self.lbl_lim_cw.setToolTip(tip.format("CW (IO33)"))
        self.lim_box.setVisible(False)
        self._update_limit_labels()

        # ---------------- seksi: batas motor F-max ----------------
        sec_fmax = Section("Batas motor (F-max)")
        self.fmax_unlocked = False
        self.fmax = Param("F-max", 8.0, 20.0, 15.0, 0.5, "%", 1)
        self.fmax.setToolTip("Throttle maksimum yang boleh dipakai PID (8–20 %).\n"
                             "Dikirim ke ESP32 sebagai batas keselamatan PID.\n"
                             "Tes motor manual TIDAK dibatasi F-max (0–100 %).")
        self.fmax.set_locked(True)
        self.fmax.changed.connect(self._on_fmax_changed)
        sec_fmax.add(self.fmax, 0)
        self.btn_fmax_lock = QtWidgets.QPushButton("Buka kunci F-max…")
        self.btn_fmax_lock.setToolTip("Mengubah F-max butuh konfirmasi, hanya bisa saat motor\n"
                                      "berhenti, dan terkunci lagi otomatis setelah 15 detik.")
        self.btn_fmax_lock.clicked.connect(self._toggle_fmax_lock)
        sec_fmax.add(self.btn_fmax_lock, 1)
        self.lb_authority = QtWidgets.QLabel()
        self.lb_authority.setObjectName("EventLabel")
        self.lb_authority.setWordWrap(True)
        sec_fmax.add(self.lb_authority, 2)
        self.fmax_relock = QtCore.QTimer(self)
        self.fmax_relock.setSingleShot(True)
        self.fmax_relock.setInterval(15000)
        self.fmax_relock.timeout.connect(self._lock_fmax)
        adv.addWidget(sec_fmax)

        # ---------------- seksi: tes motor manual ----------------
        sec_motor = Section("Tes motor manual")
        self.chk_motor = QtWidgets.QCheckBox("Aktifkan tes motor")
        self.chk_motor.setToolTip("Butuh firmware esp32_pid.\n"
                                  "HATI-HATI: baling-baling berputar!")
        self.chk_motor.toggled.connect(self._on_motor_enable)
        sec_motor.add(self.chk_motor, 0)
        self.sl_motor = []
        self.lb_motor = []
        self.bar_motor = []
        r = 1
        for name in ("Kiri (CW, IO26)", "Kanan (CCW, IO25)"):
            lb = QtWidgets.QLabel(f"{name}: 0 %")
            lb.setObjectName("ParamLabel")
            sl = QtWidgets.QSlider(Qt.Horizontal)
            sl.setRange(0, 1000)          # 0.1 % per langkah
            sl.setEnabled(False)
            sl.valueChanged.connect(self._on_motor_slider)
            # indikator PWM: panjang bar = throttle, teks = pulsa & duty cycle
            bar = QtWidgets.QProgressBar()
            bar.setRange(0, 1000)
            bar.setFixedHeight(16)
            bar.setAlignment(Qt.AlignCenter)
            bar.setToolTip("Sinyal PWM ke ESC (50 Hz): pulsa 1000 µs = 0 %,\n"
                           "2000 µs = 100 %. Duty = pulsa / 20 ms.")
            sec_motor.add(lb, r)
            sec_motor.add(sl, r + 1)
            sec_motor.add(bar, r + 2)
            r += 3
            self.lb_motor.append((lb, name))
            self.sl_motor.append(sl)
            self.bar_motor.append(bar)
        self.btn_motor_stop = QtWidgets.QPushButton("STOP MOTOR")
        self.btn_motor_stop.setObjectName("Danger")
        self.btn_motor_stop.setEnabled(False)
        self.btn_motor_stop.clicked.connect(self._motor_stop)
        sec_motor.add(self.btn_motor_stop, r)
        adv.addWidget(sec_motor)

        # heartbeat: firmware mematikan motor jika perintah berhenti
        self.motor_timer = QtCore.QTimer(self)
        self.motor_timer.timeout.connect(self._motor_heartbeat)
        self.motor_timer.start(100)
        self._apply_fmax(self.fmax.value())   # batasi slider motor & isi indikator PWM

        # ---------------- seksi: rekam data ----------------
        sec_rec = Section("Rekam data CSV", expanded=True)
        self.ed_label = QtWidgets.QLineEdit()
        self.ed_label.setPlaceholderText("Label percobaan, mis. step_10_pid321")
        self.btn_rec = QtWidgets.QPushButton("Rekam")
        self.btn_rec.setObjectName("Danger")
        self.btn_rec.setToolTip("Simpan SEMUA baris data ESP32 ke CSV di folder data/")
        self.btn_rec.clicked.connect(self._toggle_record)
        sec_rec.add(self.ed_label, 0, 0, 1, 3)
        sec_rec.add(self.btn_rec, 0, 3, 1, 1)
        self.rec_status = QtWidgets.QLabel()
        self.rec_status.setObjectName("EventLabel")
        self.rec_status.setWordWrap(True)
        self.rec_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        b_folder = QtWidgets.QPushButton("Buka folder data")
        b_folder.clicked.connect(self._open_data_dir)
        sec_rec.add(self.rec_status, 1, 0, 1, 3)
        sec_rec.add(b_folder, 1, 3, 1, 1)
        adv.addWidget(sec_rec)

        card.body.addWidget(self.hw_box)
        self.hw_box.setVisible(False)

        self.hw_timer = QtCore.QTimer(self)
        self.hw_timer.timeout.connect(self._update_hw_status)
        self.hw_timer.start(200)
        self._refresh_ports()
        self._update_hw_status()
        return card

    # ------------------------------------------------------------------
    # STRIP PEMBACAAN UTAMA (tingkat hierarki 1)
    # ------------------------------------------------------------------
    def _build_topstrip(self):
        """Strip tipis di bawah header: logo afiliasi + chip status alat."""
        bar = QtWidgets.QFrame()
        bar.setObjectName("TopStrip")
        lay = QtWidgets.QHBoxLayout(bar)
        lay.setContentsMargins(4, 0, 14, 0)
        lay.setSpacing(0)
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "assets", "icons", "logo_trik_ugm.jpg")
        pix = QtGui.QPixmap(logo_path)
        if not pix.isNull():
            logo = QtWidgets.QLabel()
            logo.setPixmap(pix.scaledToHeight(40, Qt.SmoothTransformation))
            logo.setContentsMargins(10, 4, 14, 4)
            logo.setToolTip("TRIK · Sekolah Vokasi UGM")
            lay.addWidget(logo, 0, Qt.AlignVCenter)
        lay.addStretch(1)
        self.status_chip = QtWidgets.QLabel("SIMULASI")
        self.status_chip.setObjectName("StatusChip")
        lay.addWidget(self.status_chip, 0, Qt.AlignVCenter)
        self._chip_state = None
        return bar

    def _build_readout(self):
        bar = QtWidgets.QFrame()
        bar.setObjectName("ReadoutBar")
        lay = QtWidgets.QHBoxLayout(bar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.ro_th = Readout("Sudut θ", "°", tooltip="Sudut batang terukur / tersimulasi")
        self.ro_sp = Readout("Setpoint", "°")
        self.ro_err = Readout("Error", "°", small=True, tooltip="e = setpoint − θ")
        self.ro_u = Readout("Keluaran u", "%", small=True, tooltip="Keluaran PID (−100 .. 100 %)")
        self.ro_f = Readout("Gaya kiri | kanan", "N", small=True, last=True,
                            tooltip="F1 (kiri) | F2 (kanan)")
        cells = (self.ro_th, self.ro_sp, self.ro_err, self.ro_u, self.ro_f)
        col_w = max(w.sizeHint().width() for w in cells)     # semua kolom selebar yang terlebar
        for i, w in enumerate(cells):
            w.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
            w.setMinimumWidth(col_w)
            lay.addWidget(w, 1)         # kolom sama lebar, isi rata kiri
            if i < len(cells) - 1:
                div = QtWidgets.QFrame()
                div.setObjectName("VDivider")
                div.setFixedWidth(1)
                lay.addWidget(div)
        return bar

    def _status(self):
        """(teks, warna) status alat untuk chip di strip pembacaan."""
        if self.mode == "sim":
            return ("SIMULASI · JEDA", AMBER) if self.paused else ("SIMULASI · BERJALAN", GREEN)
        hw = self.hw
        if not hw.is_open:
            return "HARDWARE · TIDAK TERHUBUNG", MUTED
        if not hw.receiving:
            return "HARDWARE · MENUNGGU DATA", AMBER
        if self.pid_run:
            return ("HARDWARE · PID AKTIF", ACCENT) if hw.pid_active else \
                   ("HARDWARE · PID MULAI…", AMBER)
        if self.chk_motor.isChecked() and any(v > 0 for v in self._motor_values()):
            return "HARDWARE · TES MOTOR", AMBER
        return "HARDWARE · SIAP TERBANG", GREEN

    def _update_readout(self, s):
        _t, th, _meas, sp, u, F1, F2 = s[:7]
        err = sp - th
        self.ro_th.set(f"{th:+.2f}")
        self.ro_sp.set(f"{sp:+.1f}", ACCENT)
        self.ro_err.set(f"{err:+.2f}", AMBER if abs(err) > 3.0 else None)
        self.ro_u.set(f"{u:+.1f}", RED if abs(u) >= 99.5 else None)
        self.ro_f.set(f"{F1:.2f} | {F2:.2f}")
        self._refresh_chip()

    def _refresh_chip(self):
        if not hasattr(self, "status_chip"):
            return
        text, color = self._status()
        if (text, color) != self._chip_state:
            self._chip_state = (text, color)
            self.status_chip.setText(text)
            self.status_chip.setStyleSheet(f"color:{color}; border:1px solid {color};")

    # --- F-max (batas throttle motor) ---
    def _motors_running(self):
        return self.chk_motor.isChecked() and any(v > 0 for v in self._motor_values())

    def _apply_fmax(self, v):
        """Terapkan batas F-max ke slider/indikator motor dan kirim ke ESP32."""
        v = max(8.0, min(20.0, float(v)))
        # Slider tes motor manual selalu 0..100 % (tidak ikut F-max).
        self._on_motor_slider()
        if hasattr(self, "ln_fmax"):
            self.ln_fmax.setValue(v)
        if self.hw.is_open:
            self.hw.set_fmax(v)
        bias, R, tau = self._pid_authority(v)
        txt = (f"PID: bias {bias:.1f} %, koreksi ±{R:.1f} % "
               f"→ torsi maks ≈ {tau:.3f} N·m")
        if v < 12.0:
            txt += ("\nF-max kecil: daya koreksi lemah, batang mungkin tidak "
                    "bisa terangkat dari batas mekanik. Disarankan F-max 15 %.")
        elif v > 15.0:
            txt += ("\nDi atas 15 % gaya dorong belum diukur (angka torsi "
                    "diekstrapolasi). Gain 3/2/1 dituning pada F-max 15 %: respons "
                    "bisa lebih agresif.")
        self.lb_authority.setText(txt)

    def _pid_warn_text(self):
        bias, R, tau = self._pid_authority(self.fmax.value())
        msg = "<b>Jauhkan tangan dari baling-baling!</b>"   # label QLabel -> HTML tebal
        pts = []
        if self.fmax.value() < 12.0:
            pts.append(f"F-max {self.fmax.value():.1f} % terlalu rendah "
                       f"(torsi ≈ {tau:.3f} N·m), disarankan 15 %")
        return msg, pts

    @staticmethod
    def _pid_authority(fmax):
        """Bias, rentang koreksi (%) dan torsi maksimum (N.m) PID hardware.
        Sama dengan firmware: bias = (8 + Fmax)/2, R = (Fmax - 8)/2;
        F(u) = 0.1241*u - 0.316 N (docs/pengukuran/detail_pengukuran.md, Bagian 1), L = 0.25 m."""
        bias = 0.5 * (8.0 + fmax)
        R = 0.5 * (fmax - 8.0)
        tau = 0.25 * 2 * 0.1241 * R
        return bias, R, tau

    def _on_fmax_changed(self, v):
        if self._motors_running():          # pengaman: tak boleh berubah saat motor jalan
            self._lock_fmax()
            return
        self.fmax_relock.start()            # mulai ulang hitung mundur kunci
        self._apply_fmax(v)

    def _toggle_fmax_lock(self):
        if self.fmax_unlocked:
            self._lock_fmax()
            return
        if self._motors_running():
            notify(self, "Hentikan motor dulu",
                   "Tekan STOP MOTOR sebelum mengubah F-max.", level="info")
            return
        if not confirm(
                self, "Buka kunci F-max?",
                "Batas atas throttle saat PID (8–20 %). Menaikkannya mengubah hasil tuning.",
                points=("Pastikan area baling-baling aman",
                        "Terkunci lagi otomatis setelah 15 detik"),
                level="warn", ok_text="Buka kunci"):
            return
        self.fmax_unlocked = True
        self.fmax.set_locked(False)
        self.btn_fmax_lock.setText("Kunci F-max")
        self.fmax_relock.start()

    def _lock_fmax(self):
        self.fmax_unlocked = False
        self.fmax_relock.stop()
        self.fmax.set_locked(True)
        self.btn_fmax_lock.setText("Buka kunci F-max…")

    # --- tes motor ---
    def _motor_values(self):
        return [s.value() / 10.0 for s in self.sl_motor]

    def _on_motor_slider(self, *_):
        if self.fmax_unlocked and any(v > 0 for v in self._motor_values()):
            self._lock_fmax()               # motor mulai jalan -> kunci F-max
        for (lb, name), bar, v in zip(self.lb_motor, self.bar_motor,
                                      self._motor_values()):
            lb.setText(f"{name}: {v:.1f} %")
            us = 1000.0 + 10.0 * v            # throttle % -> pulsa ESC (µs)
            duty = us / 20000.0 * 100.0       # 50 Hz -> periode 20 ms
            bar.setValue(int(round(v * 10)))
            bar.setFormat(f"PWM {us:.0f} µs  |  duty {duty:.2f} %")
        if self.chk_motor.isChecked() and self.hw.is_open:
            self.hw.set_motors(*self._motor_values())

    def _motor_stop(self):
        for s in self.sl_motor:
            s.blockSignals(True)
            s.setValue(0)
            s.blockSignals(False)
        self._on_motor_slider()
        if self.hw.is_open:
            self.hw.stop_motors()

    def _on_motor_enable(self, on):
        ok = bool(on) and self.hw.is_open
        if on and not self.hw.is_open:
            self.chk_motor.blockSignals(True)
            self.chk_motor.setChecked(False)
            self.chk_motor.blockSignals(False)
            self.hw.error = "Connect ke ESP32 dulu sebelum tes motor."
        for s in self.sl_motor:
            s.setEnabled(ok)
        self.btn_motor_stop.setEnabled(ok)
        if ok:
            self.hw.set_fmax(self.fmax.value())   # sinkronkan batas ke ESP32
        if not ok:
            self._motor_stop()

    # --- trim / feedforward ---
    def _on_trim_changed(self, v):
        self.hw.trim = float(v)
        if self.pid_run:
            self.hw.send_pid(True)

    def _trim_from_integral(self):
        if not (self.pid_run and self.hw.pid_active):
            self.hw.error = "Trim ← I hanya bisa saat PID aktif dan batang sudah tenang."
            return
        new = max(-60.0, min(60.0, self.trim.value() + self.hw.i_term))
        self.trim.set_value_silent(new)
        self.hw.trim = new
        self.hw.send_pid(True)          # kirim trim baru dulu,
        self.hw.reset_integral()        # lalu nolkan integral -> u total tetap sama

    # --- kontrol PID hardware ---
    def _toggle_pid_run(self):
        self._set_pid_run(not self.pid_run, ask=True)

    def _set_pid_run(self, on, ask=False):
        if on == self.pid_run:
            return
        if on:
            if not (self.hw.is_open and self.hw.receiving):
                self.hw.error = "Connect ke ESP32 (firmware esp32_pid) dulu."
                return
            if len(self.hw.fields() or []) < 15:
                self.hw.error = ("Data ESP32 belum berformat PID: upload firmware "
                                 "esp32_pid dulu.")
                return
            if ask:
                msg, pts = self._pid_warn_text()
                if not confirm(self, "Aktifkan PID?", msg, points=pts,
                               level="warn", ok_text="Turn on"):
                    return
            self.chk_motor.setChecked(False)          # tes manual dimatikan
            self.chk_motor.setEnabled(False)
            self._lock_fmax()
            self.btn_fmax_lock.setEnabled(False)
            self.pid_run = True
            self._pid_t0 = time.monotonic()
            self.hw.other_lines.clear()       # hanya pesan sejak PID dinyalakan
            self.btn_pid_run.setText("TURN OFF")
            self.btn_pid_run.setObjectName("HeroStop")
        else:
            self.pid_run = False
            if self.hw.is_open:
                self.hw.send_pid(False)
                self.hw.stop_motors()
            self.chk_motor.setEnabled(True)
            self.btn_fmax_lock.setEnabled(True)
            self.btn_pid_run.setText("TURN ON")
            self.btn_pid_run.setObjectName("Hero")
        self.btn_pid_run.style().unpolish(self.btn_pid_run)
        self.btn_pid_run.style().polish(self.btn_pid_run)
        self.sp.setEnabled(self.pid_run)
        self.sp.set_locked(False)       # anak widget selalu terbuka; yang mengatur setEnabled induk
        if not self.pid_run:
            self.sp.set_value_silent(0.0)
            self.hw.set_setpoint(0.0)
        self._apply_pid_lock()
        if self.pid_run:
            self.hw.set_gains(self.kp.value(), self.ki.value(), self.kd.value())
            self.hw.send_pid(True)

    def _pid_failure_reason(self):
        """Terjemahkan pesan teks ESP32 sejak PID dinyalakan menjadi alasan
        yang mudah dipahami."""
        # Pesan singkat (maks. 2 baris). Baris info firmware ("Diag:", "F-max =",
        # "Info:", "PID AKTIF", dst.) diabaikan, tidak pernah ditampilkan.
        hw = self.hw
        lines = list(hw.other_lines)

        def has(*keys):
            return any(k in l for l in lines for k in keys)

        # 1) limit switch: dari pesan ESP32 ATAU status telemetri (cadangan bila
        #    baris pesan hilang di serial). Dicek paling dulu.
        lim_msg = next((l for l in lines if "limit switch" in l), "")
        ccw = bool(re.search(r"\bCCW\b", lim_msg)) or bool(hw.limit_ccw)
        cw = bool(re.search(r"\bCW\b", lim_msg)) or bool(hw.limit_cw)
        if lim_msg or ccw or cw:
            side = "CW + CCW" if (cw and ccw) else "CW" if cw else "CCW" if ccw else ""
            return f"Limit switch {side} tertekan.\nMotor dimatikan.".replace("  ", " ")
        if has("data IMU", "I2C", "IMU tidak"):
            return "Data IMU hilang.\nCek kabel IMU."
        if has("FAILSAFE"):
            return "Koneksi GUI terputus.\nCek kabel USB."
        if has("batas mati", "batas awal"):
            return "Sudut batang terlalu besar.\nMotor dimatikan."
        if not lines:
            return "ESP32 tidak merespons.\nUpload ulang firmware esp32_pid."
        return "PID berhenti.\nMotor dimatikan."

    def _pid_failed(self):
        reason = self._pid_failure_reason()
        self._set_pid_run(False)
        # tanpa judul: cukup label BAHAYA besar + pesan singkat
        notify(self, "", reason, level="danger",
               blocking=False)          # tidak memblokir timer GUI

    def _motor_heartbeat(self):
        if self.pid_run:
            if not self.hw.receiving:                 # koneksi/data putus
                self._set_pid_run(False)
                return
            if not self.hw.pid_active and time.monotonic() - self._pid_t0 > 1.5:
                self._pid_failed()
                return
            self.hw.send_pid(True)
            return
        if not self.chk_motor.isChecked():
            return
        if not self.hw.is_open:        # koneksi putus -> reset UI ke 0
            self.chk_motor.setChecked(False)
            return
        self.hw.set_motors(*self._motor_values())

    def _refresh_ports(self):
        cur = self.cb_port.currentData()
        self.cb_port.clear()
        for dev, desc in list_ports():
            self.cb_port.addItem(desc, dev)
        if self.cb_port.count() == 0:
            self.cb_port.addItem("(tidak ada port)", None)
        i = self.cb_port.findData(cur)
        if i >= 0:
            self.cb_port.setCurrentIndex(i)

    def _toggle_connect(self):
        if self.hw.is_open:
            if self.hw.recording:
                self._toggle_record()
            self.chk_motor.setChecked(False)     # motor 0 sebelum putus
            self._set_pid_run(False)
            self.hw.disconnect()
        else:
            port = self.cb_port.currentData()
            if not port:
                self.hw.error = "Pilih port COM dulu (colok ESP32, lalu \u21bb)."
            else:
                try:
                    self.hw.connect(port)
                    self.hw.set_fmax(self.fmax.value())
                    self.reset()
                except Exception as exc:
                    self.hw.error = f"Gagal membuka {port}: {exc}"
        self._update_hw_status()

    def _on_mapping(self, *_):
        self.hw.set_invert(self.chk_inv.isChecked())
        self.hist.clear()
        self.thr_hist.clear()
        self._clear_event()

    def _calibrate_gyro(self):
        if self.hw.calibrate_gyro():
            self.hw.error = None
            # tombol dinonaktifkan selama kalibrasi berjalan di ESP32 (~2 s)
            self._calibrating = True
            self.btn_calib.setText("Kalibrasi… diamkan")
            QtCore.QTimer.singleShot(2500, self._calib_done)
        self._update_hw_status()

    def _calib_done(self):
        self._calibrating = False
        self.btn_calib.setText("Kalibrasi gyro")
        self._update_hw_status()

    def _tare(self):
        self.hw.tare()
        self.hist.clear()
        self.thr_hist.clear()
        self._clear_event()

    def _untare(self):
        self.hw.offset = 0.0
        self.hist.clear()
        self.thr_hist.clear()
        self._clear_event()

    def _on_hw_load(self, *_):
        if self.mode != "hw":
            return
        if self.chk_load.isChecked():
            self.hw.set_load(self.lm.value() / 1000.0, self.lx.value() / 100.0)
        else:
            self.hw.set_load(0.0, self.lx.value() / 100.0)

    def _toggle_record(self):
        if self.hw.recording:
            path, rows = self.hw.rec_path, self.hw.rec_rows
            self.hw.stop_recording()
            self._last_rec_msg = f"Tersimpan: {os.path.basename(path)}  ({rows} baris)"
        else:
            if not self.hw.receiving:
                self._last_rec_msg = "Belum ada data dari ESP32, rekaman tidak dimulai."
            else:
                try:
                    self.hw.start_recording(self.ed_label.text())
                    self._last_rec_msg = ""
                except OSError as exc:
                    self._last_rec_msg = f"Gagal mulai merekam: {exc}"
        self._update_hw_status()

    def _open_data_dir(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(DATA_DIR))

    def _update_limit_labels(self):
        hw = self.hw
        live = hw.is_open and hw.receiving
        # kotak di tatakan, di bawah motor (dicek di alat):
        # CCW (IO32) = kanan, CW (IO33) = kiri.
        # Tampilan dibalik ("Balik arah") -> sisi ikut tertukar.
        ccw = bool(live and hw.limit_ccw)
        cw = bool(live and hw.limit_cw)
        self.view.show_limits = self.mode == "hw"
        self.view.set_limits(*((ccw, cw) if hw.invert else (cw, ccw)))
        for lb, name, st in ((self.lbl_lim_ccw, "CCW", hw.limit_ccw),
                             (self.lbl_lim_cw, "CW", hw.limit_cw)):
            # teks hanya nama sisi; status ditunjukkan warna saja
            if not live or st is None:
                fg, bg = MUTED, "transparent"       # belum ada data
            elif st:
                fg, bg = "#FFFFFF", INK             # tertekan: biru tua (seperti Connect)
            else:
                fg, bg = "#FFFFFF", ACCENT          # tidak tertekan: biru
            lb.setText(name)
            lb.setStyleSheet(f"color: {fg}; background: {bg}; border: 1px solid {BORDER}; "
                             "border-radius: 6px; font-weight: 600;")

    def _update_hw_status(self):
        hw = self.hw
        self._update_limit_labels()
        self.btn_conn.setText("Disconnect" if hw.is_open else "Connect")
        self.btn_calib.setEnabled(hw.is_open and not self._calibrating)
        # Label status hanya untuk masalah (info normal seperti laju data,
        # baris rusak, pesan ESP32 tidak ditampilkan; status ada di chip atas).
        msgs = []
        if not HAVE_SERIAL:
            msgs.append("pyserial belum terpasang \u2192 pip install pyserial")
        elif (hw.is_open and not hw.receiving
              and time.monotonic() - getattr(hw, "opened_at", 0.0) > 2.0):
            # jeda 2 s: data pertama butuh sesaat setelah Connect, jangan
            # sampai pesan ini berkedip sebentar lalu hilang
            msgs.append(f"{hw.port} terbuka, menunggu data\u2026  (pastikan firmware "
                        "esp32_pid sudah di-upload & baud 115200; tekan EN di board "
                        "jika perlu)")
        if hw.error:
            msgs.append(hw.error)
        self.hw_status.setText("\n".join(msgs))
        self.hw_status.setVisible(bool(msgs))
        self._refresh_chip()

        # status rekam
        if hw.recording:
            self.btn_rec.setText("Stop")
            self.ed_label.setEnabled(False)
            self.rec_status.setText(
                f"MEREKAM  {hw.rec_duration:5.1f} s  \u00b7  {hw.rec_rows} baris\n"
                f"{os.path.basename(hw.rec_path)}")
            self.rec_status.setStyleSheet(f"color: {RED};")
        else:
            self.btn_rec.setText("Rekam")
            self.ed_label.setEnabled(True)
            if hw.rec_error:
                self.rec_status.setText(f"Rekaman berhenti: {hw.rec_error}")
                self.rec_status.setStyleSheet(f"color: {AMBER};")
            else:
                self.rec_status.setText(self._last_rec_msg or "Tidak merekam")
                self.rec_status.setStyleSheet("")

        # data tambahan untuk Processing
        self.stream.extra = {
            "mode": self.mode,
            "conn": int(hw.receiving) if self.mode == "hw" else 1,
            "port": hw.port or "",
            "inv": int(hw.invert),
            "off": round(hw.offset, 2),
            "rate": round(hw.rate_hz, 1),
            "rec": int(hw.recording),
            "lbl": hw.rec_label if hw.recording else "",
        } if self.mode == "hw" else {"mode": "sim"}

    def _apply_initial_mode(self, mode):
        """Pilih mode awal (dari launcher) dan, untuk hardware, port yang
        terlihat seperti ESP32 tanpa campur tangan pengguna."""
        if mode == "hw":
            i = self.cb_mode.findData("hw")
            if i >= 0:
                self.cb_mode.setCurrentIndex(i)
            for k in range(self.cb_port.count()):
                if looks_like_esp(self.cb_port.itemText(k)):
                    self.cb_port.setCurrentIndex(k)
                    break
            else:
                self.cb_port.insertItem(0, "(pilih port ESP32 \u2014 colok USB lalu \u21bb)", None)
                self.cb_port.setCurrentIndex(0)
        else:
            i = self.cb_mode.findData("sim")
            if i >= 0:
                self.cb_mode.setCurrentIndex(i)

    def set_mode(self, mode):
        if mode == self.mode:
            return
        self.chk_motor.setChecked(False)       # motor 0 saat ganti mode
        self._set_pid_run(False)
        self.stop_scenarios("Dihentikan (ganti sumber data)" if self.scn else None)
        if mode != "hw" and self.hw.recording:
            self._toggle_record()
        self.mode = mode
        hw = mode == "hw"
        # gain: hardware punya nilai awal sendiri (konservatif, Ki = 0);
        # gain simulasi disimpan & dipulihkan saat kembali ke Simulasi.
        if hw:
            self._sim_gains = (self.kp.value(), self.ti.value(), self.td.value(),
                               self.ti.is_off())
            kp, ti, td = self._to_dependen(*self.HW_GAINS)
            self._set_dependen(kp, ti, td)
        elif getattr(self, "_sim_gains", None):
            kp, ti, td, off = self._sim_gains
            self._set_dependen(kp, None if off else ti, td)
        self.be = self.hw if hw else self.sim
        self._refresh_dependen()
        self.be.set_gains(self.kp.value(), self.ki.value(), self.kd.value())
        self.hw_box.setVisible(hw)
        self.btn_pid_run.setVisible(hw)
        self.power_card.setVisible(hw)
        self.lim_box.setVisible(hw)
        # skenario otomatis hanya untuk simulasi
        if hw and self.tabs.currentIndex() == self._scn_tab_idx:
            self.tabs.setCurrentIndex(0)
        self.tabs.setTabVisible(self._scn_tab_idx, not hw)
        # skala panah gaya di tampilan 2D: alat asli ~0,7-2 N, simulasi s/d 8 N
        self.view.show_load = not hw
        self.view.update()
        # garis F-max: alat = slider F-max, simulasi = Params.Fmax
        self.ln_fmax.setValue(self.fmax.value() if hw else self.sim.p.Fmax)
        self._hw_t_prev = None
        self.hw_adv_card.setVisible(hw)
        # Mode hardware: PID, setpoint, noise, impuls & skenario tidak berlaku
        # (tahap 1: ESP32 hanya membaca IMU, motor belum dikendalikan).
        # Slider beban tetap aktif sebagai keterangan beban fisik.
        for w in (self.sp, self.nz, self.btn_disturb,
                  self.btn_scn_run, self.btn_step):
            w.setEnabled(not hw)
        # Mode hardware: slider noise, massa & posisi beban disembunyikan
        for w in (self.nz, self.lm, self.lx):
            w.setVisible(not hw)
        # Tombol uji simulasi disembunyikan di mode hardware
        for w in (self.btn_int, self.btn_disturb, self.btn_step):
            w.setVisible(not hw)
        # Gain PID mengikuti status gembok (dan terkunci paksa saat mode HW).
        self._apply_pid_lock()
        tip = ("Mode hardware (tahap 1): ESP32 hanya membaca IMU,\n"
               "motor belum dikendalikan dari GUI.") if hw else ""
        self.sp.setToolTip(tip)
        self.view.setToolTip("" if hw else
                             "Klik pada sisi kiri atau kanan batang untuk "
                             "memberi sentakan gangguan (Impuls)!")
        self.reset()
        if hw:
            self._on_hw_load()
        else:
            self._refresh_step_btn()
            self.be.set_load(self.lm.value() / 1000.0, self.lx.value() / 100.0)
        self._update_hw_status()

    def _build_shortcuts(self):
        def sc(key, fn):
            s = QtGui.QShortcut(QtGui.QKeySequence(key), self)
            s.setContext(Qt.WindowShortcut)
            s.activated.connect(fn)

        sc(Qt.Key_Space, self.toggle_pause)
        sc("D", lambda: self.trigger_impulse(2.5))
        sc("Shift+D", lambda: self.trigger_impulse(-2.5))
        sc("Ctrl+R", self.reset)
        sc("Ctrl+I", lambda: self.be.reset_integral())
        sc("Ctrl+Up", self.step_sp)
        sc("Ctrl+L", self.log_tuning)
        sc("F5", self.run_scenarios)
        sc("Esc", lambda: self.stop_scenarios("Dihentikan") if self.scn else None)

    def trigger_impulse(self, delta_w=2.5):
        """Beri gangguan impuls torsi pada batang dan catat metrik respons."""
        if self.mode == "hw":
            return               # tidak berlaku pada alat asli
        self.be.apply_impulse(delta_w)
        self._set_event("load", self.be.t)

    # ------------------------------------------------------------------
    # HANDLER INPUT
    # ------------------------------------------------------------------
    def toggle_pid_lock(self):
        """Kunci/buka gain PID. Saat terkunci slider & spinbox dinonaktifkan
        agar parameter tidak tergeser tanpa sengaja."""
        self.pid_locked = self.btn_pid_lock.isChecked()
        self._apply_pid_lock()

    def _apply_pid_lock(self):
        # Mode hardware memang sudah menonaktifkan PID; lock tetap dihormati
        # supaya saat kembali ke simulasi status kunci tidak "bocor".
        hw = self.mode == "hw"
        run = getattr(self, "pid_run", False)
        # Gembok berlaku di kedua mode: KUNCI = slider & spinbox gain
        # nonaktif (cegah tergeser tak sengaja, mis. saat PID alat aktif).
        locked = self.pid_locked
        for w in (self.kp, self.ti, self.td):
            w.set_locked(locked)
        self.btn_pid_lock.setText("KUNCI" if self.pid_locked else "BUKA")
        self.btn_pid_lock.setToolTip(
            "Gain PID terkunci \u2014 klik untuk membuka."
            if self.pid_locked else
            "Gain PID terbuka \u2014 klik untuk mengunci.")

    def _ti_text(self):
        """Ti untuk tabel: angka (s) atau ∞ bila integral dimatikan."""
        return "∞" if self.ti.is_off() else f"{self.ti.value():.2f}"

    def _set_dependen(self, kp, ti, td):
        """Isi Kp, Ti, Td tanpa memancarkan sinyal (Ti None = tanpa integral)."""
        self.kp.set_value_silent(kp)
        if ti is not None:
            self.ti.set_value_silent(ti)
        self.ti.set_off_silent(ti is None)
        self.td.set_value_silent(td)

    @staticmethod
    def _to_dependen(kp, ki, kd):
        """Gain paralel (Kp, Ki, Kd) -> bentuk dependen (Kp, Ti, Td).
        Ti = None bila Ki = 0 (tanpa integral)."""
        ti = kp / ki if ki > 1e-9 else None
        td = kd / kp if kp > 1e-9 else 0.0
        return kp, ti, td

    def _refresh_dependen(self):
        """Hitung Ki = Kp/Ti dan Kd = Kp*Td dari Kp, Ti, Td. Dibatasi seperti di
        firmware (Ki <= 3, Kd <= 1,5), supaya angka di GUI = angka yang diterima alat."""
        kp = self.kp.value()
        ki_raw = 0.0 if self.ti.is_off() else kp / max(self.ti.value(), 1e-6)
        kd_raw = kp * self.td.value()
        self.ki.set_value_silent(ki_raw)          # spinbox membatasi ke rentang 0..3
        self.kd.set_value_silent(kd_raw)          # dan 0..1,5
        ki, kd = self.ki.value(), self.kd.value()
        lim = []
        ki_max, kd_max = self.ki.sb.maximum(), self.kd.sb.maximum()    # batas firmware 3,00 / 1,50
        if ki_raw > ki_max + 1e-9:
            lim.append(f"Ki dibatasi {ki_max:.2f} (hitungan {ki_raw:.2f}, maks firmware)")
        if kd_raw > kd_max + 1e-9:
            lim.append(f"Kd dibatasi {kd_max:.2f} (hitungan {kd_raw:.2f}, maks firmware)")
        self.box_ki.set(f"{ki:.2f}", ki_raw > ki_max + 1e-9)
        self.box_kd.set(f"{kd:.2f}", kd_raw > kd_max + 1e-9)
        self.lb_dep.setText("\n".join(lim))
        self.lb_dep.setStyleSheet(f"color:{AMBER};" if lim else "")
        self.lb_dep.setVisible(bool(lim))

    def on_gains(self, _=None):
        self._refresh_dependen()
        self.be.set_gains(self.kp.value(), self.ki.value(), self.kd.value())

    def _start_pending(self, kind):
        if self.pend is None or self.pend["kind"] != kind:
            self.pend = dict(kind=kind, t0=self.be.t)
        self.debounce.start(350)

    def on_sp(self, v):
        if self.scn:
            self.stop_scenarios("Dihentikan (setpoint diubah manual)")
        self._start_pending("sp")
        self.be.set_setpoint(v)
        self._refresh_step_btn()

    def on_load(self, _=None):
        if self.scn:
            self.stop_scenarios("Dihentikan (beban diubah manual)")
        self._start_pending("load")
        if self.mode == "hw":
            self._on_hw_load()      # hanya keterangan beban fisik
            return
        self.be.set_load(self.lm.value() / 1000.0, self.lx.value() / 100.0)

    def _commit_event(self):
        if self.pend:
            self._set_event(self.pend["kind"], self.pend["t0"])
            self.pend = None

    def _set_event(self, kind, t0):
        """Mulai event baru: data sejak t0 diambil dari buffer grafik, lalu
        terus ditambah di tick() ke buffer event (tidak terbuang)."""
        self.event = (kind, t0)
        self.ev_buf = [s for s in self.hist if s[COL_T] >= t0 - 1e-9]
        self._last_metrics = None
        for line in self.event_markers:
            line.setPos(t0)
            line.setVisible(True)

    def _clear_event(self):
        self.event = None
        self.pend = None
        self.debounce.stop()
        self.ev_buf = []
        self._last_metrics = None
        self.band.setVisible(False)
        for line in self.event_markers:
            line.setVisible(False)
        self.mt_event.setText("Menunggu perubahan setpoint / beban")
        for m in self.metric_w.values():
            m.set(DASH)

    def _refresh_step_btn(self):
        self.btn_step.setEnabled(self.mode != "hw" and
                                 self.sp.value() < SP_LIMIT - 1e-9)

    def step_sp(self):
        if self.btn_step.isEnabled():
            self.sp.set_value(min(SP_LIMIT, self.sp.value() + SP_STEP))

    def toggle_pause(self):
        self.paused = not self.paused
        self._t_last = None
        self.btn_pause.setText("Continue" if self.paused else "Pause")

    def reset(self):
        self.stop_scenarios("Dihentikan (reset)" if self.scn else None)
        self.be.reset()
        if self.mode == "hw":
            # beban fisik tetap seperti yang diisi pengguna
            self._on_hw_load()
        else:
            # kembalikan input ke default tanpa memicu event
            for prm in (self.sp, self.lm, self.lx):
                prm.set_value_silent(prm.default)
            self.be.set_setpoint(self.sp.value())
            self.be.set_load(self.lm.value() / 1000.0, self.lx.value() / 100.0)
        self.hist.clear()
        self.thr_hist.clear()
        self._clear_event()
        self.prop1_rot = self.prop2_rot = 0.0
        self.frame = 0
        self._acc = 0.0
        self._t_last = None
        self.paused = False
        self.btn_pause.setText("Pause")
        self._refresh_step_btn()

    # ------------------------------------------------------------------
    # LOOP UTAMA
    # ------------------------------------------------------------------
    def _prop_rate(self, thrust):
        """Kecepatan putar propeller (deg/s): idle + proporsional thrust."""
        return self.PROP_IDLE_DPS + max(0.0, thrust) * self.PROP_GAIN_DPS

    def _throttles(self, s):
        """Throttle kiri/kanan (%) untuk grafik. Hardware: nilai yang
        dilaporkan ESP32. Simulasi: throttle model (hukum kontrol sama)."""
        if self.mode == "hw":
            f = self.hw.fields()
            if f and len(f) >= 15:
                return (f[10], f[11])
            return (0.0, 0.0)
        return (self.sim.thr_l, self.sim.thr_r)

    def _hw_prop_rates(self):
        """Kecepatan putar visual baling-baling mode hardware (deg/s) dari
        throttle kiri/kanan yang dilaporkan ESP32. Motor mati -> diam.
        Skala dipilih agar di bias ~11,5 % kecepatannya mirip mode simulasi."""
        f = self.hw.fields()
        if not f or len(f) < 15:
            return 0.0, 0.0
        return tuple(0.0 if thr < 0.5 else self.PROP_IDLE_DPS + 90.0 * thr
                     for thr in (f[10], f[11]))

    def _steps_due(self):
        """Jumlah langkah simulasi berdasarkan waktu nyata (perf_counter),
        supaya simulasi tetap real-time walau QTimer meleset."""
        now = time.perf_counter()
        if self._t_last is None:
            elapsed = self.TICK_MS / 1000.0
        else:
            elapsed = min(now - self._t_last, self.MAX_CATCHUP_S)
        self._t_last = now
        self._acc += elapsed
        n = int(self._acc / self.be.p.dt)
        self._acc -= n * self.be.p.dt
        return n

    def tick(self):
        self._update_connection_status()
        if self.paused:
            self.stream.heartbeat()
            return

        if self.mode == "hw":
            # data mengikuti IMU asli; baling-baling berputar sesuai throttle
            # motor yang dilaporkan ESP32 (PID atau tes motor manual)
            s = self.be.poll()
            if s is None:
                self.stream.heartbeat()
                return
            if "conn" in self.stream.extra:
                self.stream.extra["conn"] = 1
            prev = getattr(self, "_hw_t_prev", None)
            dtg = 0.0 if prev is None else min(0.1, max(0.0, s[0] - prev))
            self._hw_t_prev = s[0]
        else:
            n = self._steps_due()
            if n == 0:
                # QTimer meleset ke bawah -> jaga status koneksi Processing
                # tetap akurat walau belum ada langkah simulasi baru.
                self.stream.heartbeat()
                return
            for _ in range(n):
                self.be.step()
            s = self.be.sample()
            dtg = n * self.be.p.dt
        self.hist.append(s)
        self.thr_hist.append(self._throttles(s))
        if self.event is not None and len(self.ev_buf) < self.ev_max:
            self.ev_buf.append(s)
        t, th, _meas, sp, _u, F1, F2 = s[:7]

        if self.mode == "sim":
            r1, r2 = (self.PROP_IDLE_DPS + 90.0 * thr
                      for thr in (self.sim.thr_l, self.sim.thr_r))
        else:
            r1, r2 = self._hw_prop_rates()
        self.prop1_rot = (self.prop1_rot + r1 * dtg) % self.PROP_WRAP
        self.prop2_rot = (self.prop2_rot + r2 * dtg) % self.PROP_WRAP
        self.stream.send(th, self.prop1_rot, self.prop2_rot, sp, _u, self.be.load_m, self.be.load_x, F1, F2)

        self.view.set_state(th, sp, F1, F2, self.be.load_m, self.be.load_x,
                            self.prop1_rot, self.prop2_rot)

        self._scenario_tick()

        self.frame += 1
        if self.frame % 2:
            return

        a = np.asarray(self.hist)
        m = a[:, COL_T] > t - self.WINDOW_S
        x = a[m, COL_T]
        self._update_readout(s)
        self.c_th.setData(x, a[m, COL_TH])
        self.c_meas.setData(x, a[m, COL_MEAS])
        self.c_sp.setData(x, a[m, COL_SP])
        self.c_pt.setData(x, a[m, COL_P])
        self.c_it.setData(x, a[m, COL_I])
        self.c_dt.setData(x, a[m, COL_D])
        self.c_ut.setData(x, a[m, COL_U])
        self.c_err.setData(x, a[m, COL_SP] - a[m, COL_TH])
        self.c_omega.setData(x, a[m, COL_W])
        th_arr = np.asarray(self.thr_hist)
        if len(th_arr) == len(a):
            self.c_thr1.setData(x, th_arr[m, 0])
            self.c_thr2.setData(x, th_arr[m, 1])
        self.p1.setXRange(t - self.WINDOW_S, t, padding=0)

        peak = float(np.max(np.abs(a[m][:, [COL_TH, COL_MEAS, COL_SP]])))
        self._set_angle_range(peak)
        self.update_metrics()

    def _set_angle_range(self, peak):
        """Sumbu Y sudut otomatis (kelipatan 5 deg, min +-25, maks +-50)
        supaya kurva tidak hilang saat batang menyentuh batas +-33 deg."""
        lim = min(50.0, max(25.0, math.ceil((peak + 3.0) / 5.0) * 5.0))
        if lim != self._ylim:
            self._ylim = lim
            self.p1.setYRange(-lim, lim, padding=0)

    CONN_LABEL = {
        "connected": ("PROCESSING  \u00b7  connected", GREEN),
        "no-ack": ("PROCESSING  \u00b7  no ACK", AMBER),
        "no-listener": ("PROCESSING  \u00b7  no listener", RED),
        "idle": ("PROCESSING  \u00b7  connecting\u2026", MUTED),
    }

    def open_3d_viewer(self):
        """Jalankan viewer 3D Processing dari tombol header.

        ``start_processing`` bisa makan beberapa detik (PowerShell untuk
        membersihkan viewer zombie, menunggu port lepas), jadi dijalankan
        di thread terpisah supaya GUI tidak membeku. Hasilnya kembali ke
        thread GUI lewat signal ``_open3d_done``.
        """
        if self.stream.healthy:
            # viewer sudah terhubung -> jangan probe/bunuh apa pun
            self._set_open3d_active()
            return
        self.btn_open3d.setEnabled(False)
        self.btn_open3d.setText("Memeriksa\u2026")

        def work():
            try:
                ok, msg = start_processing(editor_only=False, wait=False)
            except Exception as exc:          # jaga-jaga: tombol jangan macet
                ok, msg = False, f"Gagal membuka Processing: {exc}"
            self._open3d_done.emit(ok, msg)

        threading.Thread(target=work, name="open3d", daemon=True).start()

    def _set_open3d_active(self):
        self.btn_open3d.setEnabled(False)
        self.btn_open3d.setText("3D aktif")
        self.btn_open3d.setToolTip("Viewer 3D Processing sedang terhubung.")
        self._open3d_waits = 0

    @QtCore.Slot(bool, str)
    def _on_open3d_done(self, ok, msg):
        self.btn_open3d.setToolTip(msg)
        if ok:
            self._open3d_waits = 40     # poll s/d ~40 s (kompilasi bisa lama)
            self.btn_open3d.setEnabled(False)
            self.btn_open3d.setText("3D dimulai\u2026")
            QtCore.QTimer.singleShot(1000, self._poll_open3d)
        else:
            self.btn_open3d.setEnabled(True)
            self.btn_open3d.setText("Buka viewer 3D")
            notify(self, "Tidak bisa membuka 3D", msg, level="warn")

    def _poll_open3d(self):
        """Tunggu ACK dari viewer 3D; baru aktifkan lagi tombol bila gagal."""
        if self.stream.healthy:
            self._set_open3d_active()
            return
        self._open3d_waits -= 1
        if self._open3d_waits > 0:
            QtCore.QTimer.singleShot(1000, self._poll_open3d)
        else:
            self.btn_open3d.setEnabled(True)
            self.btn_open3d.setText("Buka viewer 3D")
            self.btn_open3d.setToolTip(
                "Viewer 3D belum merespons. Klik lagi untuk mencoba ulang.")

    def _update_connection_status(self):
        state = self.stream.status
        if state == self._conn_state:
            return
        self._conn_state = state
        text, color = self.CONN_LABEL[state]
        self.pill_dot.setStyleSheet(f"color: {color}; font-size: 12px;")
        self.pill_txt.setText(text)
        # Viewer 3D putus -> aktifkan lagi tombol buka, supaya bisa
        # dijalankan ulang tanpa restart aplikasi.
        if state != "connected" and not self.btn_open3d.isEnabled() \
                and self.btn_open3d.text() == "3D aktif":
            self.btn_open3d.setEnabled(True)
            self.btn_open3d.setText("Buka viewer 3D")

    # ------------------------------------------------------------------
    # METRIK
    # ------------------------------------------------------------------
    def _compute_current_metrics(self):
        if self.event is None or len(self.ev_buf) < 5:
            return None
        kind, t0 = self.event
        return compute_metrics(np.asarray(self.ev_buf), kind, t0, SETTLING_CRIT)

    def update_metrics(self):
        if self.event is None:
            return
        res = self._compute_current_metrics()
        if res is None:
            return
        kind, t0 = self.event
        sp_f, band = res["sp_final"], res["band"]
        self.band.setRegion((sp_f - band, sp_f + band))
        self.band.setVisible(True)

        jenis = "Setpoint step" if kind == "sp" else "Load disturbance"
        note = ""
        if len(self.ev_buf) >= self.ev_max:
            note = f"  \u00b7  (data dibatasi {self.EVENT_MAX_S:.0f} s)"
        self.mt_event.setText(f"{jenis}  \u00b7  t = {t0:.1f} s  \u00b7  "
                              f"band \u00b1{band:.2f}\u00b0{note}")
        for key, w in self.metric_w.items():
            w.set(res[key])
        self._last_metrics = res

    # ------------------------------------------------------------------
    # RIWAYAT TUNING
    # ------------------------------------------------------------------
    def log_tuning(self):
        m = self._last_metrics or {k: DASH for k in METRIC_KEYS}
        if self.event is None:
            ev = DASH
        else:
            ev = "Step setpoint" if self.event[0] == "sp" else "Gangguan beban"
        self._append_row(self.tuning_table, [
            f"{self.be.t:.1f} s", f"{self.kp.value():.2f}", self._ti_text(),
            f"{self.td.value():.2f}", f"{self.ki.value():.2f}", f"{self.kd.value():.2f}",
            ev, m["overshoot"], m["rise"], m["settling"], m["error"]])
        self.tabs.setCurrentIndex(3)

    # ------------------------------------------------------------------
    # SKENARIO UJI OTOMATIS (berbasis waktu simulasi)
    # ------------------------------------------------------------------
    def run_scenarios(self):
        if self.scn or self.mode == "hw":
            return
        self.scenario_table.setRowCount(0)
        self.scn_queue = list(SCENARIOS)
        self.scn_total = len(self.scn_queue)
        self.btn_scn_run.setEnabled(False)
        self.btn_scn_stop.setEnabled(True)
        if self.paused:
            self.toggle_pause()
        self.tabs.setCurrentIndex(4)
        self._start_next_scenario()

    def stop_scenarios(self, msg=None):
        self.scn = None
        self.scn_queue = []
        self.btn_scn_run.setEnabled(True)
        self.btn_scn_stop.setEnabled(False)
        if msg:
            self.scenario_status.setText(msg)

    def _apply_input(self, sp=None, load=None):
        """Set setpoint/beban ke backend + slider tanpa memicu event manual."""
        if sp is not None:
            self.sp.set_value_silent(sp)
            self.be.set_setpoint(sp)
            self._refresh_step_btn()
        if load is not None:
            mass, pos = load
            self.lm.set_value_silent(mass * 1000.0)
            self.lx.set_value_silent(pos * 100.0)
            self.be.set_load(mass, pos)

    def _start_next_scenario(self):
        if not self.scn_queue:
            self.stop_scenarios(f"Selesai  \u00b7  {self.scn_total} skenario tercatat")
            return
        name, init, change = self.scn_queue.pop(0)
        idx = self.scn_total - len(self.scn_queue)

        # kondisi awal identik untuk tiap skenario
        self._clear_event()
        self.be.reset(keep_time=True)
        sp0 = init.get("sp", 0.0)
        self._apply_input(sp=sp0, load=init.get("load", (0.0, self.lx.default / 100.0)))
        self.be.th = math.radians(sp0)
        self.be.meas = self.be.prev_meas = sp0   # hindari derivative kick

        self.scn = dict(name=name, idx=idx, change=change, phase="settle",
                        t_end=self.be.t + SCN_SETTLE_S)
        self._scenario_status()

    def _scenario_status(self):
        s = self.scn
        phase = "settle" if s["phase"] == "settle" else "mengukur"
        left = max(0.0, s["t_end"] - self.be.t)
        self.scenario_status.setText(
            f"Skenario {s['idx']}/{self.scn_total}: {s['name']}  \u00b7  "
            f"{phase} ({left:.1f} s)")

    def _scenario_tick(self):
        s = self.scn
        if s is None:
            return
        if self.frame % 10 == 0:
            self._scenario_status()
        if self.be.t < s["t_end"]:
            return

        if s["phase"] == "settle":
            kind, value = s["change"]
            t0 = self.be.t
            if kind == "sp":
                self._apply_input(sp=value)
            else:
                self._apply_input(load=value)
            self._set_event(kind, t0)
            s["phase"] = "measure"
            s["t_end"] = t0 + SCN_MEASURE_S
            self._scenario_status()
            return

        # fase ukur selesai -> catat metrik dari buffer event
        res = self._compute_current_metrics() or {k: DASH for k in METRIC_KEYS}
        gains = f"{self.kp.value():.2f} / {self._ti_text()} / {self.td.value():.2f}"
        self._append_row(self.scenario_table, [
            s["name"], gains, res["overshoot"], res["rise"], res["peak_time"],
            res["settling"], res["error"], res["deviation"]])
        self._start_next_scenario()
