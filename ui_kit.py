"""Widget kit that gives the Windows app the same look as the Android app (3.8 design):
indigo/teal palette, round bordered icon buttons, tonal pills, filled segmented switch,
gradient logo and a glowing connect button."""
import math

from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, QSizeF, Qt, QTimer
from PyQt6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                         QRadialGradient)
from PyQt6.QtWidgets import (QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QLayout, QPushButton, QVBoxLayout,
                             QWidget)

import core
from core import S
from i18n import tr


def _mix(fg, bg, a):
    f, b = QColor(fg), QColor(bg)
    return QColor(round(b.red() + (f.red() - b.red()) * a), round(b.green() + (f.green() - b.green()) * a),
                  round(b.blue() + (f.blue() - b.blue()) * a)).name()


# Same colours as the Android Theme.kt (Material 3 roles):
#   bg=surface  card=surfaceContainer  card2=surfaceContainerHigh  hi=surfaceContainerHighest
#   text=onSurface  sub=onSurfaceVariant  border=outlineVariant  line=outline
#   primary/onp=primary/onPrimary  teal=secondary (brand "a")  amber=tertiary (busy)  danger=error
PAL = {
    "dark": dict(bg="#0A0E1A", card="#131A2B", card2="#1B2438", hi="#232E47", text="#E8EAF6", sub="#A9B1CC",
                 border="#263050", line="#55607F", primary="#8D9BFF", onp="#0B1240", teal="#3DDBC4",
                 amber="#FFB84D", danger="#FF8A8A", sheet="#131A2B"),
    "light": dict(bg="#F4F6FC", card="#FFFFFF", card2="#EEF1FA", hi="#E6EAF7", text="#151A2C", sub="#586080",
                  border="#DDE2F0", line="#8B93B0", primary="#4F5BD5", onp="#FFFFFF", teal="#0FA58F",
                  amber="#D98200", danger="#D93A3A", sheet="#FFFFFF"),
}
for _p in PAL.values():
    _p["sel"] = _mix(_p["primary"], _p["card"], 0.14)


def pal():
    return PAL.get(S.theme, PAL["dark"])


def L(key, **kw):
    return tr(S.language, key, **kw)


def rtl():
    return S.language == "fa"


def alpha(color, a):
    c = QColor(color)
    c.setAlphaF(max(0.0, min(1.0, a)))
    return c


def mix(c1, c2, t):
    a, b = QColor(c1), QColor(c2)
    return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t))


def brand_gradient(r: QRectF) -> QLinearGradient:
    """The Android 'Extra.gradient': teal -> primary, top-left to bottom-right."""
    g = QLinearGradient(r.topLeft(), r.bottomRight())
    g.setColorAt(0.0, QColor(pal()["teal"]))
    g.setColorAt(1.0, QColor(pal()["primary"]))
    return g


