import ctypes
import html
import os
import re
import shutil
import sys
import threading
import time

from PyQt6.QtCore import QPoint, QRectF, QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QDesktopServices, QFont, QIcon, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton, QScrollArea,
                             QSpinBox, QStackedWidget, QSystemTrayIcon, QTextEdit, QVBoxLayout, QWidget)

import core
from core import S, TELEGRAM, VERSION, Controller
from ui_kit import (L, Btn, Card, Chips, ClickCard, ConnectButton, Dot, Icon, IconButton, LogoMark, SectionTitle,
                    Segmented, Sheet, SwitchRow, Tile, flag_pixmap, fmt_rate, paint_icon, pal, qss, rtl)

GITHUB = "https://github.com/Mrmmd2004/8VPN_Windows"
GITHUB_ANDROID = "https://github.com/Mrmmd2004/8vpn"

REGIONS = {
    "AT": ("Austria", "اتریش"), "AU": ("Australia", "استرالیا"), "BE": ("Belgium", "بلژیک"),
    "BG": ("Bulgaria", "بلغارستان"), "BR": ("Brazil", "برزیل"), "CA": ("Canada", "کانادا"),
    "CH": ("Switzerland", "سوئیس"), "CZ": ("Czechia", "چک"), "DE": ("Germany", "آلمان"),
    "DK": ("Denmark", "دانمارک"), "EE": ("Estonia", "استونی"), "ES": ("Spain", "اسپانیا"),
    "FI": ("Finland", "فنلاند"), "FR": ("France", "فرانسه"), "GB": ("United Kingdom", "بریتانیا"),
    "HR": ("Croatia", "کرواسی"), "HU": ("Hungary", "مجارستان"), "IE": ("Ireland", "ایرلند"),
    "ID": ("Indonesia", "اندونزی"), "IN": ("India", "هند"), "IT": ("Italy", "ایتالیا"), "JP": ("Japan", "ژاپن"), "LT": ("Lithuania", "لیتوانی"), "LV": ("Latvia", "لتونی"),
    "NL": ("Netherlands", "هلند"), "NO": ("Norway", "نروژ"), "PL": ("Poland", "لهستان"),
    "RO": ("Romania", "رومانی"), "RS": ("Serbia", "صربستان"), "SE": ("Sweden", "سوئد"),
    "SG": ("Singapore", "سنگاپور"), "SK": ("Slovakia", "اسلواکی"), "UA": ("Ukraine", "اوکراین"),
    "US": ("United States", "ایالات متحده"),
}
ROUTE_LABEL = {k: r.label for k, r in core.ROUTES.items()}


def region_name(cc):
    n = REGIONS.get(cc.upper())
    return f"{n[1] if rtl() else n[0]}  ({cc.upper()})" if n else cc.upper()


def active_label():
    return core.active_label(S)


# ------------------------------------------------------------------ small builders
def card(margins=(16, 14, 16, 14), spacing=12):
    f = Card("card")
    v = QVBoxLayout(f)
    v.setContentsMargins(*margins)
    v.setSpacing(spacing)
    return f, v


def label(text, name=None, wrap=False):
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def field(title, widget):
    box = QWidget()
    v = QVBoxLayout(box)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(8)
    v.addWidget(label(title, "sub"))
    v.addWidget(widget)
    return box


def banner(text):
    """Soft tinted note with an info icon (Android Banner)."""
    f = Card("banner")
    h = QHBoxLayout(f)
    h.setContentsMargins(14, 12, 14, 12)
    h.setSpacing(10)
    h.addWidget(Icon("info", 20, "primary"))
    h.addWidget(label(text, None, True), 1)
    return f


def page_header(title, back, actions=()):
    """Round back button, bold title, optional round action buttons (Android Page)."""
    h = QHBoxLayout()
    h.setContentsMargins(0, 8, 0, 12)
    h.setSpacing(8)
    b = IconButton("back", 42, 2.0)
    b.clicked.connect(back)
    h.addWidget(b)
    h.addSpacing(4)
    h.addWidget(label(title, "page"), 1)
    for a in actions:
        h.addWidget(a)
    return h


def scrolling(widget_layout_owner):
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sc.setWidget(widget_layout_owner)
    return sc


def clear_layout(layout, keep=()):
    """Remove everything from a layout (nested layouts too) and delete the widgets, except those in keep."""
    while layout.count():
        it = layout.takeAt(0)
        sub = it.layout()
        if sub is not None:
            clear_layout(sub, keep)
        w = it.widget()
        if w is not None and w not in keep:
            w.deleteLater()


def dialog_button(text, on_click):
    b = QPushButton(text)
    b.setObjectName("link")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.clicked.connect(on_click)
    return b


class ConfirmSheet(Sheet):
    def __init__(self, parent, title, text, ok_text, on_ok):
        super().__init__(parent, title)
        self.v.addWidget(label(text, "sub", True))
        h = QHBoxLayout()
        h.addStretch()
        h.addWidget(dialog_button(L("cancel"), self.reject))
        h.addWidget(dialog_button(ok_text, lambda: (on_ok(), self.accept())))
        self.v.addLayout(h)


