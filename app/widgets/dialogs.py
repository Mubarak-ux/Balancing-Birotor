"""Dialog konfirmasi / pemberitahuan bergaya panel instrumen (pengganti QMessageBox)."""

from PySide6 import QtCore, QtWidgets

from ..config import (ACCENT, AMBER, BORDER, CARD, CARD_ALT, INK, MUTED, RED,
                      SUB_FONT, TITLE_FONT)

Qt = QtCore.Qt

# tingkat -> (warna, label kecil)
_LEVELS = {
    "info": (ACCENT, "INFO"),
    "warn": (AMBER, "PERINGATAN"),
    "danger": (RED, "BAHAYA"),
}


class NoticeDialog(QtWidgets.QDialog):
    def __init__(self, parent, level, title, message, points=(),
                 ok_text="OK", cancel_text=None):
        super().__init__(parent)
        color, tag = _LEVELS.get(level, _LEVELS["info"])
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setModal(True)
        self.setMinimumWidth(380)
        self.setMaximumWidth(460)
        self.setObjectName("Notice")
        self.setStyleSheet(f"""
            QDialog#Notice {{ background: {CARD}; border: 2px solid {INK}; }}
            QLabel {{ font-family: {SUB_FONT}; }}
            QLabel#Tag {{ color: {color}; font-size: 10px; font-weight: 700; }}
            QLabel#Title {{ color: {INK}; font-family: {TITLE_FONT};
                            font-size: 17px; font-weight: 700; }}
            QLabel#Msg {{ color: {INK}; font-size: 12px; }}
            QLabel#Point {{ color: {MUTED}; font-size: 11px; }}
            QFrame#Foot {{ background: {CARD_ALT}; border-top: 1px solid {BORDER}; }}
            QPushButton {{ font-family: {SUB_FONT}; }}
            QPushButton#Ok {{ background: {color}; border: 1px solid {color};
                              color: #FFFFFF; font-weight: 700; padding: 7px 16px; }}
            QPushButton#Ok:hover {{ background: {INK}; border-color: {INK}; }}
            QPushButton#Cancel {{ background: {CARD}; border: 1px solid {BORDER};
                                  color: {INK}; font-weight: 600; padding: 7px 16px; }}
            QPushButton#Cancel:hover {{ border-color: {INK}; }}
        """)

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)     # sisakan ruang untuk stroke
        root.setSpacing(0)

        col = QtWidgets.QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        root.addLayout(col, 1)

        body = QtWidgets.QVBoxLayout()
        body.setContentsMargins(20, 18, 20, 16)
        body.setSpacing(6)
        col.addLayout(body)

        lbl_tag = QtWidgets.QLabel(tag)
        lbl_tag.setObjectName("Tag")
        lbl_title = QtWidgets.QLabel(title)
        lbl_title.setObjectName("Title")
        lbl_title.setWordWrap(True)
        body.addWidget(lbl_tag)
        body.addWidget(lbl_title)

        if message:
            lbl_msg = QtWidgets.QLabel(message)
            lbl_msg.setObjectName("Msg")
            lbl_msg.setWordWrap(True)
            body.addSpacing(2)
            body.addWidget(lbl_msg)
        for p in points:
            lbl = QtWidgets.QLabel(f"•  {p}")
            lbl.setObjectName("Point")
            lbl.setWordWrap(True)
            body.addWidget(lbl)

        foot = QtWidgets.QFrame()
        foot.setObjectName("Foot")
        fl = QtWidgets.QHBoxLayout(foot)
        fl.setContentsMargins(20, 10, 20, 10)
        fl.setSpacing(8)
        fl.addStretch(1)
        if cancel_text:
            b_cancel = QtWidgets.QPushButton(cancel_text)
            b_cancel.setObjectName("Cancel")
            b_cancel.setCursor(Qt.PointingHandCursor)
            b_cancel.clicked.connect(self.reject)
            fl.addWidget(b_cancel)
        b_ok = QtWidgets.QPushButton(ok_text)
        b_ok.setObjectName("Ok")
        b_ok.setCursor(Qt.PointingHandCursor)
        b_ok.clicked.connect(self.accept)
        fl.addWidget(b_ok)
        col.addWidget(foot)

        # default = tombol aman (Batal) bila ada; Esc selalu menolak
        (b_cancel if cancel_text else b_ok).setDefault(True)
        (b_cancel if cancel_text else b_ok).setFocus()


def confirm(parent, title, message="", points=(), level="warn",
            ok_text="Lanjutkan", cancel_text="Batal"):
    """True bila pengguna menekan tombol OK. Default fokus = Batal."""
    return NoticeDialog(parent, level, title, message, points,
                        ok_text, cancel_text).exec() == QtWidgets.QDialog.Accepted


def notify(parent, title, message="", points=(), level="info", ok_text="OK",
           blocking=True):
    dlg = NoticeDialog(parent, level, title, message, points, ok_text)
    if blocking:
        dlg.exec()
    else:
        dlg.setAttribute(Qt.WA_DeleteOnClose)
        dlg.open()
