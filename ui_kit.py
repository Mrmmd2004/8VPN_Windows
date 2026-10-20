"""Small widget kit that gives the Windows app the same look as the Android one."""
import math
import os

from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QLayout, QPushButton, QVBoxLayout,
                             QWidget)

import core
from core import S
from i18n import tr

PAL = {
    "dark": dict(bg="#0D101E", card="#161A2C", card2="#222640", text="#E4E6F4", sub="#A9ADC6", border="#252A44",
                 line="#4D5273", primary="#8EB1FF", onp="#00205C", sel="#443F5E", amber="#FFB84D", danger="#FF8A8A",
                 sheet="#1E2238"),
    "light": dict(bg="#F5F6FC", card="#FFFFFF", card2="#E9ECF8", text="#161A2C", sub="#565B78", border="#DCE0F0",
                  line="#A5AAC6", primary="#2F5FD0", onp="#FFFFFF", sel="#DCE0F6", amber="#B87400", danger="#C62828",
                  sheet="#FFFFFF"),
}


def pal():
    return PAL.get(S.theme, PAL["dark"])


def L(key, **kw):
    return tr(S.language, key, **kw)


def rtl():
    return S.language == "fa"


def qss():
    p = pal()
    return f"""
    * {{ font-family: 'Segoe UI', Tahoma, sans-serif; font-size: 13px; color: {p['text']}; }}
    QWidget {{ background: transparent; }}
    QLabel:disabled {{ color: {p['sub']}; }}
    QLabel#sub {{ color: {p['sub']}; }}
    QLabel#hint {{ color: {p['sub']}; font-size: 12px; }}
    QLabel#err {{ color: {p['danger']}; font-size: 12px; }}
    QLabel#gtitle {{ color: {p['primary']}; font-weight: 700; font-size: 13px; }}
    QLabel#page {{ font-size: 21px; }}
    QFrame#card {{ background: {p['card']}; border: 1px solid {p['border']}; border-radius: 22px; }}
    QFrame#segBox {{ border: 1px solid {p['line']}; border-radius: 22px; }}
    QFrame#banner {{ background: {p['card2']}; border-radius: 14px; }}
    QPushButton {{ border: none; background: transparent; }}
    QPushButton#link {{ color: {p['primary']}; font-weight: 600; font-size: 14px; padding: 6px 10px; border-radius: 10px; }}
    QPushButton#link:hover {{ background: {p['card2']}; }}
    QPushButton#linkDanger {{ color: {p['danger']}; font-weight: 600; padding: 6px 10px; border-radius: 10px; }}
    QPushButton#seg {{ border-radius: 20px; padding: 10px 0; font-weight: 600; }}
    QPushButton#seg[on="true"] {{ background: {p['sel']}; }}
    QPushButton#seg:disabled {{ color: {p['sub']}; }}
    QPushButton#chip {{ border: 1px solid {p['line']}; border-radius: 16px; padding: 7px 16px; }}
    QPushButton#chip[on="true"] {{ background: {p['sel']}; border-color: {p['sel']}; font-weight: 600; }}
    QPushButton#chip:disabled {{ color: {p['sub']}; }}
    QPushButton#pill {{ border: 1px solid {p['line']}; border-radius: 22px; padding: 11px 22px; color: {p['primary']}; font-weight: 600; }}
    QPushButton#pill:hover {{ background: {p['card2']}; }}
    QPushButton#pill:disabled {{ color: {p['sub']}; }}
    QPushButton#row {{ background: {p['card2']}; border-radius: 16px; padding: 14px 16px; text-align: left; }}
    QPushButton#row:disabled {{ color: {p['sub']}; }}
    QPushButton#action {{ background: {p['card2']}; border-radius: 16px; padding: 13px 16px; text-align: left; }}
    QPushButton#action:hover {{ background: {p['sel']}; }}
    QPushButton#action:disabled {{ color: {p['sub']}; }}
    QPushButton#mono {{ padding: 2px 4px; text-align: left; font-family: Consolas, monospace; font-size: 12px; color: {p['sub']}; }}
    QPushButton#primary {{ background: {p['primary']}; color: {p['onp']}; border-radius: 20px; padding: 10px 22px; font-weight: 700; }}
    QLineEdit, QSpinBox {{ background: transparent; border: 1px solid {p['line']}; border-radius: 14px; padding: 9px 12px;
        selection-background-color: {p['primary']}; selection-color: {p['onp']}; }}
    QLineEdit:focus, QSpinBox:focus {{ border: 1px solid {p['primary']}; }}
    QLineEdit[bad="true"] {{ border: 1px solid {p['danger']}; }}
    QLineEdit:disabled, QSpinBox:disabled {{ color: {p['sub']}; }}
    QPlainTextEdit {{ background: {p['card']}; border: 1px solid {p['border']}; border-radius: 16px; padding: 8px;
        font-family: Consolas, monospace; font-size: 12px; }}
    QListWidget {{ background: transparent; border: none; outline: none; }}
    QListWidget::item {{ padding: 8px 6px; border-radius: 12px; }}
    QListWidget::item:hover {{ background: {p['card2']}; }}
    QListWidget::item:selected {{ background: {p['sel']}; color: {p['text']}; }}
    QScrollArea {{ border: none; }}
    QScrollBar:vertical {{ width: 8px; background: transparent; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {p['line']}; border-radius: 4px; min-height: 36px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QScrollBar:horizontal {{ height: 0; }}
    QMenu {{ background: {p['card']}; border: 1px solid {p['border']}; padding: 4px; }}
    QMenu::item {{ padding: 7px 22px; border-radius: 6px; }}
    QMenu::item:selected {{ background: {p['card2']}; }}
    """


