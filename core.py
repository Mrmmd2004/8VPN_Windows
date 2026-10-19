"""8 VPN for Windows - engine side.

    apps -> TUN (sing-box, gVisor) -> SOCKS5 127.0.0.1:<port> -> Aether -> internet

Two modes:
  * VPN   - sing-box owns a Wintun adapter and routes the whole PC through Aether (needs admin).
  * Proxy - only Aether runs; the Windows system proxy is pointed at its HTTP port (no admin).
"""
import ctypes
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from collections import deque

from PyQt6.QtCore import QObject, pyqtSignal

APP_NAME = "8VPN"
VERSION = "1.0.0"
TELEGRAM = "https://t.me/Clubapp8"

NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW
IS_WIN = sys.platform == "win32"


# ----------------------------------------------------------------- paths
def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource(*parts) -> str:
    base = getattr(sys, "_MEIPASS", app_dir())
    return os.path.join(base, *parts)


_c1 = os.path.join(app_dir(), "core")                                   # zip / installed layout
_c2 = os.path.join(getattr(sys, "_MEIPASS", app_dir()), "core")        # single-file portable build
CORE_DIR = _c1 if os.path.isdir(_c1) else _c2
DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
os.makedirs(DATA_DIR, exist_ok=True)
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
PROXY_BACKUP = os.path.join(DATA_DIR, "proxy_backup.json")

AETHER_EXE = os.path.join(CORE_DIR, "aether.exe")
SINGBOX_EXE = os.path.join(CORE_DIR, "sing-box.exe")
WINTUN_DLL = os.path.join(CORE_DIR, "wintun.dll")


# ------------------------------------------------------------- settings
DEFAULTS = {
    "language": "fa",
    "theme": "dark",
    "mode": "vpn",               # vpn | proxy
    "protocol": "wg",            # wg | masque | gool | gool_classic | mim
    "carrier": "h2",             # MASQUE transport: h2 | h3
    "scan": "turbo",
    "noize": "default",
    "ip_version": "4",           # 4 | 6 | dual
    "quick_reconnect": True,
    "fresh_after_drop": True,
    "max_tries": 3,
    "retry_delay_ms": 1000,
    "ping_fails": 3,
    "ping_interval": 5,
    "mtu": 1500,
    "tun_stack": "gvisor",       # gvisor | system | mixed
    "perf": "auto",
    "dns": "",
    "endpoint": "",
    "endpoint2": "",
    "route_block": "",
    "route_direct": "",
    "upstream": "",
    "extra_args": "",
    "socks_port": 1819,
    "http_port": 1822,
    "system_proxy": True,        # proxy mode: also set the Windows system proxy
    "autostart": False,
    "auto_connect": False,
    "start_minimized": False,
    "close_to_tray": True,
}

PROTOCOLS = [
    ("wg", "WireGuard"),
    ("masque", "MASQUE"),
    ("gool", "WARP-in-MASQUE (Gool)"),
    ("gool_classic", "WARP-in-WARP (Gool classic)"),
    ("mim", "MASQUE-in-MASQUE"),
]