def qss():
    p = pal()
    return f"""
    * {{ font-family: 'Segoe UI', Tahoma, sans-serif; font-size: 13px; color: {p['text']}; }}
    QWidget {{ background: transparent; }}
    QLabel:disabled {{ color: {p['sub']}; }}
    QLabel#sub {{ color: {p['sub']}; font-weight: 500; }}
    QLabel#hint {{ color: {p['sub']}; font-size: 12px; }}
    QLabel#err {{ color: {p['danger']}; font-size: 12px; }}
    QLabel#gtitle {{ color: {p['primary']}; font-weight: 700; font-size: 14px; }}
    QLabel#stitle {{ font-weight: 700; font-size: 14px; }}
    QLabel#page {{ font-size: 22px; font-weight: 700; }}
    QLabel#title {{ font-size: 22px; font-weight: 700; }}
    QLabel#mono {{ font-family: Consolas, monospace; font-size: 11px; color: {p['sub']}; }}
    QPushButton {{ border: none; background: transparent; }}
    QPushButton#link {{ color: {p['primary']}; font-weight: 600; font-size: 14px; padding: 6px 12px; border-radius: 12px; }}
    QPushButton#link:hover {{ background: {p['card2']}; }}
    QPushButton#row {{ padding: 14px 16px; text-align: left; }}
    QPushButton#row:disabled {{ color: {p['sub']}; }}
    QPushButton#action:disabled {{ color: {p['sub']}; }}
    QLineEdit, QSpinBox {{ background: {p['card2']}; border: 1px solid transparent; border-radius: 14px; padding: 11px 14px;
        selection-background-color: {p['primary']}; selection-color: {p['onp']}; }}
    QLineEdit:focus, QSpinBox:focus {{ border: 1px solid {p['primary']}; }}
    QLineEdit[bad="true"] {{ border: 1px solid {p['danger']}; }}
    QLineEdit:disabled, QSpinBox:disabled {{ color: {p['sub']}; }}
    QTextEdit {{ background: transparent; border: none; font-family: Consolas, monospace; font-size: 12px; }}
    QScrollArea {{ border: none; }}
    QScrollBar:vertical {{ width: 8px; background: transparent; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {p['line']}; border-radius: 4px; min-height: 36px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QScrollBar:horizontal {{ height: 0; }}
    QToolTip {{ background: {p['card']}; color: {p['text']}; border: 1px solid {p['border']}; padding: 4px 8px; }}
    QMenu {{ background: {p['card']}; border: 1px solid {p['border']}; padding: 4px; }}
    QMenu::item {{ padding: 7px 22px; border-radius: 8px; }}
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


def lion_sun_pixmap(width: int = 26) -> QPixmap:
    """Iran's Lion and Sun flag, drawn (same shapes as LionSunFlag.kt) - there is no emoji or PNG for it."""
    h = max(1, round(width * 18 / 26))
    pm = QPixmap(width, h)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, width, h), 3 * width / 26, 3 * width / 26)
    p.setClipPath(clip)
    green, red, gold = QColor("#239F40"), QColor("#DA0000"), QColor("#F2B000")
    amber, face, sword = QColor("#965C14"), QColor("#BE8228"), QColor("#5A5A5A")
    bh = h / 3
    p.fillRect(QRectF(0, 0, width, h), QColor("#FFFFFF"))
    p.fillRect(QRectF(0, 0, width, bh), green)
    p.fillRect(QRectF(0, 2 * bh, width, bh), red)
    r, cx, cy = 0.34 * h, width / 2, h / 2

    def pt(x, y):
        return QPointF(cx + x * r, cy + y * r)

    sx, sy = 0.28, -0.18
    p.setPen(QPen(gold, r * 0.07, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
    for i in range(16):
        a = i * math.pi / 8
        p.drawLine(pt(sx + 0.62 * math.cos(a), sy + 0.62 * math.sin(a)), pt(sx + 0.88 * math.cos(a), sy + 0.88 * math.sin(a)))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(gold)
    p.drawEllipse(pt(sx, sy), r * 0.55, r * 0.55)
    p.setBrush(amber)
    p.drawRoundedRect(QRectF(pt(-0.6, 0), QSizeF(1.15 * r, 0.45 * r)), 0.2 * r, 0.2 * r)
    for lx in (-0.5, -0.28, 0.22, 0.42):
        p.drawRect(QRectF(pt(lx, 0.35), QSizeF(0.13 * r, 0.43 * r)))
    p.drawEllipse(pt(-0.62, -0.08), r * 0.38, r * 0.38)
    p.setBrush(face)
    p.drawEllipse(pt(-0.72, -0.02), r * 0.2, r * 0.2)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(amber, r * 0.08, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawPolyline([pt(0.55, 0.1), pt(0.78, -0.05), pt(0.72, -0.35)])
    p.setPen(QPen(sword, r * 0.06, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(pt(-0.45, -0.15), pt(-0.2, -0.85))
    p.end()
    return pm


def flag_pixmap(cc: str, width: int = 36) -> QPixmap:
    key = (cc.lower() or "auto", width)
    if key not in _flag_cache:
        if cc.upper() == "IR":
            pm = lion_sun_pixmap(width)
        else:
            name = "auto" if not cc else cc.upper()
            pm = QPixmap(core.resource("assets", "flags", f"{name}.png"))
            if not pm.isNull():
                pm = pm.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)
        _flag_cache[key] = pm
    return _flag_cache[key]


# ------------------------------------------------------------ icons (same 24-unit drawings as Icon8 in Components.kt)
def paint_icon(p: QPainter, kind: str, r: QRectF, color: QColor, w: float = 2.0):
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    side = min(r.width(), r.height())
    u = side / 24.0
    ox, oy = r.center().x() - side / 2, r.center().y() - side / 2
    color = QColor(color)
    pen = QPen(color, w * u, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    def P(x, y):
        return QPointF(ox + x * u, oy + y * u)

    def line(x1, y1, x2, y2):
        p.drawLine(P(x1, y1), P(x2, y2))

    def poly(close, *pts):
        path = QPainterPath(P(pts[0], pts[1]))
        for i in range(2, len(pts), 2):
            path.lineTo(P(pts[i], pts[i + 1]))
        if close:
            path.closeSubpath()
        p.drawPath(path)

    def arc(x, y, w_, h_, start, sweep):
        # Compose angles run clockwise from 3 o'clock; Qt's run counter-clockwise.
        p.drawArc(QRectF(P(x, y), QSizeF(w_ * u, h_ * u)), int(-start * 16), int(-sweep * 16))

    def ring(cx, cy, rad):
        p.drawEllipse(P(cx, cy), rad * u, rad * u)

    def dot(cx, cy, rad):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(P(cx, cy), rad * u, rad * u)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

    def rrect(x, y, w_, h_, rad):
        p.drawRoundedRect(QRectF(P(x, y), QSizeF(w_ * u, h_ * u)), rad * u, rad * u)

    if kind == "back":
        line(20, 12, 5, 12)
        poly(False, 11, 6, 5, 12, 11, 18)
    elif kind in ("settings", "gear"):
        line(4, 7, 20, 7)
        line(4, 12, 20, 12)
        line(4, 17, 20, 17)
        dot(9, 7, 2.6)
        dot(15, 12, 2.6)
        dot(8, 17, 2.6)
    elif kind == "logs":
        rrect(5, 3.5, 14, 17, 3.5)
        line(8.5, 9, 15.5, 9)
        line(8.5, 13, 15.5, 13)
        line(8.5, 17, 12.5, 17)
    elif kind == "power":
        arc(4.5, 5.5, 15, 15, -55, 290)
        line(12, 3, 12, 12)
    elif kind == "check":
        poly(False, 5, 12.5, 10, 17, 19, 7)
    elif kind == "chevron":
        poly(False, 6, 9, 12, 15, 18, 9)
    elif kind == "chev_up":
        poly(False, 6, 15, 12, 9, 18, 15)
    elif kind == "chev_right":
        poly(False, 9, 6, 15, 12, 9, 18)
    elif kind == "chev_left":
        poly(False, 15, 6, 9, 12, 15, 18)
    elif kind == "lock":
        rrect(5.5, 11, 13, 9.5, 3)
        arc(8.5, 4.5, 7, 7, 180, 180)
        line(8.5, 8, 8.5, 11)
        line(15.5, 8, 15.5, 11)
    elif kind == "down":
        line(12, 4, 12, 16)
        poly(False, 6, 11, 12, 17, 18, 11)
        line(5, 21, 19, 21)
    elif kind == "up":
        line(12, 20, 12, 8)
        poly(False, 6, 13, 12, 7, 18, 13)
        line(5, 3, 19, 3)
    elif kind == "bolt":
        poly(True, 13, 3, 5, 13.5, 11, 13.5, 10, 21, 19, 10, 13, 10)
    elif kind == "globe":
        ring(12, 12, 9)
        p.drawEllipse(QRectF(P(8, 3), QSizeF(8 * u, 18 * u)))
        line(3, 12, 21, 12)
    elif kind == "refresh":
        arc(4.5, 5.5, 15, 15, 0, 270)
        poly(False, 8.5, 2.5, 12, 5.5, 8.5, 8.5)
    elif kind == "copy":
        rrect(8.5, 8.5, 11, 11, 2.5)
        poly(False, 15, 5, 5, 5, 5, 15, 8, 15)
    elif kind == "share":
        ring(6, 12, 2.6)
        ring(18, 6, 2.6)
        ring(18, 18, 2.6)
        line(8.2, 10.8, 15.8, 7.2)
        line(8.2, 13.2, 15.8, 16.8)
    elif kind == "trash":
        line(4, 7, 20, 7)
        poly(False, 6, 7, 7, 20, 17, 20, 18, 7)
        poly(False, 9, 7, 9, 4, 15, 4, 15, 7)
        line(10, 11, 10, 16)
        line(14, 11, 14, 16)
    elif kind == "info":
        ring(12, 12, 9)
        dot(12, 7.8, 1.2)
        line(12, 11.5, 12, 16.5)
    elif kind == "code":
        poly(False, 8, 7, 3, 12, 8, 17)
        poly(False, 16, 7, 21, 12, 16, 17)
        line(13.5, 5, 10.5, 19)
    elif kind == "send":
        poly(True, 21, 3, 3, 10.5, 10, 13, 13, 20)
        line(10, 13, 21, 3)
    elif kind == "close":
        line(6, 6, 18, 18)
        line(18, 6, 6, 18)
    elif kind == "minus":
        line(6, 12, 18, 12)
    p.restore()


class IconButton(QPushButton):
    """Round button with a thin outline (Android IconBtn). minus/close are flat window-chrome buttons."""

    def __init__(self, kind, size=42, stroke=2.0, tint=None, parent=None):
        super().__init__(parent)
        self.kind, self.stroke, self.tint = kind, stroke, tint
        self.flat = kind in ("minus", "close")
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = pal()
        hover = self.underMouse() and self.isEnabled()
        circle = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)
        if self.flat:
            if hover:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(c["card2"]))
                p.drawEllipse(circle)
            col = QColor(c["sub"])
        else:
            p.setPen(QPen(QColor(c["border"]), 1))
            p.setBrush(QColor(c["hi"] if hover else c["card"]))
            p.drawEllipse(circle)
            col = QColor(c[self.tint] if self.tint else c["text"])
        if not self.isEnabled():
            col = QColor(c["sub"])
        px = 20 if self.width() >= 36 else 14
        r = QRectF((self.width() - px) / 2, (self.height() - px) / 2, px, px)
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
        paint_icon(p, self.kind, QRectF(self.rect()), QColor(pal()[self.ck]), self.stroke)


class Dot(QWidget):
    def __init__(self, size=8):
        super().__init__()
        self.setFixedSize(size, size)
        self.color = QColor(pal()["sub"])

    def set_color(self, c):
        self.color = QColor(c)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.color)
        p.drawEllipse(QRectF(self.rect()))


class LogoMark(QWidget):
    """Gradient rounded square with a white '8' (Android LogoMark)."""

    def __init__(self, size):
        super().__init__()
        self.setFixedSize(size, size)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(brand_gradient(r)))
        rad = self.width() * 0.3
        p.drawRoundedRect(r, rad, rad)
        f = QFont(self.font())
        f.setPixelSize(max(8, int(self.width() * 0.56)))
        f.setWeight(QFont.Weight.ExtraBold)
        p.setFont(f)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, "8")