def fmt_rate(b: float) -> str:
    if b < 0:
        return "—"
    if b >= 1048576:
        return f"{b / 1048576:.1f} MB/s"
    if b >= 1024:
        return f"{b / 1024:.0f} KB/s"
    return f"{b:.0f} B/s"


# ------------------------------------------------------------ flags
_flag_cache = {}


def flag_pixmap(cc: str, width: int = 36) -> QPixmap:
    key = (cc.lower() or "auto", width)
    if key not in _flag_cache:
        name = "auto" if not cc else cc.upper()
        pm = QPixmap(core.resource("assets", "flags", f"{name}.png"))
        if not pm.isNull():
            pm = pm.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)
        _flag_cache[key] = pm
    return _flag_cache[key]


# ------------------------------------------------------------ icons
def paint_icon(p: QPainter, kind: str, r: QRectF, color: QColor, w: float = 2.0):
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(color, w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    cx, cy, s = r.center().x(), r.center().y(), min(r.width(), r.height()) / 2
    P = QPointF
    if kind == "back":
        p.drawLine(P(cx + s * .55, cy), P(cx - s * .55, cy))
        p.drawPolyline([P(cx - s * .1, cy - s * .5), P(cx - s * .6, cy), P(cx - s * .1, cy + s * .5)])
    elif kind in ("down", "up", "left", "right"):
        d = {"down": (0, 1), "up": (0, -1), "left": (-1, 0), "right": (1, 0)}[kind]
        px, py = -d[1], d[0]
        a = P(cx - d[0] * s * .25 - px * s * .5, cy - d[1] * s * .25 - py * s * .5)
        b = P(cx + d[0] * s * .3, cy + d[1] * s * .3)
        c = P(cx - d[0] * s * .25 + px * s * .5, cy - d[1] * s * .25 + py * s * .5)
        p.drawPolyline([a, b, c])
    elif kind == "check":
        p.drawPolyline([P(cx - s * .5, cy), P(cx - s * .1, cy + s * .4), P(cx + s * .55, cy - s * .4)])
    elif kind == "gear":
        p.drawEllipse(P(cx, cy), s * .62, s * .62)
        p.drawEllipse(P(cx, cy), s * .22, s * .22)
        for i in range(8):
            a = math.radians(i * 45)
            p.drawLine(P(cx + s * .62 * math.cos(a), cy + s * .62 * math.sin(a)),
                       P(cx + s * .95 * math.cos(a), cy + s * .95 * math.sin(a)))
    elif kind == "info":
        p.drawEllipse(P(cx, cy), s * .85, s * .85)
        p.drawLine(P(cx, cy - s * .05), P(cx, cy + s * .42))
        p.drawPoint(P(cx, cy - s * .38))
    elif kind == "lock":
        p.drawRoundedRect(QRectF(cx - s * .55, cy - s * .1, s * 1.1, s * .85), 3, 3)
        p.drawArc(QRectF(cx - s * .33, cy - s * .75, s * .66, s * .9), 0, 180 * 16)
    elif kind == "trash":
        p.drawLine(P(cx - s * .65, cy - s * .5), P(cx + s * .65, cy - s * .5))
        p.drawPolyline([P(cx - s * .45, cy - s * .5), P(cx - s * .35, cy + s * .75), P(cx + s * .35, cy + s * .75), P(cx + s * .45, cy - s * .5)])
        p.drawLine(P(cx - s * .2, cy - s * .5), P(cx - s * .2, cy - s * .8))
        p.drawLine(P(cx + s * .2, cy - s * .5), P(cx + s * .2, cy - s * .8))
        p.drawLine(P(cx - s * .2, cy - s * .8), P(cx + s * .2, cy - s * .8))
    elif kind == "logs":
        for i in (-1, 0, 1):
            p.drawLine(P(cx - s * .65, cy + i * s * .5), P(cx + s * .65, cy + i * s * .5))
    elif kind == "copy":
        p.drawRoundedRect(QRectF(cx - s * .2, cy - s * .75, s * .95, s * 1.1), 3, 3)
        p.drawRoundedRect(QRectF(cx - s * .75, cy - s * .35, s * .95, s * 1.1), 3, 3)
    elif kind == "close":
        p.drawLine(P(cx - s * .5, cy - s * .5), P(cx + s * .5, cy + s * .5))
        p.drawLine(P(cx + s * .5, cy - s * .5), P(cx - s * .5, cy + s * .5))
    elif kind == "minus":
        p.drawLine(P(cx - s * .55, cy), P(cx + s * .55, cy))
    elif kind == "refresh":
        p.drawArc(QRectF(cx - s * .6, cy - s * .6, s * 1.2, s * 1.2), 40 * 16, 280 * 16)
        p.drawPolyline([P(cx + s * .55, cy - s * .75), P(cx + s * .55, cy - s * .3), P(cx + s * .1, cy - s * .3)])
    p.restore()


class IconButton(QPushButton):
    def __init__(self, kind, size=38, stroke=2.0, parent=None):
        super().__init__(parent)
        self.kind, self.stroke = kind, stroke
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = pal()
        if self.underMouse():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(c["card2"]))
            p.drawEllipse(self.rect().adjusted(1, 1, -1, -1))
        col = QColor(c["primary"] if self.kind in ("gear", "info", "copy", "trash", "refresh") else c["sub"] if self.kind in ("minus", "close") else c["text"])
        if not self.isEnabled():
            col = QColor(c["sub"])
        r = QRectF(self.rect()).adjusted(9, 9, -9, -9)
        if self.kind == "back" and rtl():  # arrow points the other way in right-to-left layouts
            p.translate(self.width(), 0)
            p.scale(-1, 1)
        paint_icon(p, self.kind, r, col, self.stroke)