class PickRow(Btn):
    """One row of a picker dialog: flag, name and a check mark on the current choice."""

    def __init__(self, text, cc, on, on_click):
        super().__init__("", "pick", on)
        self.hay = ""
        self.setStyleSheet("QPushButton#pick { padding: 0; }")
        self.setMinimumHeight(44)
        self.clicked.connect(on_click)
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 6, 12, 6)
        h.setSpacing(12)
        flag = QLabel()
        flag.setPixmap(flag_pixmap(cc, 30))
        name = QLabel(text)
        if on:
            name.setStyleSheet(f"color:{pal()['primary']};")
        parts = [flag, name]
        h.addWidget(flag)
        h.addWidget(name, 1)
        if on:
            ck = Icon("check", 18, "primary", 2.6)
            parts.append(ck)
            h.addWidget(ck)
        for w in parts:
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


class RegionSheet(Sheet):
    def __init__(self, parent, current, on_pick):
        super().__init__(parent, L("region"), 380)
        self._pick = on_pick
        self.search = QLineEdit()
        self.search.setPlaceholderText(L("search"))
        self.v.addWidget(self.search)
        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(0, 0, 6, 0)
        bl.setSpacing(2)
        self.rows = []
        cur = current.upper()
        entries = [("", L("region_auto"), "auto")] + [(cc, region_name(cc), " ".join(REGIONS[cc]).lower() + cc.lower()) for cc in REGIONS]
        for cc, text, hay in entries:
            row = PickRow(text, cc, cc == cur, lambda _=False, c=cc: self.picked(c))
            row.hay = hay
            bl.addWidget(row)
            self.rows.append(row)
        bl.addStretch()
        sc = scrolling(body)
        sc.setFixedHeight(320)
        self.v.addWidget(sc)
        self.search.textChanged.connect(self.filter)
        h = QHBoxLayout()
        h.addStretch()
        h.addWidget(dialog_button(L("cancel"), self.reject))
        self.v.addLayout(h)

    def filter(self, q):
        q = q.strip().lower()
        for row in self.rows:
            row.setVisible(not q or q in row.hay)

    def picked(self, cc):
        self._pick(cc)
        self.accept()


class RegionRow(Btn):
    """Flag + country name + chevron, used on Home and in Settings (Android RegionButton)."""

    def __init__(self, on_click, enabled=True):
        super().__init__("", "row")
        self.setStyleSheet("QPushButton#row { padding: 0; }")
        self.setMinimumHeight(48)
        self.setEnabled(enabled)
        self.clicked.connect(on_click)
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 8, 14, 8)
        h.setSpacing(12)
        cc = S.psiphon_region
        flag = QLabel()
        flag.setPixmap(flag_pixmap(cc, 30))
        text = QLabel(region_name(cc) if cc else L("region_auto"))
        chev = Icon("chev_left" if rtl() else "chev_right", 20)
        for w in (flag, text, chev):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        h.addWidget(flag)
        h.addWidget(text, 1)
        h.addWidget(chev)


class SummaryRow(Btn):
    """'VPN · route' line that opens the options; shows a lock while connected."""

    def __init__(self, on_click):
        super().__init__("", "row")
        self.clicked.connect(on_click)
        self.kind = "chevron"
        self.restyle()

    def restyle(self):
        self.setStyleSheet("QPushButton#row { padding: 13px 16px 13px 46px; text-align: right; }" if rtl() else
                           "QPushButton#row { padding: 13px 46px 13px 16px; text-align: left; }")

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        x = 14 if rtl() else self.width() - 34
        paint_icon(p, self.kind, QRectF(x, (self.height() - 20) / 2, 20, 20), QColor(pal()["sub"]), 2.0)