class Tile(QWidget):
    """Rounded square tinted with the primary colour that holds an icon (About rows)."""

    def __init__(self, kind, size=42, icon=22):
        super().__init__()
        self.kind, self.icon = kind, icon
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = pal()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(alpha(c["primary"], 0.14))
        p.drawRoundedRect(QRectF(self.rect()), 14, 14)
        s = self.icon
        paint_icon(p, self.kind, QRectF((self.width() - s) / 2, (self.height() - s) / 2, s, s), QColor(c["primary"]), 2.0)


# ------------------------------------------------------------ controls
class Switch(QCheckBox):
    """Material 3 switch: filled primary track with a big thumb when on, outlined track with a small thumb when off."""

    def __init__(self, value=False):
        super().__init__()
        self.setChecked(value)
        self.setFixedSize(52, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, _):
        c = pal()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        p.setOpacity(1.0 if self.isEnabled() else 0.5)
        if on:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(c["primary"]))
            p.drawRoundedRect(QRectF(0, 0, 52, 32), 16, 16)
            p.setBrush(QColor(c["onp"]))
            p.drawEllipse(QPointF(36, 16), 12, 12)
        else:
            p.setPen(QPen(QColor(c["line"]), 2))
            p.setBrush(QColor(c["hi"]))
            p.drawRoundedRect(QRectF(1, 1, 50, 30), 15, 15)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(c["line"]))
            p.drawEllipse(QPointF(16, 16), 8, 8)


