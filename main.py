import ctypes
import math
import sys
import time

from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import (QAction, QColor, QDesktopServices, QFont, QIcon, QLinearGradient, QPainter,
                         QPainterPath, QPen, QRadialGradient)
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout,
                             QLabel, QLayout, QLineEdit, QListWidget, QMenu, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox,
                             QSystemTrayIcon, QVBoxLayout, QWidget)

import core
from core import S, TELEGRAM, VERSION, Controller
from i18n import tr

PAL = {
    "dark": dict(bg="#0A0E1A", card="#131A2B", card2="#1B2438", text="#E8EAF6", sub="#A9B1CC",
                 border="#263050", primary="#8D9BFF", teal="#3DDBC4", amber="#FFB84D", danger="#FF8A8A", pc="#2A3487"),
    "light": dict(bg="#F4F6FC", card="#FFFFFF", card2="#EEF1FA", text="#151A2C", sub="#586080",
                  border="#DDE2F0", primary="#4F5BD5", teal="#0FA58F", amber="#D98200", danger="#D93A3A", pc="#E0E3FF"),
}


def pal():
    return PAL.get(S.theme, PAL["dark"])


def L(key, **kw):
    return tr(S.language, key, **kw)


def qss():
    p = pal()
    return f"""
    * {{ font-family: 'Segoe UI', Tahoma, sans-serif; font-size: 13px; color: {p['text']}; }}
    QDialog, #root {{ background: transparent; }}
    #dlg {{ background: {p['bg']}; }}
    QLabel {{ background: transparent; }}
    #sub {{ color: {p['sub']}; }}
    #card {{ background: {p['card']}; border: 1px solid {p['border']}; border-radius: 14px; }}
    #cardTitle {{ color: {p['sub']}; font-size: 11px; }}
    #cardValue {{ font-size: 15px; font-weight: 600; }}
    #section {{ color: {p['primary']}; font-weight: 700; font-size: 12px; margin-top: 10px; }}
    QPushButton {{ background: {p['card']}; border: 1px solid {p['border']}; border-radius: 10px; padding: 7px 14px; }}
    QPushButton:hover {{ background: {p['card2']}; }}
    QPushButton:disabled {{ color: {p['sub']}; }}
    QPushButton#icon {{ border: none; background: transparent; padding: 4px 9px; border-radius: 8px; font-size: 15px; }}
    QPushButton#icon:hover {{ background: {p['card2']}; }}
    QPushButton#seg {{ border-radius: 10px; border: none; background: transparent; padding: 8px 0; color: {p['sub']}; }}
    QPushButton#seg[on="true"] {{ background: {p['primary']}; color: {p['bg']}; font-weight: 700; }}
    QFrame#segBox {{ background: {p['card']}; border: 1px solid {p['border']}; border-radius: 12px; }}
    QComboBox, QLineEdit, QSpinBox {{ background: {p['card']}; border: 1px solid {p['border']}; border-radius: 10px;
        padding: 6px 10px; min-height: 20px; selection-background-color: {p['primary']}; }}
    QComboBox:disabled, QLineEdit:disabled, QSpinBox:disabled {{ color: {p['sub']}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{ background: {p['card']}; border: 1px solid {p['border']};
        selection-background-color: {p['primary']}; selection-color: {p['bg']}; outline: none; }}
    QCheckBox {{ spacing: 8px; }}
    QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 6px; border: 1px solid {p['border']}; background: {p['card']}; }}
    QCheckBox::indicator:checked {{ background: {p['primary']}; border-color: {p['primary']}; }}
    QPushButton#chip {{ border-radius: 16px; padding: 6px 14px; background: transparent; }}
    QPushButton#chip[on="true"] {{ background: {p['pc']}; border-color: {p['primary']}; color: {p['primary']}; font-weight: 600; }}
    QPushButton#link {{ border: none; background: transparent; color: {p['primary']}; font-weight: 600; font-size: 14px; }}
    QPushButton#link:hover {{ background: {p['card2']}; }}
    QPushButton#row {{ background: {p['card2']}; border: none; border-radius: 12px; padding: 12px 14px; text-align: left; }}
    QPushButton#pill {{ background: {p['pc']}; border: none; border-radius: 16px; padding: 7px 16px; color: {p['primary']}; }}
    QPushButton#pill:disabled {{ color: {p['sub']}; }}
    QPushButton#mono {{ background: {p['card']}; border: 1px solid {p['border']}; border-radius: 14px; padding: 10px 14px;
        text-align: left; font-family: Consolas, monospace; font-size: 11px; color: {p['sub']}; }}
    QListWidget {{ background: {p['card']}; border: 1px solid {p['border']}; border-radius: 12px; outline: none; }}
    QListWidget::item {{ padding: 9px 12px; }}
    QListWidget::item:selected {{ background: {p['pc']}; color: {p['primary']}; }}
    QPlainTextEdit {{ background: {p['card']}; border: 1px solid {p['border']}; border-radius: 12px;
        font-family: Consolas, monospace; font-size: 11px; }}
    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{ width: 8px; background: transparent; }}
    QScrollBar::handle:vertical {{ background: {p['border']}; border-radius: 4px; min-height: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QMenu {{ background: {p['card']}; border: 1px solid {p['border']}; padding: 4px; }}
    QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
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


# ---------------------------------------------------------------- widgets
class ConnectButton(QWidget):
    """Round power button: idle ring, spinning arc while busy, soft pulse while connected."""

    def __init__(self, on_click):
        super().__init__()
        self.setFixedSize(190, 190)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._click = on_click
        self.phase = "idle"
        self._t = 0.0
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
        p = pal()
        qp = QPainter(self)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        busy = self.phase in ("connecting", "reconnecting", "stopping")
        live = self.phase == "connected"
        teal, prim, amber = QColor(p["teal"]), QColor(p["primary"]), QColor(p["amber"])

        if live:  # glow
            pulse = 0.5 + 0.5 * math.sin(self._t * 2.2)
            g = QRadialGradient(c, 92)
            col = QColor(teal)
            col.setAlpha(int(60 + 50 * pulse))
            g.setColorAt(0.55, col)
            col.setAlpha(0)
            g.setColorAt(1.0, col)
            qp.setPen(Qt.PenStyle.NoPen)
            qp.setBrush(g)
            qp.drawEllipse(c, 92, 92)

        r = 68
        rect = QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        if live:
            grad.setColorAt(0, teal)
            grad.setColorAt(1, prim)
        elif busy:
            grad.setColorAt(0, QColor(p["card2"]))
            grad.setColorAt(1, QColor(p["card"]))
        else:
            grad.setColorAt(0, QColor(p["card2"]))
            grad.setColorAt(1, QColor(p["card"]))
        qp.setPen(QPen(QColor(p["border"]), 1))
        qp.setBrush(grad)
        qp.drawEllipse(rect)

        if busy:  # spinning arc
            pen = QPen(amber, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            qp.setPen(pen)
            qp.setBrush(Qt.BrushStyle.NoBrush)
            ring = QRectF(c.x() - r - 9, c.y() - r - 9, 2 * r + 18, 2 * r + 18)
            qp.drawArc(ring, int(-self._t * 300 * 16), 100 * 16)
        else:
            ring_col = QColor(teal if live else p["border"])
            qp.setPen(QPen(ring_col, 3))
            qp.setBrush(Qt.BrushStyle.NoBrush)
            qp.drawEllipse(QRectF(c.x() - r - 9, c.y() - r - 9, 2 * r + 18, 2 * r + 18))

        # power icon
        icon_col = QColor(p["bg"]) if live else (amber if busy else QColor(p["sub"]))
        qp.setPen(QPen(icon_col, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        ir = 24
        qp.drawArc(QRectF(c.x() - ir, c.y() - ir + 3, 2 * ir, 2 * ir), 120 * 16, 300 * 16)
        qp.drawLine(QPointF(c.x(), c.y() - ir - 4), QPointF(c.x(), c.y() - 2))


class StatCard(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 10, 14, 10)
        v.setSpacing(2)
        self.t = QLabel()
        self.t.setObjectName("cardTitle")
        self.v = QLabel("—")
        self.v.setObjectName("cardValue")
        v.addWidget(self.t)
        v.addWidget(self.v)


class Segmented(QFrame):
    def __init__(self, items, on_change):
        super().__init__()
        self.setObjectName("segBox")
        h = QHBoxLayout(self)
        h.setContentsMargins(4, 4, 4, 4)
        h.setSpacing(4)
        self.btns, self._cb = {}, on_change
        for key in items:
            b = QPushButton()
            b.setObjectName("seg")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, k=key: self._cb(k))
            self.btns[key] = b
            h.addWidget(b)

    def set_value(self, value, labels):
        for k, b in self.btns.items():
            b.setText(labels[k])
            b.setProperty("on", "true" if k == value else "false")
            b.style().unpolish(b)
            b.style().polish(b)


# ---------------------------------------------------------------- dialogs
class Dialog(QDialog):
    def __init__(self, parent, title_key):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, False)
        self.setWindowIcon(parent.windowIcon())
        self.title_key = title_key
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft if S.language == "fa" else Qt.LayoutDirection.LeftToRight)
        self.setObjectName("dlg")
        self.setWindowTitle(L(title_key))


class LogsDialog(Dialog):
    def __init__(self, parent, ctl):
        super().__init__(parent, "logs")
        self.ctl = ctl
        self.resize(560, 420)
        v = QVBoxLayout(self)
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(600)
        self.view.setPlainText("\n".join(ctl.logs))
        v.addWidget(self.view)
        h = QHBoxLayout()
        for key, fn in (("copy", self.copy), ("clear", self.clear)):
            b = QPushButton(L(key))
            b.clicked.connect(fn)
            h.addWidget(b)
        h.addStretch()
        b = QPushButton(L("close"))
        b.clicked.connect(self.close)
        h.addWidget(b)
        v.addLayout(h)
        ctl.log.connect(self.view.appendPlainText)
        self.setStyleSheet(qss())

    def copy(self):
        QApplication.clipboard().setText(self.view.toPlainText())

    def clear(self):
        self.ctl.logs.clear()
        self.view.clear()

    def closeEvent(self, e):
        try:
            self.ctl.log.disconnect(self.view.appendPlainText)
        except TypeError:
            pass
        super().closeEvent(e)


class SettingsDialog(Dialog):
    def __init__(self, parent, ctl):
        super().__init__(parent, "settings")
        self.main, self.ctl = parent, ctl
        self.resize(400, 640)
        self.root = QVBoxLayout(self)
        self.build()

    def clear(self):
        while self.root.count():
            it = self.root.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    def build(self):
        self.clear()
        self.setStyleSheet(qss())
        self.setWindowTitle(L("settings"))
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft if S.language == "fa" else Qt.LayoutDirection.LeftToRight)
        locked = self.ctl.running
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setObjectName("dlg")
        self.form = QVBoxLayout(body)
        self.form.setSpacing(8)
        scroll.setWidget(body)
        self.root.addWidget(scroll)
        f = self.form

        def section(key):
            lab = QLabel(L(key))
            lab.setObjectName("section")
            f.addWidget(lab)

        def row(label_key, widget):
            h = QHBoxLayout()
            h.addWidget(QLabel(L(label_key)), 1)
            h.addWidget(widget, 1)
            f.addLayout(h)

        def combo(key, items, label_for=None, locked_=False):
            c = QComboBox()
            for val, text in items:
                c.addItem(text, val)
            c.setCurrentIndex(max(0, c.findData(S.d[key])))
            c.currentIndexChanged.connect(lambda _, c=c, k=key: self.save(k, c.currentData()))
            c.setEnabled(not locked_)
            return c

        def check(key, label_key, locked_=False):
            c = QCheckBox(L(label_key))
            c.setChecked(bool(S.d[key]))
            c.toggled.connect(lambda v, k=key: self.save(k, v))
            c.setEnabled(not locked_)
            f.addWidget(c)

        def text(key, locked_=False):
            e = QLineEdit(str(S.d[key]))
            e.textChanged.connect(lambda v, k=key: self.save(k, v, apply=False))
            e.setEnabled(not locked_)
            return e

        def spin(key, lo, hi, locked_=False):
            e = QSpinBox()
            e.setRange(lo, hi)
            e.setValue(int(S.d[key]))
            e.valueChanged.connect(lambda v, k=key: self.save(k, v, apply=False))
            e.setEnabled(not locked_)
            return e

        section("sec_general")
        row("language", combo("language", [("fa", "فارسی"), ("en", "English")]))
        row("theme", combo("theme", [("dark", L("dark")), ("light", L("light"))]))
        check("autostart", "autostart")
        check("auto_connect", "auto_connect")
        check("start_minimized", "start_min")
        check("close_to_tray", "close_tray")

        section("sec_conn")
        if locked:
            note = QLabel(L("locked"))
            note.setObjectName("sub")
            note.setWordWrap(True)
            f.addWidget(note)
        row("carrier", combo("carrier", [("h2", "HTTP/2 (TCP)"), ("h3", "HTTP/3 (QUIC)")], locked_=locked))
        row("scan", combo("scan", [(x, x) for x in ("turbo", "balanced", "thorough", "verified", "ironclad")], locked_=locked))
        row("noize", combo("noize", [("default", L("default"))] + [(x, x) for x in ("off", "light", "firewall", "balanced", "gfw", "aggressive")], locked_=locked))
        row("ipv", combo("ip_version", [("4", "IPv4"), ("6", "IPv6"), ("dual", "IPv4 + IPv6")], locked_=locked))
        row("dns", text("dns", locked))
        row("endpoint", text("endpoint", locked))
        row("endpoint2", text("endpoint2", locked))
        check("quick_reconnect", "quick", locked)
        check("fresh_after_drop", "fresh", locked)
        check("system_proxy", "sys_proxy", locked)

        section("sec_net")
        row("socks", spin("socks_port", 1024, 65535, locked))
        row("http", spin("http_port", 1024, 65535, locked))
        row("mtu", spin("mtu", 1280, 9000, locked))
        row("stack", combo("tun_stack", [("gvisor", "gVisor"), ("system", "system"), ("mixed", "mixed")], locked_=locked))

        section("sec_adv")
        row("tries", spin("max_tries", 1, 999, locked))
        row("pingfails", spin("ping_fails", 1, 20, locked))
        row("perf", combo("perf", [(x, x) for x in ("auto", "low", "medium", "high")], locked_=locked))
        row("extra", text("extra_args", locked))
        f.addStretch()

        b = QPushButton(L("close"))
        b.clicked.connect(self.close)
        self.root.addWidget(b)

    def save(self, key, value, apply=True):
        S.set(**{key: value})
        if key == "autostart":
            core.set_autostart(bool(value))
        if apply and key in ("language", "theme"):
            self.main.refresh()
            QTimer.singleShot(0, self.build)
        elif apply and key in ("socks_port", "http_port"):
            self.main.refresh()


# ---------------------------------------------------------------- main window
REGIONS = {
    "AT": ("Austria", "اتریش"), "AU": ("Australia", "استرالیا"), "BE": ("Belgium", "بلژیک"),
    "BG": ("Bulgaria", "بلغارستان"), "BR": ("Brazil", "برزیل"), "CA": ("Canada", "کانادا"),
    "CH": ("Switzerland", "سوئیس"), "CZ": ("Czechia", "چک"), "DE": ("Germany", "آلمان"),
    "DK": ("Denmark", "دانمارک"), "EE": ("Estonia", "استونی"), "ES": ("Spain", "اسپانیا"),
    "FI": ("Finland", "فنلاند"), "FR": ("France", "فرانسه"), "GB": ("United Kingdom", "بریتانیا"),
    "HR": ("Croatia", "کرواسی"), "HU": ("Hungary", "مجارستان"), "IE": ("Ireland", "ایرلند"),
    "IN": ("India", "هند"), "IT": ("Italy", "ایتالیا"), "JP": ("Japan", "ژاپن"), "LV": ("Latvia", "لتونی"),
    "NL": ("Netherlands", "هلند"), "NO": ("Norway", "نروژ"), "PL": ("Poland", "لهستان"),
    "RO": ("Romania", "رومانی"), "RS": ("Serbia", "صربستان"), "SE": ("Sweden", "سوئد"),
    "SG": ("Singapore", "سنگاپور"), "SK": ("Slovakia", "اسلواکی"), "UA": ("Ukraine", "اوکراین"),
    "US": ("United States", "ایالات متحده"),
}


def region_name(cc):
    n = REGIONS.get(cc.upper())
    return f"{cc.upper()} · {n[1] if S.language == 'fa' else n[0]}" if n else cc.upper()


def active_label():
    r = core.route_of(S)
    proto = dict(core.PROTOCOLS)[S.protocol]
    return {"aether": proto, "aether_psiphon": f"{proto} → Psiphon", "aether_tor": f"{proto} → Tor",
            "psiphon_reverse": "Psiphon → MASQUE (HTTP/2)", "tor_reverse": "Tor → MASQUE (HTTP/2)"}.get(r.name, r.label)


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


class RegionDialog(Dialog):
    def __init__(self, parent, current, on_pick):
        super().__init__(parent, "pick_region")
        self.resize(340, 520)
        self._pick = on_pick
        v = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.addItem("🌐  " + L("region_auto"))
        self.list.item(0).setData(Qt.ItemDataRole.UserRole, "")
        for cc in REGIONS:
            self.list.addItem(region_name(cc))
            self.list.item(self.list.count() - 1).setData(Qt.ItemDataRole.UserRole, cc)
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.ItemDataRole.UserRole) == current.upper():
                self.list.setCurrentRow(i)
        self.list.itemClicked.connect(self.picked)
        v.addWidget(self.list)
        self.setStyleSheet(qss())

    def picked(self, item):
        self._pick(item.data(Qt.ItemDataRole.UserRole))
        self.close()


class MainWindow(QWidget):
    pinged = pyqtSignal(object)

    def __init__(self, ctl: Controller):
        super().__init__()
        self.ctl = ctl
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(410, 740)
        self.setWindowTitle("8 VPN")
        self.icon = QIcon(core.resource("assets", "icon.png"))
        self.setWindowIcon(self.icon)
        self._drag = None
        self._since = None
        self._err = ""
        self._reason = ""
        self._attempt, self._tries = 0, 3
        self._ping, self._rx, self._tx, self._speed, self._exit = -1, 0.0, 0.0, -1.0, ""
        self._panel_open = False
        self._testing, self._test_res = False, ""
        self._logs = self._settings = self._region = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.body = QFrame()
        self.body.setObjectName("root")
        outer.addWidget(self.body)
        root = QVBoxLayout(self.body)
        root.setContentsMargins(18, 12, 10, 12)
        root.setSpacing(6)

        # ---- title bar (fixed)
        top = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(self.icon.pixmap(30, 30))
        title = QLabel("8 VPN")
        title.setStyleSheet("font-size:19px;font-weight:700;")
        top.addWidget(logo)
        top.addWidget(title)
        top.addStretch()
        self.b_logs, self.b_set = QPushButton(), QPushButton()
        for b, fn in ((self.b_logs, self.open_logs), (self.b_set, self.open_settings)):
            b.setObjectName("link")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(fn)
            top.addWidget(b)
        bmin, bx = QPushButton("—"), QPushButton("✕")
        for b, fn in ((bmin, self.showMinimized), (bx, self.close)):
            b.setObjectName("icon")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(fn)
            top.addWidget(b)
        root.addLayout(top)

        # ---- scrolling content
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("root")
        sc.setWidget(inner)
        root.addWidget(sc)
        v = QVBoxLayout(inner)
        v.setContentsMargins(0, 0, 8, 0)
        v.setSpacing(10)

        self.btn = ConnectButton(self.toggle)
        v.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignHCenter)

        self.pill = QFrame()
        self.pill.setObjectName("pillbox")
        pl = QHBoxLayout(self.pill)
        pl.setContentsMargins(14, 5, 14, 5)
        pl.setSpacing(8)
        self.dot, self.status = QLabel("●"), QLabel()
        pl.addWidget(self.dot)
        pl.addWidget(self.status)
        v.addWidget(self.pill, 0, Qt.AlignmentFlag.AlignHCenter)
        self.sub = QLabel()
        self.sub.setWordWrap(True)
        self.sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop = QLabel()
        self.drop.setObjectName("sub")
        self.drop.setWordWrap(True)
        self.drop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.sub)
        v.addWidget(self.drop)

        # ---- stats
        self.stats = QFrame()
        self.stats.setObjectName("card")
        sl = QHBoxLayout(self.stats)
        sl.setContentsMargins(6, 14, 6, 14)
        self.st = {}
        for key, glyph in (("ping", "⚡"), ("download", "↓"), ("upload", "↑"), ("link_speed", "◉")):
            col = QVBoxLayout()
            col.setSpacing(3)
            g, val, lab = QLabel(glyph), QLabel("—"), QLabel()
            g.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val.setStyleSheet("font-size:13px;font-weight:600;")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setObjectName("cardTitle")
            for w in (g, val, lab):
                col.addWidget(w)
            sl.addLayout(col, 1)
            self.st[key] = (g, val, lab)
        v.addWidget(self.stats)

        self.proxy_card = QLabel()
        self.proxy_card.setObjectName("card")
        self.proxy_card.setStyleSheet("font-family:Consolas,monospace;font-size:11px;padding:12px;")
        v.addWidget(self.proxy_card)

        # ---- actions (connected only)
        self.actions = QWidget()
        al = QHBoxLayout(self.actions)
        al.setContentsMargins(0, 0, 0, 0)
        self.b_test, self.b_rescan = QPushButton(), QPushButton()
        for b in (self.b_test, self.b_rescan):
            b.setObjectName("pill")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            al.addWidget(b)
        self.test_lbl = QLabel()
        self.test_lbl.setObjectName("sub")
        al.addWidget(self.test_lbl)
        al.addStretch()
        self.b_test.clicked.connect(self.run_ping)
        self.b_rescan.clicked.connect(ctl.rescan)
        self.pinged.connect(self.on_pinged)
        v.addWidget(self.actions)

        # ---- setup card
        self.setup = QFrame()
        self.setup.setObjectName("card")
        sv = QVBoxLayout(self.setup)
        sv.setContentsMargins(12, 12, 12, 12)
        sv.setSpacing(10)
        self.seg_mode = Segmented(["vpn", "proxy"], self.set_mode)
        self.seg_fam = Segmented(["aether", "psiphon", "tor"], self.set_family)
        self.summary = QPushButton()
        self.summary.setObjectName("row")
        self.summary.setCursor(Qt.CursorShape.PointingHandCursor)
        self.summary.clicked.connect(self.toggle_panel)
        self.hint = QLabel()
        self.hint.setObjectName("sub")
        self.hint.setWordWrap(True)
        self.panel = QWidget()
        self.panel_l = QVBoxLayout(self.panel)
        self.panel_l.setContentsMargins(2, 0, 2, 0)
        self.panel_l.setSpacing(10)
        for w in (self.seg_mode, self.seg_fam, self.summary, self.hint, self.panel):
            sv.addWidget(w)
        v.addWidget(self.setup)

        # ---- recent log + footer
        self.logcard = QPushButton()
        self.logcard.setObjectName("mono")
        self.logcard.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logcard.clicked.connect(self.open_logs)
        v.addWidget(self.logcard)
        foot = QHBoxLayout()
        self.tg = QPushButton()
        self.tg.setObjectName("link")
        self.tg.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tg.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(TELEGRAM)))
        ver = QLabel(f"v{VERSION}")
        ver.setObjectName("sub")
        foot.addWidget(self.tg)
        foot.addStretch()
        foot.addWidget(ver)
        v.addLayout(foot)
        v.addStretch()

        # ---- controller signals
        ctl.status.connect(self.on_status)
        ctl.message.connect(self.on_message)
        ctl.ping.connect(self.on_ping)
        ctl.traffic.connect(self.on_traffic)
        ctl.exit_info.connect(self.on_exit)
        ctl.speed.connect(self.on_speed)
        ctl.log.connect(self.on_log)

        # ---- tray
        self.tray = QSystemTrayIcon(self.icon, self)
        self.tray.activated.connect(lambda r: self.toggle_window() if r == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray_menu = QMenu()
        self.a_show, self.a_toggle, self.a_quit = QAction(), QAction(), QAction()
        self.a_show.triggered.connect(self.show_window)
        self.a_toggle.triggered.connect(self.toggle)
        self.a_quit.triggered.connect(self.quit_app)
        for a in (self.a_show, self.a_toggle):
            self.tray_menu.addAction(a)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.a_quit)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.show()

        self.clock = QTimer(self)
        self.clock.timeout.connect(self.update_status_line)
        self.clock.start(1000)

        self.refresh()

    # ---- window chrome
    def paintEvent(self, _):
        p = pal()
        qp = QPainter(self)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 20, 20)
        qp.fillPath(path, QColor(p["bg"]))
        qp.setPen(QPen(QColor(p["border"]), 1))
        qp.drawPath(path)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() < 56:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _):
        self._drag = None

    # ---- state
    @property
    def idle(self):
        return self.ctl.phase == "idle"

    def _set(self, **kw):
        for k, val in kw.items():
            setattr(self, "_" + k, val)
        self.update_stats()
        self.update_status_line()

    def refresh(self):
        """Full re-render: language, theme, settings."""
        QApplication.instance().setStyleSheet(qss())
        rtl = S.language == "fa"
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft if rtl else Qt.LayoutDirection.LeftToRight)
        self.b_logs.setText(L("logs"))
        self.b_set.setText(L("settings"))
        self.tg.setText("✈  @Clubapp8")
        self.b_test.setText(L("ping_testing") if self._testing else L("ping_test"))
        self.b_rescan.setText("↻  " + L("rescan"))
        for key, (g, _, lab) in self.st.items():
            lab.setText(L(key))
            g.setStyleSheet(f"color:{pal()['teal']};font-size:15px;")
        self.a_show.setText(L("tray_show"))
        self.a_quit.setText(L("tray_quit"))
        self.seg_mode.set_value(S.mode, {"vpn": L("vpn"), "proxy": L("proxy")})
        self.seg_fam.set_value(core.route_of(S).family,
                               {"aether": L("core_aether"), "psiphon": L("core_psiphon"), "tor": L("core_tor")})
        self.build_panel()
        self.update_all()
        self.update()

    def update_all(self):
        ph, idle = self.ctl.phase, self.idle
        live = ph == "connected"
        color = {"connected": pal()["teal"], "idle": pal()["sub"]}.get(ph, pal()["amber"])
        qc = QColor(color)
        self.pill.setStyleSheet(f"#pillbox {{ background: rgba({qc.red()},{qc.green()},{qc.blue()},0.14); border-radius: 15px; }}")
        self.dot.setStyleSheet(f"color:{color};font-size:10px;")
        self.status.setStyleSheet(f"color:{color};font-size:15px;font-weight:600;")
        self.status.setText(L({"idle": "idle"}.get(ph, ph)))
        self.btn.set_phase(ph)
        self.proxy_card.setVisible(S.mode == "proxy")
        self.proxy_card.setText(L("proxy_info", a=f"127.0.0.1:{S.socks_port}") +
                                (("    " + L("http_info", a=f"127.0.0.1:{S.http_port}")) if S.system_proxy else ""))
        self.actions.setVisible(live)
        self.b_rescan.setVisible(core.route_of(S).family == "aether")
        self.hint.setVisible(not idle)
        self.hint.setText(L("locked_hint"))
        self.panel.setVisible(self._panel_open and idle)
        mode = L("mode_summary_vpn") if S.mode == "vpn" else L("mode_summary_proxy")
        arrow = "🔒" if not idle else ("▴" if self._panel_open else "▾")
        self.summary.setText(f"{mode}  ·  {active_label()}    {arrow}")
        self.summary.setEnabled(idle)
        for seg in (self.seg_mode, self.seg_fam):
            for b in seg.btns.values():
                b.setEnabled(idle)
        self.a_toggle.setText(L("tray_disconnect") if not idle else L("tray_connect"))
        self.drop.setText(L("last_drop", r=self._reason) if self._reason and idle else "")
        self.update_stats()
        self.update_status_line()
        self.update_logcard()

    def update_stats(self):
        live = self.ctl.phase == "connected"
        vals = {
            "ping": L("ms", v=self._ping) if live and self._ping >= 0 else "—",
            "download": fmt_rate(self._rx) if live and S.mode == "vpn" else "—",
            "upload": fmt_rate(self._tx) if live and S.mode == "vpn" else "—",
            "link_speed": (fmt_rate(self._speed) if self._speed >= 0 else "…") if live else "—",
        }
        for k, t in vals.items():
            self.st[k][1].setText(t)

    def update_status_line(self):
        ph = self.ctl.phase
        amber, danger, sub = pal()["amber"], pal()["danger"], pal()["sub"]
        if ph == "reconnecting" or (ph == "connecting" and self._attempt > 1):
            txt, col = L("attempt", a=self._attempt, t=self._tries), amber
        elif ph == "idle" and self._err:
            txt, col = self._err, danger
        elif ph == "idle":
            txt, col = L("tap"), sub
        elif ph == "connected":
            t = int(time.time() - self._since) if self._since else 0
            parts = [active_label()]
            if self._exit:
                parts.append(self._exit)
            parts.append(f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}")
            txt, col = "  ·  ".join(parts), sub
        else:
            txt, col = "", sub
        self.sub.setText(txt)
        self.sub.setStyleSheet(f"color:{col};")

    def update_logcard(self):
        lines = list(self.ctl.logs)[-2:]
        self.logcard.setVisible(bool(lines))
        fm = self.logcard.fontMetrics()
        self.logcard.setText("\n".join(fm.elidedText(l, Qt.TextElideMode.ElideRight, 330) for l in lines))
        self.logcard.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

    # ---- panel (route / protocol / region ...)
    def chips(self, items, current, on_pick):
        w = QWidget()
        w.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        fl = FlowLayout(w)
        for val, text in items:
            b = QPushButton(text)
            b.setObjectName("chip")
            b.setProperty("on", "true" if val == current else "false")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, x=val: on_pick(x))
            fl.addWidget(b)
        return w

    def field(self, title, widget):
        box = QWidget()
        bl = QVBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(6)
        lab = QLabel(title)
        lab.setObjectName("sub")
        bl.addWidget(lab)
        bl.addWidget(widget)
        return box

    def region_button(self):
        cc = S.psiphon_region
        b = QPushButton(("🌐  " + L("region_auto")) if not cc else region_name(cc))
        b.setObjectName("row")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(self.pick_region)
        return self.field(L("region"), b)

    def build_panel(self):
        while self.panel_l.count():
            it = self.panel_l.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        r = core.route_of(S)
        add = self.panel_l.addWidget
        route_pick = lambda x: self.setv(route=x)
        if r.family == "aether":
            add(self.field(L("route"), self.chips([(k, ROUTE_LABEL[k]) for k in ("aether", "aether_psiphon", "aether_tor")], r.name, route_pick)))
            if r.name == "aether_psiphon":
                add(self.region_button())
            add(self.field(L("protocol"), self.chips(core.PROTOCOLS, S.protocol, lambda x: self.setv(protocol=x))))
            if S.protocol in ("masque", "mim"):
                add(self.field(L("transport"), self.chips([("h3", "HTTP/3 (QUIC)"), ("h2", "HTTP/2 (TCP)")], S.carrier, lambda x: self.setv(carrier=x))))
        elif r.family == "psiphon":
            add(self.field(L("route"), self.chips([(k, ROUTE_LABEL[k]) for k in ("psiphon_only", "psiphon_reverse")], r.name, route_pick)))
            add(self.region_button())
            add(self.field(L("psiphon_mode"), self.chips([("auto", L("auto")), ("cdn", "CDN")], S.psiphon_mode, lambda x: self.setv(psiphon_mode=x))))
        else:
            add(self.field(L("route"), self.chips([(k, ROUTE_LABEL[k]) for k in ("tor_only", "tor_reverse")], r.name, route_pick)))
            add(self.field(L("bridges"), self.chips([("auto", L("auto")), ("always", L("always")), ("never", L("never"))], S.tor_bridges, lambda x: self.setv(tor_bridges=x))))

    def setv(self, **kw):
        if not self.idle:
            return
        S.set(**kw)
        self.refresh()

    def set_mode(self, mode):
        self.setv(mode=mode)

    def set_family(self, fam):
        if core.route_of(S).family != fam:
            self.setv(route={"aether": "aether", "psiphon": "psiphon_only", "tor": "tor_only"}[fam])

    def toggle_panel(self):
        self._panel_open = not self._panel_open
        self.update_all()

    def pick_region(self):
        if self.idle:
            self._region = RegionDialog(self, S.psiphon_region, lambda cc: self.setv(psiphon_region=cc))
            self._region.show()

    # ---- actions
    def toggle(self):
        if self.ctl.phase == "idle":
            self._err = ""
            if S.mode == "vpn" and not core.is_admin():
                self._err = L("need_admin_ask")
                self.update_status_line()
                if core.relaunch_as_admin(["--connect"]):
                    QTimer.singleShot(300, self.quit_app)
                else:
                    self._err = L("admin_denied")
                    self.update_status_line()
                return
            self.ctl.start()
        elif self.ctl.phase != "stopping":
            self.ctl.stop()

    def run_ping(self):
        if self._testing or self.ctl.phase != "connected":
            return
        self._testing = True
        self.b_test.setText(L("ping_testing"))
        port = core.exit_port(S)

        def work():
            r = core.socks_get(port, "cp.cloudflare.com", "/generate_204", 8)
            self.pinged.emit(r[0] if r else None)
        import threading
        threading.Thread(target=work, daemon=True).start()

    def on_pinged(self, ms):
        self._testing = False
        self.b_test.setText(L("ping_test"))
        if ms is None:
            self.test_lbl.setText(L("ping_none"))
        else:
            self._ping = ms
            self.test_lbl.setText(L("ms", v=ms))
            self.update_stats()

    def open_logs(self):
        self._logs = LogsDialog(self, self.ctl)
        self._logs.show()

    def open_settings(self):
        self._settings = SettingsDialog(self, self.ctl)
        self._settings.show()

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def toggle_window(self):
        self.hide() if self.isVisible() else self.show_window()

    def quit_app(self):
        self.tray.hide()
        self.ctl.shutdown()
        core.restore_system_proxy()
        QApplication.quit()

    def closeEvent(self, e):
        e.ignore()
        if S.close_to_tray and self.tray.isVisible():
            self.hide()
        else:
            self.quit_app()

    # ---- controller callbacks
    def on_status(self, phase, attempt, tries):
        if attempt:
            self._attempt, self._tries = attempt, tries
        self._since = (self._since or time.time()) if phase == "connected" else None
        if phase == "connected":
            self._reason = ""
        if phase == "idle":
            self._ping, self._rx, self._tx, self._speed, self._exit = -1, 0.0, 0.0, -1.0, ""
            self._test_res = ""
            self.test_lbl.setText("")
        self.update_all()

    def on_ping(self, ms): self._set(ping=ms)
    def on_traffic(self, rx, tx): self._set(rx=rx, tx=tx)
    def on_exit(self, text): self._set(exit=text)
    def on_speed(self, bps): self._set(speed=bps)
    def on_log(self, _line): self.update_logcard()

    def on_message(self, key):
        if not key or key == "stopped":
            self._err = ""
        elif key in ("ping_failed", "core_exited", "tun_exited", "rescan"):
            self._reason = L("rescan_msg" if key == "rescan" else key)
            self._err = ""
        else:
            self._err = L(key)
        self.update_status_line()


ROUTE_LABEL = {k: r.label for k, r in core.ROUTES.items()}


# ---------------------------------------------------------------- entry
def single_instance(wait_s=0.0):
    """Named mutex so only one copy runs. Returns False if another copy is alive."""
    if not core.IS_WIN:
        return True
    k = ctypes.windll.kernel32
    end = time.time() + wait_s
    while True:
        h = k.CreateMutexW(None, False, "Local\\8VPN_Windows_Single")
        if k.GetLastError() != 183:  # ERROR_ALREADY_EXISTS
            single_instance.handle = h
            return True
        k.CloseHandle(h)
        if time.time() >= end:
            return False
        time.sleep(0.2)


def main():
    argv = sys.argv[1:]
    if not single_instance(6.0 if "--connect" in argv else 0.0):
        return 0
    if core.IS_WIN:  # own taskbar identity + icon
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Mrmmd2004.8VPN")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Segoe UI", 10))
    ctl = Controller()
    core.restore_system_proxy()  # undo a proxy left behind by a crash
    w = MainWindow(ctl)
    app.aboutToQuit.connect(ctl.shutdown)
    if "--minimized" not in argv and not S.start_minimized:
        w.show()
    if "--connect" in argv or S.auto_connect:
        QTimer.singleShot(700, w.toggle)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
