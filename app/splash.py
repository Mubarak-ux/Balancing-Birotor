"""Loading screen: tampilan GUI yang diburamkan + progres pemuatan."""

import os
import time

from PySide6 import QtCore, QtGui, QtWidgets

from .config import ACCENT, BORDER, INK, MUTED, SUB_FONT, TITLE_FONT

Qt = QtCore.Qt
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def _family(css_list):
    return css_list.split(",")[0].strip().strip("'\"")


class SplashScreen(QtWidgets.QWidget):
    W, H = 760, 440

    def __init__(self):
        super().__init__(None, Qt.SplashScreen | Qt.FramelessWindowHint
                         | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setFixedSize(self.W, self.H)
        self._bg = QtGui.QPixmap(os.path.join(ASSETS, "images", "splash_bg.jpg"))
        self._icon = QtGui.QPixmap(os.path.join(ASSETS, "icons", "samping_icon.png"))
        self._shown = 0.0           # progres yang digambar (0..1), mengejar target
        self._target = 0.0
        self._text = "Memulai…"
        self._t0 = time.monotonic()
        self._timer = QtCore.QTimer(self, interval=16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        scr = QtGui.QGuiApplication.primaryScreen().availableGeometry()
        self.move(scr.center() - self.rect().center())

    # --- API ---
    def step(self, value, text):
        """Naikkan target progres (0..1) dan ganti teks status."""
        self._target = max(self._target, value)
        self._text = text
        self._pump()

    def finish(self, window):
        """Selesaikan bar, tampilkan jendela utama, lalu pudarkan splash."""
        self.step(1.0, "Siap")
        t_end = time.monotonic() + 0.5
        while (self._shown < 0.995 or time.monotonic() < t_end):
            self._pump()
            time.sleep(0.008)
        window.show_fitted()
        self._fade = QtCore.QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(260)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self.close)
        self._fade.start()

    # --- internal ---
    def _pump(self):
        self._tick()
        QtWidgets.QApplication.processEvents()

    def _tick(self):
        d = self._target - self._shown
        self._shown += d * 0.12 if abs(d) > 0.002 else d
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        W, H = self.W, self.H

        # latar: tampilan GUI buram (cover) + selubung putih
        if not self._bg.isNull():
            s = self._bg.scaled(W, H, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.drawPixmap(0, 0, s, (s.width() - W) // 2, (s.height() - H) // 2, W, H)
        else:
            p.fillRect(self.rect(), QtGui.QColor("#F2F6FB"))
        p.fillRect(self.rect(), QtGui.QColor(255, 255, 255, 150))

        # panel tengah
        pw, ph = 460, 230
        px, py = (W - pw) // 2, (H - ph) // 2 - 6
        p.setPen(QtGui.QPen(QtGui.QColor(INK), 1.5))
        p.setBrush(QtGui.QColor(255, 255, 255, 240))
        p.drawRect(px, py, pw, ph)

        # ikon (samping.png)
        isz = 112
        ix, iy = px + 28, py + 28
        p.drawPixmap(QtCore.QRect(ix, iy, isz, isz), self._icon)
        p.setBrush(Qt.NoBrush)
        p.setPen(QtGui.QPen(QtGui.QColor(INK), 1))
        p.drawRect(ix, iy, isz, isz)

        # judul & sub judul
        tx = ix + isz + 26
        f = QtGui.QFont(_family(TITLE_FONT), 30)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QtGui.QColor(INK))
        p.drawText(QtCore.QRect(tx, iy - 4, pw - (tx - px) - 20, 48), Qt.AlignLeft | Qt.AlignVCenter, "GUI BP")
        f2 = QtGui.QFont(_family(SUB_FONT), 10)
        p.setFont(f2)
        p.setPen(QtGui.QColor(MUTED))
        p.drawText(QtCore.QRect(tx, iy + 46, pw - (tx - px) - 20, 22), Qt.AlignLeft | Qt.AlignVCenter,
                   "Balancing Propeller")
        p.drawText(QtCore.QRect(tx, iy + 68, pw - (tx - px) - 20, 22), Qt.AlignLeft | Qt.AlignVCenter,
                   "Praktikum Sistem Kontrol Dasar")

        # status + persen
        f3 = QtGui.QFont(_family(SUB_FONT), 9)
        p.setFont(f3)
        p.setPen(QtGui.QColor(INK))
        by = py + ph - 58
        p.drawText(QtCore.QRect(px + 28, by, pw - 120, 20), Qt.AlignLeft | Qt.AlignVCenter, self._text)
        fb = QtGui.QFont(_family(TITLE_FONT), 9)
        fb.setBold(True)
        p.setFont(fb)
        p.drawText(QtCore.QRect(px + pw - 28 - 60, by, 60, 20), Qt.AlignRight | Qt.AlignVCenter,
                   f"{int(self._shown * 100)}%")

        # bar progres
        bx, bw, bh, byy = px + 28, pw - 56, 5, by + 26
        p.setPen(Qt.NoPen)
        p.setBrush(QtGui.QColor(BORDER))
        p.drawRect(bx, byy, bw, bh)
        p.setBrush(QtGui.QColor(ACCENT))
        p.drawRect(bx, byy, int(bw * min(1.0, self._shown)), bh)
        # kilau berjalan di ujung bar
        sh = int(bw * min(1.0, self._shown))
        if 0 < sh < bw:
            ph_ = (time.monotonic() - self._t0) * 1.4 % 1.0
            gx = bx + int(sh * ph_)
            g = QtGui.QLinearGradient(gx - 40, 0, gx + 40, 0)
            g.setColorAt(0, QtGui.QColor(255, 255, 255, 0))
            g.setColorAt(0.5, QtGui.QColor(255, 255, 255, 120))
            g.setColorAt(1, QtGui.QColor(255, 255, 255, 0))
            p.setBrush(g)
            p.drawRect(bx, byy, sh, bh)

        # bingkai luar
        p.setBrush(Qt.NoBrush)
        p.setPen(QtGui.QPen(QtGui.QColor(INK), 2))
        p.drawRect(1, 1, W - 2, H - 2)