class SwitchRow(QWidget):
    """Title + switch; the whole row is clickable (Android SwitchRow)."""

    def __init__(self, title, value, on_toggle):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(12)
        self.lab = QLabel(title)
        self.lab.setWordWrap(True)
        self.lab.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.sw = Switch(value)
        self.sw.toggled.connect(on_toggle)
        h.addWidget(self.lab, 1)
        h.addWidget(self.sw)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.sw.isEnabled():
            self.sw.toggle()


class SectionTitle(QWidget):
    """Small heading with the brand-gradient bar in front (Android SectionTitle)."""

    def __init__(self, text):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 10, 0, 0)
        lab = QLabel(text)
        lab.setObjectName("stitle")
        h.addWidget(lab)
        h.addStretch()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x = self.width() - 8 if self.layoutDirection() == Qt.LayoutDirection.RightToLeft else 4
        r = QRectF(x, 10 + (self.height() - 10 - 14) / 2, 4, 14)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(brand_gradient(r)))
        p.drawRoundedRect(r, 2, 2)


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


class Card(QFrame):
    """Rounded panel painted with anti-aliasing. kind: card | banner | pill | seg."""

    def __init__(self, kind="card"):
        super().__init__()
        self.kind, self.tint, self._hover = kind, None, False

    def paintEvent(self, e):
        c, k = pal(), self.kind
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        if k == "card":
            p.setPen(QPen(QColor(c["border"]), 1))
            p.setBrush(QColor(c["card2"] if self._hover else c["card"]))
            p.drawRoundedRect(r, 22, 22)
        elif k == "banner":
            p.setBrush(alpha(c["primary"], 0.10))
            p.drawRoundedRect(r, 16, 16)
        elif k == "seg":
            p.setBrush(QColor(c["card2"]))
            p.drawRoundedRect(r, 16, 16)
        elif k == "pill" and self.tint is not None:
            p.setBrush(alpha(self.tint, 0.12))
            p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.end()
        super().paintEvent(e)