# ------------------------------------------------------------------ pages
class HomePage(QWidget):
    pinged = pyqtSignal(object)

    def __init__(self, win):
        super().__init__()
        self.win, self.ctl = win, win.ctl
        self._err = self._reason = ""
        self._attempt, self._tries = 0, 3
        self._ping, self._rx, self._tx, self._speed, self._exit = -1, 0.0, 0.0, -1.0, ""
        self._since, self._panel_open, self._testing = None, False, False

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 0, 4, 10)
        root.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 8, 12, 0)
        top.setSpacing(8)
        self.logo = LogoMark(36)
        title = QLabel("8 VPN")
        title.setObjectName("title")
        top.addWidget(self.logo)
        top.addSpacing(2)
        top.addWidget(title)
        top.addStretch()
        self.b_logs = IconButton("logs", 42, 2.0)
        self.b_logs.clicked.connect(win.open_logs)
        self.b_set = IconButton("settings", 42, 2.0)
        self.b_set.clicked.connect(win.open_settings)
        top.addWidget(self.b_logs)
        top.addWidget(self.b_set)
        root.addLayout(top)

        inner = QWidget()
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sc.setWidget(inner)
        root.addWidget(sc)
        v = QVBoxLayout(inner)
        v.setContentsMargins(0, 4, 12, 8)
        v.setSpacing(10)

        # hero: connect button + status
        self.btn = ConnectButton(win.toggle)
        v.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignHCenter)

        self.pill = Card("pill")
        pl = QHBoxLayout(self.pill)
        pl.setContentsMargins(14, 6, 14, 6)
        pl.setSpacing(8)
        self.dot, self.status = Dot(8), QLabel()
        self.flag = QLabel()
        self.flag.hide()
        pl.addWidget(self.dot)
        pl.addWidget(self.status)
        pl.addWidget(self.flag)
        v.addWidget(self.pill, 0, Qt.AlignmentFlag.AlignHCenter)
        self.sub = label("", wrap=True)
        self.sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop = label("", "hint", True)
        self.drop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.sub)
        v.addWidget(self.drop)
        v.addSpacing(6)

        # stats: icon, value, label (same order as the Android card)
        self.stats, sl = card((6, 16, 6, 16), 0)
        row = QHBoxLayout()
        row.setSpacing(0)
        sl.addLayout(row)
        self.st = {}
        for key, ico in (("ping", "bolt"), ("download", "down"), ("upload", "up"), ("link_speed", "globe")):
            col = QVBoxLayout()
            col.setSpacing(0)
            lab, val = QLabel(), QLabel("—")
            for w in (lab, val):
                w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setObjectName("hint")
            val.setStyleSheet("font-size:14px;font-weight:600;")
            col.addWidget(Icon(ico, 18, "teal"), 0, Qt.AlignmentFlag.AlignHCenter)
            col.addSpacing(8)
            col.addWidget(val)
            col.addSpacing(2)
            col.addWidget(lab)
            row.addLayout(col, 1)
            self.st[key] = (lab, val)
        v.addWidget(self.stats)

        self.proxy_card, pc = card((14, 12, 14, 12))
        self.proxy_lbl = QLabel()
        self.proxy_lbl.setStyleSheet("font-family:Consolas,monospace;font-size:12px;")
        pc.addWidget(self.proxy_lbl)
        v.addWidget(self.proxy_card)

        # actions (only while connected)
        self.actions = QWidget()
        al = QHBoxLayout(self.actions)
        al.setContentsMargins(0, 2, 0, 0)
        al.setSpacing(8)
        self.b_test, self.b_rescan = Btn("", "tonal", icon="bolt"), Btn("", "tonal", icon="refresh")
        for b in (self.b_test, self.b_rescan):
            al.addWidget(b)
        self.test_lbl = label("", "hint")
        al.addWidget(self.test_lbl)
        al.addStretch()
        self.b_test.clicked.connect(self.run_ping)
        self.b_rescan.clicked.connect(self.ctl.rescan)
        self.pinged.connect(self.on_pinged)
        v.addWidget(self.actions)

        # connection setup card: mode, core family, collapsible options
        self.seg_mode = Segmented(self.set_mode)
        self.seg_fam = Segmented(self.set_family)
        self.setup, sv = card((12, 12, 12, 12), 10)
        self.summary = SummaryRow(self.toggle_panel)
        self.hint = label("", "hint", True)
        self.panel = QWidget()
        self.panel_l = QVBoxLayout(self.panel)
        self.panel_l.setContentsMargins(2, 0, 2, 0)
        self.panel_l.setSpacing(12)
        for w in (self.seg_mode, self.seg_fam, self.summary, self.hint, self.panel):
            sv.addWidget(w)
        v.addSpacing(4)
        v.addWidget(self.setup)

        # last two log lines; click opens the Logs page
        self.logbtn = ClickCard(win.open_logs)
        ll = QVBoxLayout(self.logbtn)
        ll.setContentsMargins(14, 12, 14, 12)
        ll.setSpacing(0)
        self.loglbl = QLabel()
        self.loglbl.setObjectName("mono")
        self.loglbl.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        ll.addWidget(self.loglbl)
        v.addWidget(self.logbtn)
        v.addStretch()

        ctl = self.ctl
        ctl.status.connect(self.on_status)
        ctl.message.connect(self.on_message)
        ctl.ping.connect(self.on_ping)
        ctl.traffic.connect(self.on_traffic)
        ctl.exit_info.connect(self.on_exit)
        ctl.speed.connect(self.on_speed)
        ctl.log.connect(self.on_log)

        self.clock = QTimer(self)
        self.clock.timeout.connect(self.update_status_line)
        self.clock.start(1000)

    # ---- helpers
    @property
    def idle(self):
        return self.ctl.phase == "idle"

    def set_state(self, **kw):
        for k, val in kw.items():
            setattr(self, "_" + k, val)
        self.update_stats()
        self.update_status_line()

    # ---- full render
    def refresh(self):
        self.b_logs.setToolTip(L("logs"))
        self.b_set.setToolTip(L("settings"))
        self.b_test.setText(L("ping_testing") if self._testing else L("ping_test"))
        self.b_rescan.setText(L("rescan"))
        for key, (lab, _) in self.st.items():
            lab.setText(L(key))
        self.seg_mode.set_items([("vpn", L("vpn")), ("proxy", L("proxy"))], S.mode, self.idle)
        fam = core.route_of(S).family
        self.seg_fam.set_items([("aether", L("core_aether")), ("psiphon", L("core_psiphon")), ("tor", L("core_tor"))], fam, self.idle)
        self.build_panel()
        self.update_all()

    def update_all(self):
        ph, idle = self.ctl.phase, self.idle
        live = ph == "connected"
        c = pal()
        color = c["teal"] if live else c["sub"] if idle else c["amber"]
        qc = QColor(color)
        self.pill.tint = qc
        self.pill.update()
        self.dot.set_color(qc)
        self.status.setStyleSheet(f"color:{color};font-size:15px;font-weight:600;")
        self.status.setText(L(ph))
        self.btn.set_phase(ph)
        self.proxy_card.setVisible(S.mode == "proxy")
        self.proxy_lbl.setText(L("proxy_info", a=f"127.0.0.1:{S.socks_port}") +
                               (("     " + L("http_info", a=f"127.0.0.1:{S.http_port}")) if S.system_proxy else ""))
        self.actions.setVisible(live)
        self.b_rescan.setVisible(core.route_of(S).family == "aether")
        self.hint.setVisible(not idle)
        self.hint.setText(L("locked_hint"))
        self.panel.setVisible(self._panel_open and idle)
        mode = L("vpn") if S.mode == "vpn" else L("proxy")
        self.summary.setText(f"{mode}  ·  {active_label()}")
        self.summary.kind = "lock" if not idle else ("chev_up" if self._panel_open else "chevron")
        self.summary.setEnabled(idle)
        self.summary.restyle()
        self.summary.update()
        self.drop.setText(L("last_drop", r=self._reason) if self._reason else "")
        self.update_stats()
        self.update_status_line()
        self.update_logs()

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

    def update_flag(self):
        """Flag of the exit country next to the status while connected; Tor shows the 'auto' globe."""
        r = core.route_of(S)
        pm, key, tip = None, "", ""
        if self.ctl.phase == "connected":
            if r.family == "tor":
                pm, key = flag_pixmap("", 26), "tor"
            else:
                m = re.search(r"\(([A-Za-z]{2})\)\s*$", self._exit or "")
                cc = m.group(1).upper() if m else ""
                if not cc and r.psiphon and len(S.psiphon_region) == 2:
                    cc = S.psiphon_region.upper()
                if cc:
                    pm, key, tip = flag_pixmap(cc, 26), cc, region_name(cc)
        if pm is None or pm.isNull():
            self.flag.hide()
            return
        if self.flag.property("cc") != key:
            self.flag.setPixmap(pm)
            self.flag.setToolTip(tip)
            self.flag.setProperty("cc", key)
        self.flag.show()

    def update_status_line(self):
        self.update_flag()
        ph, c = self.ctl.phase, pal()
        if ph == "reconnecting" or (ph == "connecting" and self._attempt > 1):
            txt, col = L("attempt", a=self._attempt, t=self._tries), c["amber"]
        elif ph == "idle" and self._err:
            txt, col = self._err, c["danger"]
        elif ph == "idle":
            txt, col = L("tap"), c["sub"]
        elif ph == "connected":
            t = int(time.time() - self._since) if self._since else 0
            parts = [active_label()] + ([self._exit] if self._exit else [])
            parts.append(f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}")
            txt, col = "  ·  ".join(parts), c["sub"]
        else:
            txt, col = "", c["sub"]
        self.sub.setText(txt)
        self.sub.setStyleSheet(f"color:{col};")

    def update_logs(self):
        lines = list(self.ctl.logs)[-2:]
        self.logbtn.setVisible(bool(lines))
        fm = self.loglbl.fontMetrics()
        self.loglbl.setText("\n".join(fm.elidedText(l, Qt.TextElideMode.ElideRight, 340) for l in lines))

    # ---- panel
    def build_panel(self):
        while self.panel_l.count():
            it = self.panel_l.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        r, add = core.route_of(S), self.panel_l.addWidget
        pick_route = lambda x: self.put(route=x)
        route = lambda keys: field(L("route"), Chips([(k, ROUTE_LABEL[k]) for k in keys], r.name, pick_route))
        if r.family == "aether":
            add(route(("aether", "aether_psiphon", "aether_tor")))
            if r.name == "aether_psiphon":
                add(field(L("region"), RegionRow(self.pick_region)))
            add(field(L("protocol"), Chips(core.PROTOCOLS, S.protocol, lambda x: self.put(protocol=x))))
            if S.protocol in ("masque", "mim"):
                add(field(L("transport"), Chips([("h3", "HTTP/3 (QUIC)"), ("h2", "HTTP/2 (TCP)")], S.carrier, lambda x: self.put(carrier=x))))
        elif r.family == "psiphon":
            add(route(("psiphon_only", "psiphon_reverse")))
            add(field(L("region"), RegionRow(self.pick_region)))
            add(field(L("psiphon_mode"), Chips([("auto", L("auto")), ("cdn", "CDN")], S.psiphon_mode, lambda x: self.put(psiphon_mode=x))))
        else:
            add(route(("tor_only", "tor_reverse")))
            add(field(L("bridges"), Chips([("auto", L("auto")), ("always", L("always")), ("never", L("never"))], S.tor_bridges, lambda x: self.put(tor_bridges=x))))

    def put(self, **kw):
        if self.idle:
            S.set(**kw)
            self.win.refresh()

    def set_mode(self, mode):
        self.put(mode=mode)

    def set_family(self, fam):
        if core.route_of(S).family != fam:
            self.put(route={"aether": "aether", "psiphon": "psiphon_only", "tor": "tor_only"}[fam])

    def toggle_panel(self):
        self._panel_open = not self._panel_open
        self.update_all()

    def pick_region(self):
        if self.idle:
            RegionSheet(self.win, S.psiphon_region, lambda cc: self.put(psiphon_region=cc)).exec()

    def run_ping(self):
        if self._testing or self.ctl.phase != "connected":
            return
        self._testing = True
        self.b_test.setText(L("ping_testing"))
        port = core.exit_port(S)

        def work():
            r = core.socks_get(port, "cp.cloudflare.com", "/generate_204", 8)
            self.pinged.emit(r[0] if r else None)
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

    # ---- controller callbacks
    def on_status(self, phase, attempt, tries):
        if attempt:
            self._attempt, self._tries = attempt, tries
        self._since = (self._since or time.time()) if phase == "connected" else None
        if phase == "idle":
            self._ping, self._rx, self._tx, self._speed, self._exit = -1, 0.0, 0.0, -1.0, ""
            self.test_lbl.setText("")
        self.refresh()

    def on_message(self, key):
        key, _, arg = (key or "").partition("|")
        if not key or key == "stopped":
            self._err = ""
        elif key.startswith("r_"):
            # why the link last dropped / could not connect (shown as "Last drop: ...")
            self._reason = L(key, n=arg) if arg else L(key)
            self._err = ""
            self.update_all()
            return
        else:
            self._err = L(key)
        self.update_status_line()

    def on_ping(self, ms): self.set_state(ping=ms)
    def on_traffic(self, rx, tx): self.set_state(rx=rx, tx=tx)
    def on_exit(self, text): self.set_state(exit=text)
    def on_speed(self, bps): self.set_state(speed=bps)
    def on_log(self, _line): self.update_logs()


class SettingsPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win, self.ctl = win, win.ctl
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(16, 0, 8, 10)
        self.scroll = None
        self._note = ""

    def put(self, key, value, rebuild=False):
        S.set(**{key: value})
        if key == "autostart":
            core.set_autostart(bool(value))
        if key in ("language", "theme"):
            self.win.refresh()
        elif rebuild:
            self.build()
            self.win.home.refresh()

    def build(self):
        keep = self.scroll.verticalScrollBar().value() if self.scroll else 0
        clear_layout(self.root)
        about = IconButton("info", 42, 2.0)
        about.clicked.connect(self.win.open_about)
        self.root.addLayout(page_header(L("settings"), self.win.go_home, [about]))

        locked = self.ctl.phase != "idle"
        body = QWidget()
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 0, 10, 10)
        v.setSpacing(8)
        self.scroll = scrolling(body)
        self.root.addWidget(self.scroll)

        def group(title_key, *, lock=False):
            v.addWidget(SectionTitle(L(title_key)))
            fr, lay = card((16, 16, 16, 16), 16)
            v.addWidget(fr)
            fr.setEnabled(not (lock and locked))
            return lay

        def chips(lay, title, key, items, rebuild=True):
            lay.addWidget(field(title, Chips(items, S.d[key], lambda x, k=key: self.put(k, x, rebuild))))

        def switch(lay, title, key):
            lay.addWidget(SwitchRow(title, bool(S.d[key]), lambda val, k=key: self.put(k, bool(val))))

        def number(lay, title, key, lo, hi):
            sp = QSpinBox()
            sp.setRange(lo, hi)
            sp.setValue(int(S.d[key]))
            sp.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            sp.valueChanged.connect(lambda val, k=key: self.put(k, int(val)))
            lay.addWidget(field(title, sp))

        def text(lay, title, key, hint="", endpoint=False):
            e = QLineEdit(str(S.d[key]))
            e.setPlaceholderText(hint)

            def changed(val, k=key):
                val = val.strip()
                self.put(k, val)
                if endpoint:
                    bad = bool(val) and core.clean_endpoint(val) is None
                    e.setProperty("bad", "true" if bad else "false")
                    e.style().unpolish(e)
                    e.style().polish(e)
            e.textChanged.connect(changed)
            lay.addWidget(field(title, e))
            if endpoint and S.d[key] and core.clean_endpoint(S.d[key]) is None:
                e.setProperty("bad", "true")
                lay.addWidget(label(L("endpoint_invalid"), "err", True))

        def action(lay, icon, title, fn, danger=False, enabled=True):
            b = Btn("", "action")
            b.setStyleSheet("QPushButton#action { padding: 0; }")
            b.setMinimumHeight(48)
            b.setEnabled(enabled)
            b.clicked.connect(fn)
            h = QHBoxLayout(b)
            h.setContentsMargins(14, 8, 14, 8)
            h.setSpacing(12)
            ic = Icon(icon, 20, "danger" if danger else "primary", 2.0)
            t = QLabel(title)
            t.setStyleSheet(f"color:{pal()['danger'] if danger else pal()['text']};")
            for w in (ic, t):
                w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            h.addWidget(ic)
            h.addWidget(t, 1)
            lay.addWidget(b)

        if locked:
            v.addWidget(banner(L("locked_hint")))

        g = group("sec_general")
        chips(g, L("language"), "language", [("fa", "فارسی"), ("en", "English")], False)
        chips(g, L("theme"), "theme", [("dark", L("dark")), ("light", L("light"))], False)
        chips(g, L("default_mode"), "mode", [("vpn", L("vpn")), ("proxy", L("proxy"))])
        switch(g, L("autostart"), "autostart")
        switch(g, L("auto_connect"), "auto_connect")
        switch(g, L("start_min"), "start_minimized")
        switch(g, L("close_tray"), "hide_on_close")
        chips(g, L("split_tunnel"), "split_mode",
              [("off", L("split_off")), ("include", L("split_include")), ("exclude", L("split_exclude"))])
        if S.split_mode != "off":
            text(g, L("split_apps"), "split_apps", L("split_hint"))
            g.addWidget(label(L("split_note"), "hint", True))
        g.addWidget(label(L("admin_note"), "hint", True))

        g = group("sec_core", lock=True)
        chips(g, L("protocol"), "protocol", core.PROTOCOLS)
        chips(g, L("transport"), "carrier", [("h3", "HTTP/3 (QUIC)"), ("h2", "HTTP/2 (TCP)")], False)
        chips(g, L("scan"), "scan", [(x, x) for x in ("turbo", "balanced", "thorough", "verified", "ironclad")], False)
        chips(g, L("noize"), "noize", [("default", L("default"))] + [(x, x) for x in ("off", "light", "firewall", "balanced", "gfw", "aggressive")], False)
        chips(g, L("ipv"), "ip_version", [("4", "IPv4"), ("6", "IPv6"), ("dual", "IPv4 + IPv6")], False)
        switch(g, L("quick"), "quick_reconnect")
        switch(g, L("fresh"), "fresh_after_drop")
        number(g, L("tries"), "max_tries", 1, 999)
        number(g, L("retry_delay"), "retry_delay_ms", 100, 60000)
        number(g, L("pingfails"), "ping_fails", 1, 20)
        number(g, L("ping_interval"), "ping_interval", 1, 60)
        text(g, L("endpoint"), "endpoint", L("endpoint_hint"), True)
        text(g, L("endpoint2"), "endpoint2", L("endpoint_hint"), True)
        text(g, L("upstream"), "upstream", L("upstream_hint"))

        g = group("sec_routing", lock=True)
        text(g, L("route_block"), "route_block", L("route_hint"))
        text(g, L("route_direct"), "route_direct", L("route_hint"))
        text(g, L("dns"), "dns", "1.1.1.1, 1.0.0.1")

        g = group("sec_psiphon", lock=True)
        g.addWidget(field(L("region"), RegionRow(lambda: RegionSheet(self.win, S.psiphon_region, lambda cc: self.put("psiphon_region", cc, True)).exec())))
        chips(g, L("psiphon_mode"), "psiphon_mode", [("auto", L("auto")), ("cdn", "CDN")], False)

        g = group("sec_tor", lock=True)
        chips(g, L("bridges"), "tor_bridges", [("auto", L("auto")), ("always", L("always")), ("never", L("never"))], False)

        g = group("sec_advanced", lock=True)
        chips(g, L("perf"), "perf", [(x, x) for x in ("auto", "low", "medium", "high")], False)
        text(g, L("extra"), "extra_args", L("extra_hint"))
        number(g, L("mtu"), "mtu", 1280, 9000)
        chips(g, L("stack"), "tun_stack", [("gvisor", "gVisor"), ("system", "system"), ("mixed", "mixed")], False)
        number(g, L("socks"), "socks_port", 1024, 65535)
        switch(g, L("free_ports"), "free_ports")
        switch(g, L("http_proxy"), "system_proxy")
        number(g, L("http"), "http_port", 1024, 65535)
        action(g, "logs", L("open_logs"), self.win.open_logs)
        action(g, "trash", L("clear_cache"), self.ask_clear, True, not locked)
        if self._note:
            g.addWidget(label(self._note, "hint", True))
        v.addStretch()
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(keep))

    def ask_clear(self):
        ConfirmSheet(self.win, L("clear_cache"), L("clear_cache_warn"), L("confirm"), self.clear_cache).exec()

    def clear_cache(self):
        for sub in ("aether", "singbox"):
            shutil.rmtree(os.path.join(core.DATA_DIR, sub), ignore_errors=True)
        self._note = L("cache_cleared")
        self.build()


class LogsPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win, self.ctl = win, win.ctl
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(16, 0, 14, 12)
        self.view = QTextEdit()
        self.view.setReadOnly(True)
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.holder = Card("card")
        hl = QVBoxLayout(self.holder)
        hl.setContentsMargins(14, 12, 8, 12)
        hl.addWidget(self.view)
        self.empty = QWidget()
        el = QVBoxLayout(self.empty)
        el.addStretch()
        el.addWidget(Icon("logs", 44, "line"), 0, Qt.AlignmentFlag.AlignHCenter)
        el.addSpacing(12)
        self.empty_lbl = QLabel()
        self.empty_lbl.setObjectName("sub")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(self.empty_lbl)
        el.addStretch()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self.render)
        self.ctl.log.connect(self.append)

    def append(self, _line):
        if self.isVisible() and not self._timer.isActive():
            self._timer.start()

    def render(self):
        """Newest line first; timestamps dimmed, error lines in the error colour (like the Android Logs page)."""
        lines = list(self.ctl.logs)
        self.empty.setVisible(not lines)
        self.holder.setVisible(bool(lines))
        c = pal()
        out = []
        for ln in reversed(lines):
            bad = "error" in ln.lower() or "fail" in ln.lower()
            body = c["danger"] if bad else c["text"]
            if len(ln) > 9 and ln[2] == ":" and ln[5] == ":":
                out.append(f'<span style="color:{c["sub"]}">{html.escape(ln[:8])}</span>'
                           f'<span style="color:{body}">{html.escape(ln[8:])}</span>')
            else:
                out.append(f'<span style="color:{body}">{html.escape(ln)}</span>')
        self.view.setHtml('<div style="white-space:pre-wrap">' + "<br>".join(out) + "</div>")

    def build(self):
        clear_layout(self.root, keep=(self.holder, self.empty))
        cp, rm = IconButton("copy", 42, 2.0), IconButton("trash", 42, 2.0, tint="danger")
        cp.clicked.connect(lambda: QApplication.clipboard().setText("\n".join(self.ctl.logs)))
        rm.clicked.connect(self.clear)
        self.root.addLayout(page_header(L("logs"), self.win.go_home, [cp, rm]))
        self.root.addWidget(self.holder, 1)
        self.root.addWidget(self.empty, 1)
        self.empty_lbl.setText(L("no_logs"))
        self.render()

    def show_all(self):
        self.render()

    def clear(self):
        self.ctl.logs.clear()
        self.render()
        self.win.home.update_logs()