class Icon(QWidget):
    def __init__(self, kind, size=20, color_key="sub", stroke=2.0):
        super().__init__()
        self.kind, self.ck, self.stroke = kind, color_key, stroke
        self.setFixedSize(size, size)

    def paintEvent(self, _):
        p = QPainter(self)
        paint_icon(p, self.kind, QRectF(self.rect()).adjusted(2, 2, -2, -2), QColor(pal()[self.ck]), self.stroke)


# ------------------------------------------------------------ controls
class Switch(QCheckBox):
    def __init__(self, value=False):
        super().__init__()
        self.setChecked(value)
        self.setFixedSize(48, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, _):
        c = pal()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on, en = self.isChecked(), self.isEnabled()
        track = QColor(c["primary"] if on else c["card2"])
        if not en:
            track.setAlpha(120)
        p.setPen(QPen(QColor(c["primary"] if on else c["line"]), 1.5))
        p.setBrush(track)
        p.drawRoundedRect(QRectF(1, 2, 46, 24), 12, 12)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(c["onp"] if on else c["sub"]))
        x = 35 if on else 13
        p.drawEllipse(QPointF(x, 14), 8 if on else 6, 8 if on else 6)


class FlowLayout(QLayout):
    def __init__(self, parent=None, spacing=8):
        super().__init__(parent)
        self._items = []
        self.setSpacing(spacing)
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, it): self._items.append(it)
    def count(self): return len(self._items)
    def itemAt(self, i): return self._items[i] if 0 <= i < len(self._items) else None
    def takeAt(self, i): return self._items.pop(i) if 0 <= i < len(self._items) else None
    def expandingDirections(self): return Qt.Orientation(0)
    def hasHeightForWidth(self): return True
    def heightForWidth(self, w): return self._do(QRect(0, 0, w, 0), True)

    def setGeometry(self, r):
        super().setGeometry(r)
        self._do(r, False)

    def sizeHint(self): return self.minimumSize()

    def minimumSize(self):
        sz = QSize()
        for it in self._items:
            sz = sz.expandedTo(it.minimumSize())
        return sz

    def _do(self, rect, test):
        x, y, lh, sp = rect.x(), rect.y(), 0, self.spacing()
        for it in self._items:
            sh = it.sizeHint()
            if x + sh.width() > rect.right() + 1 and lh > 0:
                x, y, lh = rect.x(), y + lh + sp, 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), sh))
            x += sh.width() + sp
            lh = max(lh, sh.height())
        return y + lh - rect.y()