class ClickCard(Card):
    """A card that behaves like a button (the About rows, the log preview on Home)."""

    def __init__(self, on_click):
        super().__init__("card")
        self._cb = on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self._cb()
        super().mouseReleaseEvent(e)


class Btn(QPushButton):
    """Button whose rounded shape (and, for chip/seg/tonal, its content) is painted here, anti-aliased.
    variant:
      chip   - choice chip: tinted + outlined + check mark when picked        (Android Pill)
      seg    - one cell of the filled segmented switch                        (Android Segmented)
      tonal  - icon + text on a tinted background                             (Android TonalPill)
      row    - rounded field-like row that holds child widgets / text         (Android RegionButton)
      action - full-width settings action row that holds child widgets        (Android ActionRow)
      pick   - list row of a picker dialog
    """

    PAINTED = ("chip", "seg", "tonal")

    def __init__(self, text="", variant="chip", on=False, icon=None, danger=False):
        super().__init__(text)
        self.variant, self._on, self.icon_kind, self.danger = variant, on, icon, danger
        self.setObjectName(variant)
        self.setProperty("on", "true" if on else "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if variant == "seg":
            self.setFixedHeight(40)

    # ---- painted content
    def _font(self):
        f = QFont(self.font())
        f.setPixelSize(13)
        if self.variant == "chip":
            f.setWeight(QFont.Weight.DemiBold if self._on else QFont.Weight.Normal)
        elif self.variant == "seg":
            f.setWeight(QFont.Weight.DemiBold if self._on else QFont.Weight.Medium)
        else:
            f.setWeight(QFont.Weight.DemiBold)
        return f

    def sizeHint(self):
        if self.variant not in self.PAINTED:
            return super().sizeHint()
        fm = QFontMetrics(self._font())
        tw = fm.horizontalAdvance(self.text())
        if self.variant == "chip":
            return QSize(28 + (20 if self._on else 0) + tw, 18 + fm.height())
        if self.variant == "tonal":
            return QSize(28 + 26 + tw, 20 + fm.height())
        return QSize(tw + 24, 40)

    def minimumSizeHint(self):
        if self.variant == "seg":
            return QSize(24, 40)
        if self.variant in self.PAINTED:
            return self.sizeHint()
        return super().minimumSizeHint()

    def _paint_content(self, p, color, icon, icon_px, gap, stroke=2.0):
        f = self._font()
        p.setFont(f)
        tw = QFontMetrics(f).horizontalAdvance(self.text())
        iw = (icon_px + gap) if icon else 0
        x = (self.width() - (iw + tw)) / 2
        if icon:
            paint_icon(p, icon, QRectF(x, (self.height() - icon_px) / 2, icon_px, icon_px), color, stroke)
        p.setPen(color)
        p.drawText(QRectF(x + iw, 0, tw + 4, self.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())

    def paintEvent(self, e):
        c, v = pal(), self.variant
        en = self.isEnabled()
        hover = self.underMouse() and en
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if v == "chip":
            p.setOpacity(1.0 if en else 0.5)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(c["hi"] if hover and not self._on else c["card2"]))
            p.drawRoundedRect(r, 14, 14)
            if self._on:
                p.setBrush(alpha(c["primary"], 0.16))
                p.drawRoundedRect(r, 14, 14)
                p.setPen(QPen(alpha(c["primary"], 0.55), 1))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(r, 14, 14)
            self._paint_content(p, QColor(c["primary"] if self._on else c["sub"]),
                                "check" if self._on else None, 14, 6, 2.6)
            p.end()
            return
        if v == "seg":
            p.setOpacity(1.0 if en else 0.6)
            if self._on:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(c["primary"]))
                p.drawRoundedRect(r, 12, 12)
            elif hover:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(alpha(c["primary"], 0.10))
                p.drawRoundedRect(r, 12, 12)
            self._paint_content(p, QColor(c["onp"] if self._on else c["sub"]), None, 0, 0)
            p.end()
            return
        if v == "tonal":
            tone = QColor(c["danger"] if self.danger else c["primary"])
            p.setOpacity(1.0 if en else 0.5)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(alpha(tone, 0.20 if hover else 0.13))
            p.drawRoundedRect(r, 14, 14)
            self._paint_content(p, tone, self.icon_kind, 18, 8)
            p.end()
            return

        # shapes that carry child widgets / QSS text
        fill, rad = None, 14
        if v == "row":
            fill = c["hi"] if hover else c["card2"]
        elif v == "action":
            fill, rad = (c["hi"] if hover else c["card2"]), 16
        elif v == "pick":
            rad = 12
            if self._on:
                fill = alpha(c["primary"], 0.14)
            elif hover:
                fill = c["card2"]
        if fill:
            col = QColor(fill)
            if not en:
                col.setAlpha(150)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(r, rad, rad)
        p.end()
        super().paintEvent(e)  # text and child widgets


