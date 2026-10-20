import ctypes
import os
import shutil
import sys
import threading
import time

from PyQt6.QtCore import QPoint, QRectF, QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QDesktopServices, QFont, QIcon, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                             QMenu, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QStackedWidget,
                             QSystemTrayIcon, QVBoxLayout, QWidget)

import core
from core import S, TELEGRAM, VERSION, Controller
from ui_kit import (L, Btn, Card, Chips, ConnectButton, Icon, IconButton, Segmented, Sheet, Switch, flag_pixmap, fmt_rate,
                    paint_icon, pal, qss, rtl)

GITHUB = "https://github.com/Mrmmd2004/8VPN_Windows"

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
ROUTE_LABEL = {k: r.label for k, r in core.ROUTES.items()}


def region_name(cc):
    n = REGIONS.get(cc.upper())
    return f"{n[1] if rtl() else n[0]}  ({cc.upper()})" if n else cc.upper()


def active_label():
    r = core.route_of(S)
    proto = dict(core.PROTOCOLS)[S.protocol]
    return {"aether": proto, "aether_psiphon": f"{proto} → Psiphon", "aether_tor": f"{proto} → Tor",
            "psiphon_reverse": "Psiphon → MASQUE (HTTP/2)", "tor_reverse": "Tor → MASQUE (HTTP/2)"}.get(r.name, r.label)


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
    v.setSpacing(7)
    v.addWidget(label(title, "sub"))
    v.addWidget(widget)
    return box


def inline_row(title, widget):
    box = QWidget()
    h = QHBoxLayout(box)
    h.setContentsMargins(0, 0, 0, 0)
    h.addWidget(QLabel(title), 1)
    h.addWidget(widget)
    return box


def page_header(title, back, actions=()):
    h = QHBoxLayout()
    b = IconButton("back", 42, 2.4)
    b.clicked.connect(back)
    h.addWidget(b)
    t = label(title, "page")
    h.addWidget(t, 1)
    for a in actions:
        h.addWidget(a)
    return h


def scrolling(widget_layout_owner):
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sc.setWidget(widget_layout_owner)
    return sc


class ConfirmSheet(Sheet):
    def __init__(self, parent, title, text, ok_text, on_ok):
        super().__init__(parent, title)
        self.v.addWidget(label(text, "sub", True))
        h = QHBoxLayout()
        h.addStretch()
        for txt, name, fn in ((L("cancel"), "link", self.reject), (ok_text, "linkDanger", lambda: (on_ok(), self.accept()))):
            b = QPushButton(txt)
            b.setObjectName(name)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(fn)
            h.addWidget(b)
        self.v.addLayout(h)


class RegionSheet(Sheet):
    def __init__(self, parent, current, on_pick):
        super().__init__(parent, L("region"), 380)
        self._pick = on_pick
        self.search = QLineEdit()
        self.search.setPlaceholderText(L("search"))
        self.v.addWidget(self.search)
        self.list = QListWidget()
        self.list.setIconSize(QSize(40, 27))
        self.list.setFixedHeight(340)
        rows = [("", L("region_auto"), "")] + [(cc, region_name(cc), " ".join(REGIONS[cc]).lower() + cc.lower()) for cc in REGIONS]
        for cc, text, hay in rows:
            it = QListWidgetItem(text)
            it.setIcon(QIcon(flag_pixmap(cc, 40)))
            it.setData(Qt.ItemDataRole.UserRole, cc)
            it.setData(Qt.ItemDataRole.UserRole + 1, hay or "auto")
            it.setSizeHint(QSize(0, 42))
            self.list.addItem(it)
            if cc == current.upper():
                self.list.setCurrentItem(it)
        self.list.itemClicked.connect(self.picked)
        self.search.textChanged.connect(self.filter)
        self.v.addWidget(self.list)
        h = QHBoxLayout()
        h.addStretch()
        b = QPushButton(L("cancel"))
        b.setObjectName("link")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(self.reject)
        h.addWidget(b)
        self.v.addLayout(h)

    def filter(self, q):
        q = q.strip().lower()
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setHidden(bool(q) and q not in it.data(Qt.ItemDataRole.UserRole + 1))

    def picked(self, it):
        self._pick(it.data(Qt.ItemDataRole.UserRole))
        self.accept()