def _repolish(w):
    w.style().unpolish(w)
    w.style().polish(w)


class Chips(QWidget):
    """Wrapping outlined choice chips; the picked one is filled."""

    def __init__(self, items, current, on_pick, enabled=True):
        super().__init__()
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        fl = FlowLayout(self)
        for val, text in items:
            b = QPushButton(text)
            b.setObjectName("chip")
            b.setProperty("on", "true" if val == current else "false")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setEnabled(enabled)
            b.clicked.connect(lambda _=False, v=val: on_pick(v))
            fl.addWidget(b)


class Segmented(QFrame):
    """Capsule with equal segments; the picked one is filled and carries a check mark."""

    def __init__(self, on_pick):
        super().__init__()
        self.setObjectName("segBox")
        self._h = QHBoxLayout(self)
        self._h.setContentsMargins(3, 3, 3, 3)
        self._h.setSpacing(2)
        self._on = on_pick
        self.btns = {}

    def set_items(self, items, current, enabled=True):
        while self._h.count():
            it = self._h.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.btns = {}
        for val, text in items:
            b = QPushButton(("✓  " if val == current else "") + text)
            b.setObjectName("seg")
            b.setProperty("on", "true" if val == current else "false")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setEnabled(enabled)
            b.clicked.connect(lambda _=False, v=val: self._on(v))
            self._h.addWidget(b, 1)
            self.btns[val] = b


# ------------------------------------------------------------ connect button
class ConnectButton(QWidget):
    def __init__(self, on_click):
        super().__init__()
        self.setFixedSize(210, 210)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._click, self.phase, self._t = on_click, "idle", 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def set_phase(self, phase):
        self.phase = phase
        self.update()

    def _tick(self):
        self._t += 0.033
        if self.phase != "idle":
            self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._click()

    def paintEvent(self, _):
        c = pal()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ctr = QPointF(self.width() / 2, self.height() / 2)
        live = self.phase == "connected"
        busy = self.phase in ("connecting", "reconnecting", "stopping")
        p.setPen(Qt.PenStyle.NoPen)
        if live:
            pulse = 0.5 + 0.5 * math.sin(self._t * 2.0)
            ring = QColor(c["card2"])
            ring.setAlpha(int(190 + 65 * pulse))
            p.setBrush(ring)
            p.drawEllipse(ctr, 92, 92)
            p.setBrush(QColor(c["primary"]))
        else:
            p.setBrush(QColor(c["card2"]))
        p.drawEllipse(ctr, 70, 70)
        if busy:
            p.setPen(QPen(QColor(c["amber"]), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(ctr.x() - 82, ctr.y() - 82, 164, 164), int(-self._t * 300 * 16), 110 * 16)
        col = QColor(c["onp"]) if live else QColor(c["amber"] if busy else c["sub"])
        p.setPen(QPen(col, 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        r = 27
        p.drawArc(QRectF(ctr.x() - r, ctr.y() - r + 4, 2 * r, 2 * r), 125 * 16, 290 * 16)
        p.drawLine(QPointF(ctr.x(), ctr.y() - r - 6), QPointF(ctr.x(), ctr.y() - 4))


# ------------------------------------------------------------ rounded sheet dialog
class Sheet(QDialog):
    """Frameless rounded dialog, like the Android bottom sheets / alert dialogs."""

    def __init__(self, parent, title, width=360):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedWidth(width)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft if rtl() else Qt.LayoutDirection.LeftToRight)
        self.v = QVBoxLayout(self)
        self.v.setContentsMargins(24, 22, 24, 16)
        self.v.setSpacing(14)
        t = QLabel(title)
        t.setStyleSheet("font-size:21px;")
        self.v.addWidget(t)
        self.setStyleSheet(qss())

    def paintEvent(self, _):
        c = pal()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 26, 26)
        p.fillPath(path, QColor(c["sheet"]))
        p.setPen(QPen(QColor(c["border"]), 1))
        p.drawPath(path)

    def showEvent(self, e):
        par = self.parentWidget()
        if par:
            g = par.window().frameGeometry()
            self.move(g.center() - QPoint(self.width() // 2, self.height() // 2))
        super().showEvent(e)
