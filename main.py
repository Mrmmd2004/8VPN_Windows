import ctypes
import math
import sys
import time

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl
from PyQt6.QtGui import (QAction, QColor, QDesktopServices, QFont, QIcon, QLinearGradient, QPainter,
                         QPainterPath, QPen, QRadialGradient)
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout,
                             QLabel, QLineEdit, QMenu, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox,
                             QSystemTrayIcon, QVBoxLayout, QWidget)

import core
from core import S, TELEGRAM, VERSION, Controller
from i18n import tr

PAL = {
    "dark": dict(bg="#0A0E1A", card="#131A2B", card2="#1B2438", text="#E8EAF6", sub="#A9B1CC",
                 border="#263050", primary="#8D9BFF", teal="#3DDBC4", amber="#FFB84D", danger="#FF8A8A"),
    "light": dict(bg="#F4F6FC", card="#FFFFFF", card2="#EEF1FA", text="#151A2C", sub="#586080",
                  border="#DDE2F0", primary="#4F5BD5", teal="#0FA58F", amber="#D98200", danger="#D93A3A"),
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
class MainWindow(QWidget):
    def __init__(self, ctl: Controller):
        super().__init__()
        self.ctl = ctl
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(380, 660)
        self.setWindowTitle("8 VPN")
        self.icon = QIcon(core.resource("assets", "icon.png"))
        self.setWindowIcon(self.icon)
        self._drag = None
        self._since = None
        self._msg_key = ""
        self._logs = self._settings = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.body = QFrame()
        self.body.setObjectName("root")
        outer.addWidget(self.body)
        v = QVBoxLayout(self.body)
        v.setContentsMargins(18, 12, 18, 12)
        v.setSpacing(10)

        # title bar
        top = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(self.icon.pixmap(26, 26))
        title = QLabel("8 VPN")
        title.setStyleSheet("font-size:16px;font-weight:700;")
        top.addWidget(logo)
        top.addWidget(title)
        top.addStretch()
        self.b_logs, self.b_set = QPushButton(), QPushButton()
        for b, fn in ((self.b_logs, self.open_logs), (self.b_set, self.open_settings)):
            b.setObjectName("icon")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(fn)
            top.addWidget(b)
        bmin, bx = QPushButton("—"), QPushButton("✕")
        for b, fn in ((bmin, self.showMinimized), (bx, self.close)):
            b.setObjectName("icon")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(fn)
            top.addWidget(b)
        v.addLayout(top)

        # connect button + status
        v.addSpacing(6)
        self.btn = ConnectButton(self.toggle)
        v.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignHCenter)
        self.status = QLabel()
        self.status.setStyleSheet("font-size:21px;font-weight:700;")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub = QLabel()
        self.sub.setObjectName("sub")
        self.sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.note.setStyleSheet(f"color:{pal()['amber']};")
        v.addWidget(self.status)
        v.addWidget(self.sub)
        v.addWidget(self.note)
        v.addStretch()

        # mode + protocol
        self.seg = Segmented(["vpn", "proxy"], self.set_mode)
        v.addWidget(self.seg)
        row = QHBoxLayout()
        self.lbl_proto = QLabel()
        self.lbl_proto.setObjectName("sub")
        self.proto = QComboBox()
        for k, name in core.PROTOCOLS:
            self.proto.addItem(name, k)
        self.proto.currentIndexChanged.connect(lambda _: S.set(protocol=self.proto.currentData()))
        row.addWidget(self.lbl_proto)
        row.addWidget(self.proto, 1)
        v.addLayout(row)

        # stats
        grid = QGridLayout()
        grid.setSpacing(8)
        self.c_ping, self.c_ip, self.c_dl, self.c_ul = StatCard(), StatCard(), StatCard(), StatCard()
        grid.addWidget(self.c_ping, 0, 0)
        grid.addWidget(self.c_ip, 0, 1)
        grid.addWidget(self.c_dl, 1, 0)
        grid.addWidget(self.c_ul, 1, 1)
        v.addLayout(grid)

        # footer
        foot = QHBoxLayout()
        self.tg = QPushButton()
        self.tg.setObjectName("icon")
        self.tg.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tg.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(TELEGRAM)))
        ver = QLabel(f"v{VERSION}")
        ver.setObjectName("sub")
        foot.addWidget(self.tg)
        foot.addStretch()
        self.b_rescan = QPushButton()
        self.b_rescan.setObjectName("icon")
        self.b_rescan.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_rescan.clicked.connect(ctl.rescan)
        foot.addWidget(self.b_rescan)
        foot.addWidget(ver)
        v.addLayout(foot)

        # signals
        ctl.status.connect(self.on_status)
        ctl.message.connect(self.on_message)
        ctl.ping.connect(self.on_ping)
        ctl.traffic.connect(self.on_traffic)
        ctl.exit_info.connect(self.on_exit)

        # tray
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
        self.clock.timeout.connect(self.tick)
        self.clock.start(1000)

        self.refresh()
        self.on_status("idle", 0, 0)

    # ---- painting a rounded window
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
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() < 52:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _):
        self._drag = None

    # ---- text / theme
    def refresh(self):
        QApplication.instance().setStyleSheet(qss())
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft if S.language == "fa" else Qt.LayoutDirection.LeftToRight)
        self.b_logs.setText(L("logs"))
        self.b_set.setText(L("settings"))
        self.tg.setText("✈  @Clubapp8")
        self.b_rescan.setText("↻  " + L("rescan"))
        self.lbl_proto.setText(L("protocol"))
        self.c_ping.t.setText(L("ping"))
        self.c_ip.t.setText(L("exit_ip"))
        self.c_dl.t.setText(L("download"))
        self.c_ul.t.setText(L("upload"))
        self.note.setStyleSheet(f"color:{pal()['amber']};")
        self.seg.set_value(S.mode, {"vpn": L("vpn"), "proxy": L("proxy")})
        self.proto.blockSignals(True)
        self.proto.setCurrentIndex(max(0, self.proto.findData(S.protocol)))
        self.proto.blockSignals(False)
        self.a_show.setText(L("tray_show"))
        self.a_quit.setText(L("tray_quit"))
        self.on_status(self.ctl.phase, 0, S.tries())
        self.on_message(self._msg_key)
        self.update()

    # ---- actions
    def set_mode(self, mode):
        if self.ctl.phase != "idle":
            return
        S.set(mode=mode)
        self.seg.set_value(mode, {"vpn": L("vpn"), "proxy": L("proxy")})

    def toggle(self):
        if self.ctl.phase == "idle":
            if S.mode == "vpn" and not core.is_admin():
                self.on_message("need_admin_ask")
                if core.relaunch_as_admin(["--connect"]):
                    QTimer.singleShot(300, self.quit_app)
                else:
                    self.on_message("admin_denied")
                return
            self.ctl.start()
        elif self.ctl.phase != "stopping":
            self.ctl.stop()

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
        if S.close_to_tray and self.tray.isVisible():
            e.ignore()
            self.hide()
        else:
            e.ignore()
            self.quit_app()

    # ---- controller callbacks
    def on_status(self, phase, attempt, tries):
        names = {"idle": "idle", "connecting": "connecting", "connected": "connected",
                 "reconnecting": "reconnecting", "stopping": "stopping"}
        self.status.setText(L(names[phase]))
        color = {"connected": pal()["teal"], "idle": pal()["text"]}.get(phase, pal()["amber"])
        self.status.setStyleSheet(f"font-size:21px;font-weight:700;color:{color};")
        self.btn.set_phase(phase)
        if phase == "connected":
            self._since = self._since or time.time()
        else:
            self._since = None
        if phase in ("connecting", "reconnecting") and attempt:
            self.sub.setText(L("attempt", a=attempt, t=tries))
        elif phase == "idle":
            self.sub.setText(L("tap"))
        elif phase == "stopping":
            self.sub.setText("")
        else:
            self.tick()
        busy = phase != "idle"
        self.proto.setEnabled(not busy)
        for b in self.seg.btns.values():
            b.setEnabled(not busy)
        self.b_rescan.setVisible(phase == "connected")
        self.a_toggle.setText(L("tray_disconnect") if busy else L("tray_connect"))
        if phase == "idle":
            self.c_ping.v.setText("—")
            self.c_ip.v.setText("—")
            self.c_dl.v.setText("—")
            self.c_ul.v.setText("—")

    def on_message(self, key):
        self._msg_key = key
        if not key or key == "stopped":
            self.note.setText("")
        else:
            self.note.setText(L("rescan_msg") if key == "rescan" else L(key))

    def on_ping(self, ms):
        self.c_ping.v.setText(L("ms", v=ms) if ms >= 0 else "—")

    def on_traffic(self, rx, tx):
        self.c_dl.v.setText(fmt_rate(rx) if self.ctl.phase == "connected" else "—")
        self.c_ul.v.setText(fmt_rate(tx) if self.ctl.phase == "connected" else "—")

    def on_exit(self, text):
        self.c_ip.v.setText(text or "—")

    def tick(self):
        if self._since and self.ctl.phase == "connected":
            t = int(time.time() - self._since)
            self.sub.setText(f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}   ·   {L('tap_stop')}")


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