class Settings:
    def __init__(self):
        self.d = dict(DEFAULTS)
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for k, v in saved.items():
                if k in DEFAULTS and isinstance(v, type(DEFAULTS[k])):
                    self.d[k] = v
        except Exception:
            pass
        self._sanitize()

    def __getattr__(self, k):
        try:
            return self.__dict__["d"][k]
        except KeyError:
            raise AttributeError(k)

    def set(self, **kw):
        self.d.update(kw)
        self._sanitize()
        self.save()

    def save(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.d, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _sanitize(self):
        d = self.d
        if not (1024 <= d["socks_port"] <= 65535):
            d["socks_port"] = 1819
        if not (1024 <= d["http_port"] <= 65535) or d["http_port"] == d["socks_port"]:
            d["http_port"] = 1822 if d["socks_port"] != 1822 else 1823
        for k in ("max_tries", "ping_fails", "ping_interval", "mtu", "retry_delay_ms"):
            if not isinstance(d[k], int):
                d[k] = DEFAULTS[k]

    def tries(self): return max(1, min(999, self.max_tries))
    def retry_s(self): return max(0.1, min(60.0, self.retry_delay_ms / 1000))
    def ping_limit(self): return max(1, min(20, self.ping_fails))
    def ping_every(self): return max(1, min(60, self.ping_interval))
    def mtu_v(self): return max(1280, min(9000, self.mtu))


S = Settings()


# ----------------------------------------------------------- helpers
_ansi = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_ep = re.compile(r"^(\d{1,3}(\.\d{1,3}){3}|\[[0-9a-fA-F:.]+\]):(\d{1,5})$")


def clean_endpoint(v: str):
    t = (v or "").strip()
    m = _ep.match(t)
    if not m or not (1 <= int(m.group(3)) <= 65535):
        return None
    if not t.startswith("[") and any(int(x) > 255 for x in t.split(":")[0].split(".")):
        return None
    return t


def csv(v: str) -> str:
    return ",".join(x for x in re.split(r"[,\n ;]+", v or "") if x)


def split_args(v: str):
    import shlex
    try:
        return shlex.split(v or "", posix=False)
    except ValueError:
        return (v or "").split()


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


def is_admin() -> bool:
    if not IS_WIN:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin(extra_args) -> bool:
    """Starts this program again with a UAC prompt. True if Windows accepted the request."""
    if not IS_WIN:
        return False
    if getattr(sys, "frozen", False):
        exe, args = sys.executable, list(extra_args)
    else:
        exe, args = sys.executable, [os.path.abspath(sys.argv[0])] + list(extra_args)
    params = " ".join('"%s"' % a if " " in a else a for a in args)
    try:
        r = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
        return int(r) > 32
    except Exception:
        return False


# ----------------------------------------------- Windows system proxy
_INET = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"


def _refresh_inet():
    try:
        w = ctypes.windll.wininet
        w.InternetSetOptionW(0, 39, 0, 0)  # SETTINGS_CHANGED
        w.InternetSetOptionW(0, 37, 0, 0)  # REFRESH
    except Exception:
        pass


def set_system_proxy(server: str):
    if not IS_WIN:
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _INET, 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as k:
        if not os.path.exists(PROXY_BACKUP):
            def get(name, default):
                try:
                    return winreg.QueryValueEx(k, name)[0]
                except OSError:
                    return default
            backup = {"enable": get("ProxyEnable", 0), "server": get("ProxyServer", ""), "override": get("ProxyOverride", "")}
            with open(PROXY_BACKUP, "w") as f:
                json.dump(backup, f)
        winreg.SetValueEx(k, "ProxyEnable", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "ProxyServer", 0, winreg.REG_SZ, server)
        winreg.SetValueEx(k, "ProxyOverride", 0, winreg.REG_SZ, "localhost;127.*;10.*;172.16.*;192.168.*;<local>")
    _refresh_inet()


def restore_system_proxy():
    """Puts the user's previous proxy settings back (safe to call when nothing was changed)."""
    if not IS_WIN or not os.path.exists(PROXY_BACKUP):
        return
    import winreg
    try:
        with open(PROXY_BACKUP) as f:
            b = json.load(f)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _INET, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "ProxyEnable", 0, winreg.REG_DWORD, int(b.get("enable", 0)))
            winreg.SetValueEx(k, "ProxyServer", 0, winreg.REG_SZ, b.get("server", ""))
            winreg.SetValueEx(k, "ProxyOverride", 0, winreg.REG_SZ, b.get("override", ""))
        os.remove(PROXY_BACKUP)
    except Exception:
        pass
    _refresh_inet()


def set_autostart(on: bool):
    if not IS_WIN:
        return
    import winreg
    cmd = '"%s" --minimized' % sys.executable if getattr(sys, "frozen", False) else \
        '"%s" "%s" --minimized' % (sys.executable, os.path.abspath(sys.argv[0]))
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except OSError:
                pass


# -------------------------------------------------------- SOCKS probe
def _read_full(s, n):
    buf = b""
    while len(buf) < n:
        c = s.recv(n - len(buf))
        if not c:
            raise OSError("eof")
        buf += c
    return buf