def read_versions():
    out = {}
    try:
        with open(os.path.join(core.CORE_DIR, "versions.txt"), encoding="utf-8") as f:
            for ln in f:
                if "=" in ln:
                    k, v = ln.strip().split("=", 1)
                    out[k] = v
    except OSError:
        pass
    return out


class AboutPage(QWidget):
    checked = pyqtSignal(object)  # ("ok", (tag, newer, url)) or ("fail", None)

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(16, 0, 8, 10)
        self._upd = ("idle", None)   # idle | checking | latest | failed | available
        self.checked.connect(self.on_checked)

    def check_update(self):
        state, data = self._upd
        if state == "checking":
            return
        if state == "available":
            QDesktopServices.openUrl(QUrl(data[2]))
            return
        self._upd = ("checking", None)
        self.build()

        def work():
            try:
                self.checked.emit(("ok", core.check_update()))
            except Exception:
                self.checked.emit(("fail", None))
        threading.Thread(target=work, daemon=True).start()

    def on_checked(self, res):
        kind, data = res
        self._upd = ("failed", None) if kind == "fail" else (("available", data) if data[1] else ("latest", data))
        self.build()

    def build(self):
        clear_layout(self.root)
        c = pal()
        self.root.addLayout(page_header(L("about"), self.win.open_settings))
        body = QWidget()
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 0, 10, 10)
        v.setSpacing(14)
        self.root.addWidget(scrolling(body))

        # logo, name and version badge
        head = QWidget()
        hl = QVBoxLayout(head)
        hl.setContentsMargins(0, 8, 0, 0)
        hl.setSpacing(0)
        name = QLabel("8 VPN")
        name.setStyleSheet("font-size:24px;font-weight:700;")
        pc = QColor(c["primary"])
        badge = QLabel("v" + VERSION)
        badge.setStyleSheet(f"background: rgba({pc.red()},{pc.green()},{pc.blue()},36); color:{c['primary']};"
                            "border-radius: 11px; padding: 3px 12px; font-size: 12px; font-weight: 600;")
        hl.addWidget(LogoMark(84), 0, Qt.AlignmentFlag.AlignHCenter)
        hl.addSpacing(14)
        hl.addWidget(name, 0, Qt.AlignmentFlag.AlignHCenter)
        hl.addSpacing(6)
        hl.addWidget(badge, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addWidget(head)

        ver = read_versions()
        unknown = L("version_unknown")
        info, il = card((16, 16, 16, 16), 14)
        for title, val in ((L("app_version"), VERSION), (L("core_version"), ver.get("aether", unknown)),
                           (L("singbox_version"), ver.get("singbox", unknown))):
            row = QHBoxLayout()
            lab = QLabel(title)
            lab.setStyleSheet(f"color:{c['sub']};")
            val_l = QLabel(val)
            val_l.setStyleSheet("font-weight:600;")
            row.addWidget(lab, 1)
            row.addWidget(val_l)
            il.addLayout(row)
        v.addWidget(info)

        def tile_row(on_click, kind, title_text, sub_text, title_color=None, sub_style=None, trailing=True):
            rc = ClickCard(on_click)
            rl = QHBoxLayout(rc)
            rl.setContentsMargins(14, 14, 14, 14)
            rl.setSpacing(14)
            rl.addWidget(Tile(kind, 42, 22))
            col = QVBoxLayout()
            col.setSpacing(0)
            t = label(title_text, None, True)
            t.setStyleSheet(f"font-weight:600;color:{title_color or c['text']};")
            col.addWidget(t)
            if sub_text:
                s = label(sub_text, None, True)
                s.setStyleSheet(sub_style or f"font-size:12px;color:{c['sub']};")
                col.addWidget(s)
            rl.addLayout(col, 1)
            if trailing:
                rl.addWidget(Icon("chev_left" if rtl() else "chev_right", 20, "sub"))
            v.addWidget(rc)

        # update check (same idea as the Android app)
        state, data = self._upd
        avail = state == "available"
        note = {"idle": "update_tap", "checking": "update_checking", "latest": "update_latest",
                "failed": "update_failed"}.get(state)
        sub_color = c["danger"] if state == "failed" else c["sub"]
        tile_row(self.check_update, "down" if avail else "refresh",
                 L("update_available", v=data[0]) if avail else L("update_check"), L(note) if note else "",
                 title_color=c["primary"] if avail else None,
                 sub_style=f"font-size:12px;color:{sub_color};", trailing=False)

        def open_url(u):
            return lambda: QDesktopServices.openUrl(QUrl(u))

        tile_row(open_url(GITHUB), "code", L("github"), GITHUB.replace("https://github.com/", ""),
                 sub_style=f"font-family:Consolas,monospace;font-size:12px;color:{c['sub']};")
        tile_row(open_url(GITHUB_ANDROID), "code", L("github_android"), GITHUB_ANDROID.replace("https://github.com/", ""),
                 sub_style=f"font-family:Consolas,monospace;font-size:12px;color:{c['sub']};")
        tile_row(open_url(TELEGRAM), "send", L("telegram"), "@" + TELEGRAM.rstrip("/").rsplit("/", 1)[-1],
                 sub_style=f"font-family:Consolas,monospace;font-size:12px;color:{c['sub']};")

        lic, ll = card((16, 16, 16, 16), 10)
        ll.addWidget(label(L("license_title"), "gtitle"))
        ll.addWidget(label(L("license_text"), "sub", True))
        credits = QLabel("github.com/CluvexStudio/Aether\ngithub.com/SagerNet/sing-box\nwintun.net")
        credits.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        credits.setStyleSheet(f"font-family:Consolas,monospace;font-size:12px;color:{c['sub']};")
        ll.addWidget(credits)
        v.addWidget(lic)
        v.addStretch()


# ------------------------------------------------------------------ main window
class MainWindow(QWidget):
    def __init__(self, ctl: Controller):
        super().__init__()
        self.ctl = ctl
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(430, 720)
        self.setWindowTitle("8 VPN")
        self.icon = QIcon(core.resource("assets", "icon.png"))
        self.setWindowIcon(self.icon)
        self._drag = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)

        chrome = QHBoxLayout()
        chrome.setContentsMargins(0, 6, 8, 0)
        chrome.addStretch()
        for kind, fn in (("minus", self.showMinimized), ("close", self.close)):
            b = IconButton(kind, 30, 2.0)
            b.clicked.connect(fn)
            chrome.addWidget(b)
        outer.addLayout(chrome)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack)
        self.home, self.settings, self.logs, self.about = HomePage(self), SettingsPage(self), LogsPage(self), AboutPage(self)
        for pg in (self.home, self.settings, self.logs, self.about):
            self.stack.addWidget(pg)

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
        ctl.status.connect(self.on_status)

        self.refresh()

    # ---- rendering
    def refresh(self):
        QApplication.instance().setStyleSheet(qss())
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft if rtl() else Qt.LayoutDirection.LeftToRight)
        self.a_show.setText(L("tray_show"))
        self.a_quit.setText(L("tray_quit"))
        self.a_toggle.setText(L("tray_disconnect") if self.ctl.phase != "idle" else L("tray_connect"))
        self.home.refresh()
        self.settings.build()
        self.logs.build()
        self.about.build()
        self.update()

    def on_status(self, phase, *_):
        self.a_toggle.setText(L("tray_disconnect") if phase != "idle" else L("tray_connect"))
        if phase in ("idle", "connecting"):
            self.settings.build()  # lock / unlock the option groups

    def paintEvent(self, _):
        c = pal()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 22, 22)
        p.fillPath(path, QColor(c["bg"]))
        p.setPen(QPen(QColor(c["border"]), 1))
        p.drawPath(path)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() < 62:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _):
        self._drag = None

    # ---- navigation
    def go_home(self): self.stack.setCurrentWidget(self.home)
    def open_settings(self): self.stack.setCurrentWidget(self.settings)
    def open_about(self): self.stack.setCurrentWidget(self.about)

    def open_logs(self):
        self.logs.show_all()
        self.stack.setCurrentWidget(self.logs)

    # ---- actions
    def toggle(self):
        h = self.home
        if self.ctl.phase == "idle":
            h._err = ""
            h._reason = ""
            if S.mode == "vpn" and not core.is_admin():
                h._err = L("need_admin_ask")
                h.update_status_line()
                if core.relaunch_as_admin(["--connect"]):
                    QTimer.singleShot(300, self.quit_app)
                else:
                    h._err = L("admin_denied")
                    h.update_status_line()
                return
            self.ctl.start()
        elif self.ctl.phase != "stopping":
            self.ctl.stop()

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
        if S.hide_on_close and self.tray.isVisible():
            self.hide()
            self.tray.showMessage("8 VPN", L("tray_hint"), self.icon, 3000)
        else:
            self.quit_app()


# ------------------------------------------------------------------ entry
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
    # The release builds ask for admin rights through their manifest before anything starts.
    # This covers running from source: ask for them first and open only in the elevated copy.
    if core.IS_WIN and not core.is_admin() and "--no-elevate" not in argv:
        if core.relaunch_as_admin(argv):
            return 0
    if not single_instance(6.0 if "--connect" in argv else 0.0):
        return 0
    if core.IS_WIN:
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
        QTimer.singleShot(150, w.toggle)
    code = app.exec()
    # Make sure nothing is left running: stop the cores, restore the proxy, then end the process.
    try:
        ctl.shutdown()
        core.restore_system_proxy()
    finally:
        os._exit(code)


if __name__ == "__main__":
    sys.exit(main())