class Chips(QWidget):
    """Wrapping choice chips; the picked one is tinted, outlined and carries a check mark."""

    def __init__(self, items, current, on_pick, enabled=True):
        super().__init__()
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        fl = FlowLayout(self)
        for val, text in items:
            b = Btn(text, "chip", val == current)
            b.setEnabled(enabled)
            b.clicked.connect(lambda _=False, v=val: on_pick(v))
            fl.addWidget(b)


class Segmented(Card):
    """Full-width switch with equal cells; the picked cell is filled with the primary colour."""

    def __init__(self, on_pick):
        super().__init__("seg")
        self._h = QHBoxLayout(self)
        self._h.setContentsMargins(4, 4, 4, 4)
        self._h.setSpacing(4)
        self._on = on_pick
        self.btns = {}

    def set_items(self, items, current, enabled=True):
        while self._h.count():
            it = self._h.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.btns = {}
        for val, text in items:
            b = Btn(text, "seg", val == current)
            b.setEnabled(enabled)
            b.clicked.connect(lambda _=False, v=val: self._on(v))
            self._h.addWidget(b, 1)
            self.btns[val] = b


# ------------------------------------------------------------ connect button
class ConnectButton(QWidget):
    """Big round power button with soft expanding rings while the link is up or being set up
    (port of ConnectButton in HomeScreen.kt)."""
    D = 150

    def __init__(self, on_click):
        super().__init__()
        side = int(self.D * 1.5)
        self.setFixedSize(side, side)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._click, self.phase, self._t = on_click, "idle", 0.0
        self._glow = self._live = self._busy = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def set_phase(self, phase):
        self.phase = phase
        self.update()

    @staticmethod
    def _toward(cur, target, dt, dur):
        step = dt / dur
        return min(target, cur + step) if cur < target else max(target, cur - step)

    def _is_busy(self):
        return self.phase in ("connecting", "reconnecting", "stopping")

    def _tick(self):
        if not self.isVisible():
            return
        dt = 0.033
        self._t += dt
        live, busy = self.phase == "connected", self._is_busy()
        g = self._toward(self._glow, 1.0 if live else 0.75 if busy else 0.0, dt, 0.5)
        l = self._toward(self._live, 1.0 if live else 0.0, dt, 0.45)
        b = self._toward(self._busy, 1.0 if busy else 0.0, dt, 0.3)
        changed = (g, l, b) != (self._glow, self._live, self._busy)
        self._glow, self._live, self._busy = g, l, b
        if changed or live or busy:
            self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            pos = e.position()
            if math.hypot(pos.x() - self.width() / 2, pos.y() - self.height() / 2) <= self.D / 2:
                self._click()

    def paintEvent(self, _):
        c = pal()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2
        ctr = QPointF(cx, cy)
        outer, core_r = self.width() / 2, self.D / 2
        busy_now = self._is_busy()
        ring = QColor(c["amber"] if busy_now else c["teal"])

        if self._glow > 0.01:
            g = QRadialGradient(ctr, outer)
            g.setColorAt(0.0, alpha(ring, 0.26 * self._glow))
            g.setColorAt(1.0, alpha(ring, 0.0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g))
            p.drawEllipse(ctr, outer, outer)
            p.setBrush(Qt.BrushStyle.NoBrush)
            for i in range(3):
                pr = (self._t / 2.6 + i / 3.0) % 1.0
                p.setPen(QPen(alpha(ring, (1.0 - pr) * 0.30 * self._glow), 1.5))
                rad = core_r + (outer - core_r) * pr
                p.drawEllipse(ctr, rad, rad)

        scale = (0.995 + 0.045 * math.sin(self._t * 2 * math.pi / 1.8)) if busy_now else 1.0
        p.save()
        p.translate(ctr)
        p.scale(scale, scale)
        disc = QRectF(-core_r, -core_r, 2 * core_r, 2 * core_r)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(c["card2"]))
        p.drawEllipse(disc)
        if self._live > 0.01:
            p.setOpacity(self._live)
            p.setBrush(QBrush(brand_gradient(disc)))
            p.drawEllipse(disc)
        if self._busy > 0.01:
            p.setOpacity(self._busy)
            p.setBrush(QColor(c["amber"]))
            p.drawEllipse(disc)
        p.setOpacity(max(0.0, 1.0 - max(self._live, self._busy)))
        p.setPen(QPen(QColor(c["border"]), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(disc.adjusted(0.5, 0.5, -0.5, -0.5))
        p.setOpacity(1.0)
        fg = mix(c["sub"], "#FFFFFF", self._live)
        fg = mix(fg, "#2B1E00", self._busy)
        s = self.D * 0.40
        paint_icon(p, "power", QRectF(-s / 2, -s / 2, s, s), fg, 2.3)
        p.restore()


# ------------------------------------------------------------ rounded sheet dialog
class Sheet(QDialog):
    """Frameless rounded dialog, like the Android alert dialogs."""

    def __init__(self, parent, title, width=360):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedWidth(width)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft if rtl() else Qt.LayoutDirection.LeftToRight)
        self.v = QVBoxLayout(self)
        self.v.setContentsMargins(24, 24, 24, 16)
        self.v.setSpacing(14)
        t = QLabel(title)
        t.setStyleSheet("font-size:22px;font-weight:700;")
        self.v.addWidget(t)
        self.setStyleSheet(qss())

    def paintEvent(self, _):
        c = pal()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 28, 28)
        p.fillPath(path, QColor(c["sheet"]))
        p.setPen(QPen(QColor(c["border"]), 1))
        p.drawPath(path)

    def showEvent(self, e):
        par = self.parentWidget()
        if par:
            g = par.window().frameGeometry()
            self.move(g.center() - QPoint(self.width() // 2, self.height() // 2))
        super().showEvent(e)