def socks_get(port: int, host: str, path: str, timeout: float = 6.0):
    """HTTP GET through the local SOCKS5 proxy. Returns (ms to first byte, text) or None."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
            s.settimeout(timeout)
            t0 = time.perf_counter()
            s.sendall(b"\x05\x01\x00")
            if _read_full(s, 2) != b"\x05\x00":
                return None
            hb = host.encode()
            s.sendall(b"\x05\x01\x00\x03" + bytes([len(hb)]) + hb + b"\x00\x50")
            h = _read_full(s, 4)
            if h[1] != 0:
                return None
            atyp = h[3]
            if atyp == 1:
                _read_full(s, 6)
            elif atyp == 4:
                _read_full(s, 18)
            else:
                _read_full(s, _read_full(s, 1)[0] + 2)
            s.sendall(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode())
            first = s.recv(1)
            if not first:
                return None
            ms = int((time.perf_counter() - t0) * 1000)
            data = first
            try:
                while len(data) < 4096:
                    c = s.recv(1024)
                    if not c:
                        break
                    data += c
            except OSError:
                pass
            return ms, data.decode("latin-1")
    except OSError:
        return None


# ------------------------------------------------------ Aether / sing-box
def aether_args(s: Settings, fresh: bool):
    a = ["--config", os.path.join(DATA_DIR, "aether", "aether.toml"),
         "--bind", f"127.0.0.1:{s.socks_port}"]
    if s.mode == "proxy" and s.system_proxy:
        a += ["--http-proxy", f"127.0.0.1:{s.http_port}"]

    proto = s.protocol
    a += {"wg": ["--protocol", "wg"], "masque": ["--protocol", "masque"],
          "gool": ["--protocol", "gool"], "gool_classic": ["--gool-classic"],
          "mim": ["--protocol", "mim"]}[proto]
    if proto in ("masque", "mim"):
        a.append("--h2" if s.carrier == "h2" else "--h3")

    ep, ep2 = clean_endpoint(s.endpoint), clean_endpoint(s.endpoint2)
    if proto == "masque" and ep:
        a += ["--peer", ep] + (["--h2-peer", ep] if s.carrier == "h2" else [])
    elif proto == "wg" and ep:
        a += ["--peer", ep]
    elif proto == "gool":
        if ep: a += ["--peer", ep]
        if ep2: a += ["--gool-peer", ep2]
    elif proto == "gool_classic":
        if ep: a += ["--wiw-outer", ep]
        if ep2: a += ["--wiw-inner", ep2]
    elif proto == "mim":
        if ep: a += ["--mim-outer", ep]
        if ep2: a += ["--mim-inner", ep2]

    a += ["--scan", s.scan]
    if s.noize != "default":
        a += ["--noize", s.noize]
    a.append({"6": "-6", "dual": "--dual"}.get(s.ip_version, "-4"))
    a.append("--no-quick-reconnect" if (fresh or not s.quick_reconnect) else "--quick-reconnect")
    if s.dns.strip():
        a += ["--dns", csv(s.dns)]
    if s.route_block.strip():
        a += ["--route-block", csv(s.route_block)]
    if s.route_direct.strip():
        a += ["--route-direct", csv(s.route_direct)]
    if s.upstream.strip():
        a += ["--upstream", s.upstream.strip()]
    if s.perf != "auto":
        a += ["--perf", s.perf]
    a += split_args(s.extra_args)
    return a


def singbox_config(s: Settings) -> dict:
    v6 = s.ip_version != "4"
    addr = ["172.19.0.1/30"] + (["fdfe:dcba:9876::1/126"] if v6 else [])
    dns_server = (csv(s.dns).split(",")[0] if s.dns.strip() else "") or "1.1.1.1"
    return {
        "log": {"level": "warn", "timestamp": True},
        "dns": {
            "servers": [{"type": "tcp", "tag": "remote", "server": dns_server, "detour": "proxy"}],
            "strategy": "prefer_ipv4" if v6 else "ipv4_only",
        },
        "inbounds": [{
            "type": "tun", "tag": "tun-in", "interface_name": "8VPN",
            "address": addr, "mtu": s.mtu_v(), "auto_route": True, "stack": s.tun_stack,
        }],
        "outbounds": [
            {"type": "socks", "tag": "proxy", "server": "127.0.0.1", "server_port": s.socks_port, "version": "5"},
            {"type": "direct", "tag": "direct"},
        ],
        "route": {
            "auto_detect_interface": True,
            "find_process": True,
            "rules": [
                {"action": "sniff"},
                # Aether's own traffic to the gateway must never enter the tunnel (it would loop).
                {"process_name": ["aether.exe", "sing-box.exe"], "outbound": "direct"},
                {"protocol": "dns", "action": "hijack-dns"},
                # Refuse QUIC so apps fall back to TCP at once instead of waiting on a slow UDP relay.
                {"network": "udp", "port": 443, "action": "reject"},
                {"ip_is_private": True, "outbound": "direct"},
            ],
            "final": "proxy",
        },
    }


class Fatal(Exception):
    """A problem that retrying cannot fix. The text is a message key for the UI."""


# --------------------------------------------------------- controller
class Controller(QObject):
    status = pyqtSignal(str, int, int)  # phase, attempt, tries
    message = pyqtSignal(str)           # message key shown under the button ("" clears it)
    log = pyqtSignal(str)
    ping = pyqtSignal(int)              # ms, -1 = unknown
    traffic = pyqtSignal(float, float)  # download B/s, upload B/s
    exit_info = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.phase = "idle"
        self.logs = deque(maxlen=500)
        self._thread = None
        self._stop = threading.Event()
        self._rescan = threading.Event()
        self._aether = None
        self._singbox = None
        self._sb_started = False
        self._proxy_on = False

    # ---- public
    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            return
        self._stop.clear()
        self._rescan.clear()
        self.message.emit("")
        self._thread = threading.Thread(target=self._run, name="8vpn-controller", daemon=True)
        self._thread.start()

    def stop(self):
        if self.running:
            self._stop.set()
            self._set("stopping")

    def rescan(self):
        if self.phase == "connected":
            self._rescan.set()

    def shutdown(self):
        """Blocking stop for application exit."""
        self._stop.set()
        t = self._thread
        if t and t.is_alive():
            t.join(8)
        self._teardown()

    # ---- internals
    def _set(self, phase, attempt=0, tries=0):
        self.phase = phase
        self.status.emit(phase, attempt, tries)

    def _log(self, line: str):
        line = _ansi.sub("", line).rstrip()
        if not line:
            return
        line = time.strftime("%H:%M:%S  ") + line
        self.logs.append(line)
        self.log.emit(line)

    def _sleep(self, sec: float):
        self._stop.wait(sec)

    def _run(self):
        s = S
        tries = s.tries()
        attempt, fresh, first = 0, False, True
        try:
            while not self._stop.is_set():
                attempt += 1
                self._set("connecting" if first else "reconnecting", attempt, tries)
                self.message.emit("")
                ok = self._bring_up(s, fresh)
                if self._stop.is_set():
                    break
                if ok:
                    first, attempt = False, 0
                    self._set("connected", 0, tries)
                    threading.Thread(target=self._fetch_exit, args=(s.socks_port,), daemon=True).start()
                    reason = self._monitor(s)
                    if self._stop.is_set():
                        break
                    self._log(f"link lost: {reason}")
                    self.message.emit(reason)
                    self.ping.emit(-1)
                    self.traffic.emit(0, 0)
                    self.exit_info.emit("")
                    self._teardown()
                    fresh = bool(s.fresh_after_drop) or reason == "rescan"
                    self._sleep(s.retry_s())
                    continue
                self._teardown()
                if attempt >= tries:
                    self.message.emit("connect_failed")
                    break
                fresh = True
                self._sleep(s.retry_s())
        except Fatal as e:
            self._log(f"fatal: {e}")
            self.message.emit(str(e))
        except Exception as e:  # never let the worker die silently
            self._log(f"error: {e!r}")
            self.message.emit("connect_failed")
        finally:
            self._set("stopping") if self._stop.is_set() else None
            self._teardown()
            self.ping.emit(-1)
            self.traffic.emit(0, 0)
            self.exit_info.emit("")
            self._set("idle")

    def _bring_up(self, s: Settings, fresh: bool) -> bool:
        if not IS_WIN:
            raise Fatal("windows_only")
        if not os.path.exists(AETHER_EXE):
            raise Fatal("core_missing")
        vpn = s.mode == "vpn"
        if vpn:
            if not (os.path.exists(SINGBOX_EXE) and os.path.exists(WINTUN_DLL)):
                raise Fatal("core_missing")
            if not is_admin():
                raise Fatal("need_admin")
        if port_open(s.socks_port):
            raise Fatal("port_busy")

        # 1) Aether
        args = aether_args(s, fresh)
        os.makedirs(os.path.join(DATA_DIR, "aether"), exist_ok=True)
        self._log("exec: aether " + " ".join(args))
        self._aether = subprocess.Popen(
            [AETHER_EXE] + args, cwd=os.path.join(DATA_DIR, "aether"),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
        threading.Thread(target=self._pump, args=(self._aether, "aether"), daemon=True).start()

        # Aether opens its SOCKS port only after the tunnel has been validated.
        limit = 300
        t0 = time.time()
        while not self._stop.is_set() and time.time() - t0 < limit:
            if self._aether.poll() is not None:
                self._log(f"core exited (code {self._aether.returncode})")
                return False
            if port_open(s.socks_port):
                break
            self._sleep(0.5)
        else:
            return False
        self._log("Aether is ready")

        # 2) mode specific part
        if vpn:
            return self._start_tun(s)
        if s.system_proxy:
            set_system_proxy(f"127.0.0.1:{s.http_port}")
            self._proxy_on = True
            self._log(f"system proxy set to 127.0.0.1:{s.http_port}")
        return True

    def _start_tun(self, s: Settings) -> bool:
        cfg_path = os.path.join(DATA_DIR, "singbox.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(singbox_config(s), f, indent=2)
        work = os.path.join(DATA_DIR, "singbox")
        os.makedirs(work, exist_ok=True)
        self._sb_started = False
        self._log("starting TUN (sing-box)")
        self._singbox = subprocess.Popen(
            [SINGBOX_EXE, "run", "-c", cfg_path, "-D", work], cwd=CORE_DIR,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
        threading.Thread(target=self._pump, args=(self._singbox, "tun"), daemon=True).start()
        t0 = time.time()
        while not self._stop.is_set() and time.time() - t0 < 20:
            if self._singbox.poll() is not None:
                self._log(f"sing-box exited (code {self._singbox.returncode})")
                self.message.emit("tun_failed")
                return False
            if self._sb_started:
                return True
            self._sleep(0.3)
        # no "started" line seen but still alive: accept, the monitor will notice real trouble
        return self._singbox.poll() is None

    def _pump(self, proc, tag):
        try:
            for raw in iter(proc.stdout.readline, b""):
                line = raw.decode("utf-8", "replace")
                if tag == "tun" and "started" in line:
                    self._sb_started = True
                self._log(("[tun] " if tag == "tun" else "") + line)
        except Exception:
            pass

    def _fetch_exit(self, port):
        r = socks_get(port, "www.cloudflare.com", "/cdn-cgi/trace", 15)
        if not r:
            return
        info = dict(l.split("=", 1) for l in r[1].splitlines() if "=" in l)
        ip = info.get("ip")
        if ip:
            self.exit_info.emit(f"{ip} ({info['loc']})" if info.get("loc") else ip)

    def _tun_counters(self):
        try:
            import psutil
            c = psutil.net_io_counters(pernic=True).get("8VPN")
            return (c.bytes_recv, c.bytes_sent) if c else None
        except Exception:
            return None

    def _monitor(self, s: Settings) -> str:
        """Returns the reason (message key) when the link is considered dead."""
        fails, last = 0, self._tun_counters()
        last_t = time.time()
        while not self._stop.is_set():
            if self._rescan.is_set():
                self._rescan.clear()
                return "rescan"
            if self._aether is None or self._aether.poll() is not None:
                return "core_exited"
            if s.mode == "vpn" and (self._singbox is None or self._singbox.poll() is not None):
                return "tun_exited"

            r = socks_get(s.socks_port, "cp.cloudflare.com", "/generate_204", 6) \
                or socks_get(s.socks_port, "www.gstatic.com", "/generate_204", 6)
            cur = self._tun_counters()
            now = time.time()
            if cur and last:
                dt = max(now - last_t, 0.001)
                self.traffic.emit((cur[0] - last[0]) / dt, (cur[1] - last[1]) / dt)
            busy = bool(cur and last and (cur[0] - last[0]) > 20_000)
            last, last_t = cur, now
            if r:
                fails = 0
                self.ping.emit(r[0])
            elif busy:
                pass  # probe starved by a running download: data is flowing, link is alive
            else:
                fails += 1
                self.ping.emit(-1)
                self._log(f"ping failed ({fails}/{s.ping_limit()})")
                if fails >= s.ping_limit():
                    return "ping_failed"
            # wait, but react to stop / rescan within half a second
            end = time.time() + s.ping_every()
            while time.time() < end and not self._stop.is_set() and not self._rescan.is_set():
                time.sleep(0.5)
                if self._aether is None or self._aether.poll() is not None:
                    break
        return "stopped"

    def _teardown(self):
        # TUN first (removes the routes), then the core, then the system proxy.
        for attr in ("_singbox", "_aether"):
            p = getattr(self, attr)
            setattr(self, attr, None)
            if p is not None:
                self._kill(p)
        if self._proxy_on:
            restore_system_proxy()
            self._proxy_on = False

    @staticmethod
    def _kill(p):
        try:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(2.5)
                except subprocess.TimeoutExpired:
                    pass
            if p.poll() is None:
                if IS_WIN:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                                   creationflags=NO_WINDOW, capture_output=True)
                else:
                    p.kill()
        except Exception:
            pass