class RegionRow(QPushButton):
    """Flag + country name + chevron, used on Home and in Settings."""

    def __init__(self, on_click, enabled=True):
        super().__init__("")
        self.setObjectName("row")
        self.setStyleSheet("QPushButton#row { padding: 0; }")
        self.setMinimumHeight(52)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setEnabled(enabled)
        self.clicked.connect(on_click)
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 8, 16, 8)
        h.setSpacing(12)
        cc = S.psiphon_region
        flag = QLabel()
        flag.setPixmap(flag_pixmap(cc, 34))
        text = QLabel(region_name(cc) if cc else L("region_auto"))
        for w in (flag, text):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        chev = Icon("down", 20)
        chev.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        h.addWidget(flag)
        h.addWidget(text, 1)
        h.addWidget(chev)


class SummaryRow(QPushButton):
    def __init__(self, on_click):
        super().__init__("")
        self.setObjectName("row")
        self.setStyleSheet("QPushButton#row { padding: 14px 46px 14px 16px; }" if not rtl() else
                           "QPushButton#row { padding: 14px 16px 14px 46px; text-align: right; }")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(on_click)
        self.kind = "down"

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        x = 12 if rtl() else self.width() - 40
        paint_icon(p, self.kind, QRectF(x, (self.height() - 24) / 2, 28, 24), QColor(pal()["sub"]), 2.2)


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
        root.setContentsMargins(20, 0, 8, 10)
        root.setSpacing(4)

        top = QHBoxLayout()
        self.logo = QLabel()
        self.logo.setPixmap(win.icon.pixmap(36, 36))
        title = QLabel("8 VPN")
        title.setStyleSheet("font-size:25px;")
        top.addWidget(self.logo)
        top.addSpacing(6)
        top.addWidget(title)
        top.addStretch()
        self.b_logs = QPushButton()
        self.b_logs.setObjectName("link")
        self.b_logs.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_logs.clicked.connect(win.open_logs)
        self.b_set = IconButton("gear", 42, 2.0)
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
        v.setSpacing(12)

        self.btn = ConnectButton(win.toggle)
        v.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignHCenter)

        self.pill = Card("pill")
        pl = QHBoxLayout(self.pill)
        pl.setContentsMargins(16, 6, 16, 6)
        pl.setSpacing(9)
        self.dot, self.status = QLabel("●"), QLabel()
        pl.addWidget(self.dot)
        pl.addWidget(self.status)
        v.addWidget(self.pill, 0, Qt.AlignmentFlag.AlignHCenter)
        self.sub = label("", wrap=True)
        self.sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop = label("", "hint", True)
        self.drop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.sub)
        v.addWidget(self.drop)

        # stats
        self.stats, sl = card((8, 16, 8, 16), 0)
        row = QHBoxLayout()
        sl.addLayout(row)
        self.st = {}
        for key in ("ping", "download", "upload", "link_speed"):
            col = QVBoxLayout()
            col.setSpacing(5)
            lab, val = QLabel(), QLabel("—")
            for w in (lab, val):
                w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setObjectName("sub")
            val.setStyleSheet("font-size:14px;font-weight:600;")
            col.addWidget(lab)
            col.addWidget(val)
            row.addLayout(col, 1)
            self.st[key] = (lab, val)
        v.addWidget(self.stats)

        self.proxy_card, pc = card((16, 12, 16, 12))
        self.proxy_lbl = QLabel()
        self.proxy_lbl.setStyleSheet("font-family:Consolas,monospace;font-size:12px;")
        pc.addWidget(self.proxy_lbl)
        v.addWidget(self.proxy_card)

        # actions
        self.actions = QWidget()
        al = QHBoxLayout(self.actions)
        al.setContentsMargins(0, 0, 0, 0)
        self.b_test, self.b_rescan = Btn("", "pill"), Btn("", "pill")
        for b in (self.b_test, self.b_rescan):
            al.addWidget(b)
        self.test_lbl = label("", "sub")
        al.addWidget(self.test_lbl)
        al.addStretch()
        self.b_test.clicked.connect(self.run_ping)
        self.b_rescan.clicked.connect(self.ctl.rescan)
        self.pinged.connect(self.on_pinged)
        v.addWidget(self.actions)

        # mode + core family
        self.seg_mode = Segmented(self.set_mode)
        self.seg_fam = Segmented(self.set_family)
        v.addWidget(self.seg_mode)
        v.addWidget(self.seg_fam)

        self.setup, sv = card((12, 12, 12, 14), 12)
        self.summary = SummaryRow(self.toggle_panel)
        self.hint = label("", "hint", True)
        self.panel = QWidget()
        self.panel_l = QVBoxLayout(self.panel)
        self.panel_l.setContentsMargins(4, 0, 4, 0)
        self.panel_l.setSpacing(14)
        for w in (self.summary, self.hint, self.panel):
            sv.addWidget(w)
        v.addWidget(self.setup)

        self.logbtn = QPushButton()
        self.logbtn.setObjectName("mono")
        self.logbtn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logbtn.clicked.connect(win.open_logs)
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
        self.b_logs.setText(L("logs"))
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
        color = c["primary"] if live else c["sub"] if idle else c["amber"]
        qc = QColor(color)
        self.pill.tint = qc
        self.pill.update()
        self.dot.setStyleSheet(f"color:{color};font-size:11px;")
        self.status.setStyleSheet(f"color:{color};font-size:16px;font-weight:600;")
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
        self.summary.kind = "lock" if not idle else ("up" if self._panel_open else "down")
        self.summary.setEnabled(idle)
        self.summary.update()
        self.drop.setText(L("last_drop", r=self._reason) if self._reason and idle else "")
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

    def update_status_line(self):
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
        fm = self.logbtn.fontMetrics()
        self.logbtn.setText("\n".join(fm.elidedText(l, Qt.TextElideMode.ElideRight, 340) for l in lines))
        self.logbtn.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

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
        if phase == "connected":
            self._reason = ""
        if phase == "idle":
            self._ping, self._rx, self._tx, self._speed, self._exit = -1, 0.0, 0.0, -1.0, ""
            self.test_lbl.setText("")
        self.refresh()

    def on_message(self, key):
        if not key or key == "stopped":
            self._err = ""
        elif key in ("ping_failed", "core_exited", "tun_exited", "rescan"):
            self._reason = L("rescan_msg" if key == "rescan" else key)
            self._err = ""
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
        while self.root.count():
            it = self.root.takeAt(0)
            if it.layout():
                while it.layout().count():
                    w = it.layout().takeAt(0).widget()
                    if w:
                        w.deleteLater()
            elif it.widget():
                it.widget().deleteLater()
        about = IconButton("info", 42, 2.0)
        about.clicked.connect(self.win.open_about)
        self.root.addLayout(page_header(L("settings"), self.win.go_home, [about]))

        locked = self.ctl.phase != "idle"
        body = QWidget()
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 6, 10, 10)
        v.setSpacing(14)
        self.scroll = scrolling(body)
        self.root.addWidget(self.scroll)

        def group(title_key, *, lock=False):
            gl = label(L(title_key), "gtitle")
            fr, lay = card((16, 16, 16, 16), 16)
            lay.setSpacing(16)
            v.addWidget(gl)
            v.addWidget(fr)
            fr.setEnabled(not (lock and locked))
            return lay

        def chips(lay, title, key, items, rebuild=True):
            lay.addWidget(field(title, Chips(items, S.d[key], lambda x, k=key: self.put(k, x, rebuild))))

        def switch(lay, title, key):
            sw = Switch(bool(S.d[key]))
            sw.toggled.connect(lambda val, k=key: self.put(k, bool(val)))
            lay.addWidget(inline_row(title, sw))

        def number(lay, title, key, lo, hi):
            sp = QSpinBox()
            sp.setRange(lo, hi)
            sp.setValue(int(S.d[key]))
            sp.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            sp.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sp.setFixedWidth(110)
            sp.valueChanged.connect(lambda val, k=key: self.put(k, int(val)))
            lay.addWidget(inline_row(title, sp))

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
            b.setMinimumHeight(50)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setEnabled(enabled)
            b.clicked.connect(fn)
            h = QHBoxLayout(b)
            h.setContentsMargins(16, 8, 16, 8)
            h.setSpacing(12)
            ic = Icon(icon, 22, "danger" if danger else "primary", 2.0)
            t = QLabel(title)
            t.setStyleSheet(f"color:{pal()['danger'] if danger else pal()['text']};")
            for w in (ic, t):
                w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            h.addWidget(ic)
            h.addWidget(t, 1)
            lay.addWidget(b)

        if locked:
            note, nl = card((16, 12, 16, 12))
            note.kind = "banner"
            nl.addWidget(label(L("locked_hint"), None, True))
            v.addWidget(note)

        g = group("sec_general")
        chips(g, L("language"), "language", [("fa", "فارسی"), ("en", "English")], False)
        chips(g, L("theme"), "theme", [("dark", L("dark")), ("light", L("light"))], False)
        chips(g, L("default_mode"), "mode", [("vpn", L("vpn")), ("proxy", L("proxy"))])
        switch(g, L("autostart"), "autostart")
        switch(g, L("auto_connect"), "auto_connect")
        switch(g, L("start_min"), "start_minimized")
        switch(g, L("close_tray"), "hide_on_close")
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
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(600)
        self.view.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.header = None
        self.ctl.log.connect(self.append)

    def append(self, line):
        self.view.appendPlainText(line)

    def build(self):
        while self.root.count():
            it = self.root.takeAt(0)
            if it.layout():
                while it.layout().count():
                    w = it.layout().takeAt(0).widget()
                    if w and w is not self.view:
                        w.deleteLater()
        cp, tr = IconButton("copy", 42, 2.0), IconButton("trash", 42, 2.0)
        cp.clicked.connect(lambda: QApplication.clipboard().setText(self.view.toPlainText()))
        tr.clicked.connect(self.clear)
        self.root.addLayout(page_header(L("logs"), self.win.go_home, [cp, tr]))
        self.root.addWidget(self.view)

    def show_all(self):
        self.view.setPlainText("\n".join(self.ctl.logs))

    def clear(self):
        self.ctl.logs.clear()
        self.view.clear()
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
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(16, 0, 8, 10)

    def build(self):
        while self.root.count():
            it = self.root.takeAt(0)
            if it.layout():
                while it.layout().count():
                    w = it.layout().takeAt(0).widget()
                    if w:
                        w.deleteLater()
            elif it.widget():
                it.widget().deleteLater()
        self.root.addLayout(page_header(L("about"), self.win.open_settings))
        body = QWidget()
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 8, 10, 10)
        v.setSpacing(14)
        self.root.addWidget(scrolling(body))

        logo = QLabel()
        logo.setPixmap(self.win.icon.pixmap(84, 84))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name = QLabel("8 VPN")
        name.setStyleSheet("font-size:26px;")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(logo)
        v.addWidget(name)

        ver = read_versions()
        unknown = L("version_unknown")
        c, cl = card((18, 16, 18, 16), 14)
        for title, val in ((L("app_version"), VERSION), (L("core_version"), ver.get("aether", unknown)),
                           (L("singbox_version"), ver.get("singbox", unknown))):
            row = QHBoxLayout()
            row.addWidget(QLabel(title), 1)
            val_l = QLabel(val)
            val_l.setObjectName("sub")
            row.addWidget(val_l)
            cl.addLayout(row)
        v.addWidget(c)

        c, cl = card((8, 8, 8, 8), 2)
        for title, url in ((L("github"), GITHUB), (L("telegram"), TELEGRAM)):
            b = Btn(title, "action")
            b.clicked.connect(lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            cl.addWidget(b)
        v.addWidget(c)

        c, cl = card((18, 16, 18, 16), 10)
        cl.addWidget(label(L("license_title"), "gtitle"))
        cl.addWidget(label(L("license_text"), "sub", True))
        v.addWidget(c)
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
        QTimer.singleShot(700, w.toggle)
    code = app.exec()
    # Make sure nothing is left running: stop the cores, restore the proxy, then end the process.
    try:
        ctl.shutdown()
        core.restore_system_proxy()
    finally:
        os._exit(code)


if __name__ == "__main__":
    sys.exit(main())
