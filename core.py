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
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections import deque

from PyQt6.QtCore import QObject, pyqtSignal

APP_NAME = "8VPN"
VERSION = "3.8"
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
    "route": "aether",           # aether | aether_psiphon | aether_tor | psiphon_only | psiphon_reverse | tor_only | tor_reverse
    "protocol": "masque",        # wg | masque | gool | gool_classic | mim
    "psiphon_region": "",
    "psiphon_mode": "auto",      # auto | cdn
    "tor_bridges": "auto",       # auto | always | never
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
    "free_ports": True,          # on connect: close whatever already listens on our ports
    "autostart": False,
    "auto_connect": False,
    "start_minimized": False,
    "hide_on_close": False,      # False: the X button quits the app completely
    "split_mode": "off",         # off | include | exclude (VPN mode, by program name)
    "split_apps": "",            # comma separated program names, e.g. chrome.exe, telegram.exe
    "schema": 0,
}
SCHEMA = 3

PROTOCOLS = [
    ("wg", "WireGuard"),
    ("masque", "MASQUE"),
    ("gool", "WARP-in-MASQUE (Gool)"),
    ("gool_classic", "WARP-in-WARP (Gool classic)"),
    ("mim", "MASQUE-in-MASQUE"),
]


TOR_PORT, PSIPHON_PORT = 1820, 1821


class Route:
    def __init__(self, name, family, psiphon, tor, no_warp, reverse, label):
        self.name, self.family, self.psiphon, self.tor = name, family, psiphon, tor
        self.no_warp, self.reverse, self.label = no_warp, reverse, label

    @property
    def slow(self):
        return self.psiphon or self.tor


ROUTES = {r.name: r for r in (
    Route("aether", "aether", 0, 0, 0, 0, "Aether"),
    Route("aether_psiphon", "aether", 1, 0, 0, 0, "Aether → Psiphon"),
    Route("aether_tor", "aether", 0, 1, 0, 0, "Aether → Tor"),
    Route("psiphon_only", "psiphon", 1, 0, 1, 0, "Psiphon only"),
    Route("psiphon_reverse", "psiphon", 1, 0, 0, 1, "Psiphon → Aether"),
    Route("tor_only", "tor", 0, 1, 1, 0, "Tor only"),
    Route("tor_reverse", "tor", 0, 1, 0, 1, "Tor → Aether"),
)}


def route_of(s) -> Route:
    return ROUTES.get(s.route, ROUTES["aether"])


def exit_port(s) -> int:
    """Port whose SOCKS5 listener is the real exit (Psiphon / Tor sit behind their own port)."""
    r = route_of(s)
    if r.name == "aether_psiphon":
        return PSIPHON_PORT
    if r.name == "aether_tor":
        return TOR_PORT
    return s.socks_port


class Eff:
    """Read-only view of the settings with a few values overridden for one session
    (used to alternate HTTP/3 and HTTP/2 after a drop without touching the saved settings)."""

    def __init__(self, base):
        self.__dict__["_b"] = base
        self.__dict__["_o"] = {}

    def over(self, **kw):
        self._o.update(kw)

    def __getattr__(self, k):
        o = self.__dict__["_o"]
        return o[k] if k in o else getattr(self.__dict__["_b"], k)


def active_label(s=None) -> str:
    s = s or S
    r = route_of(s)
    proto = dict(PROTOCOLS).get(s.protocol, s.protocol)
    return {"aether": proto, "aether_psiphon": f"{proto} → Psiphon", "aether_tor": f"{proto} → Tor",
            "psiphon_reverse": "Psiphon → MASQUE (HTTP/2)", "tor_reverse": "Tor → MASQUE (HTTP/2)"}.get(r.name, r.label)


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
        self._migrate()
        self._sanitize()

    def _migrate(self):
        """One-time reset of the connection tuning to the Android 3.8 defaults (MASQUE over HTTP/2,
        3 attempts, 3 failed pings, fresh scan after a drop). Language, theme, ports, mode and the
        other personal options are kept."""
        d = self.d
        if d.get("schema", 0) < SCHEMA:
            for k in ("protocol", "carrier", "quick_reconnect", "fresh_after_drop", "max_tries",
                      "retry_delay_ms", "ping_fails", "ping_interval"):
                d[k] = DEFAULTS[k]
            d["schema"] = SCHEMA
            self.save()

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
        if not (1024 <= d["socks_port"] <= 65535) or d["socks_port"] in (TOR_PORT, PSIPHON_PORT):
            d["socks_port"] = 1819
        if d["route"] not in ROUTES:
            d["route"] = "aether"
        if not (1024 <= d["http_port"] <= 65535) or d["http_port"] in (d["socks_port"], TOR_PORT, PSIPHON_PORT):
            d["http_port"] = 1822 if d["socks_port"] != 1822 else 1823
        for k in ("max_tries", "ping_fails", "ping_interval", "mtu", "retry_delay_ms"):
            if not isinstance(d[k], int):
                d[k] = DEFAULTS[k]
        if d["split_mode"] not in ("off", "include", "exclude"):
            d["split_mode"] = "off"

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


def listening_pids(port: int) -> set:
    """PIDs that listen on a local TCP port (psutil first, netstat as fallback)."""
    pids = set()
    try:
        import psutil
        for c in psutil.net_connections(kind="tcp"):
            if c.status == psutil.CONN_LISTEN and c.laddr and c.laddr.port == port and c.pid:
                pids.add(c.pid)
        if pids:
            return pids
    except Exception:
        pass
    if IS_WIN:
        try:
            out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True,
                                 creationflags=NO_WINDOW, timeout=15).stdout
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[0] == "TCP" and parts[3].upper() == "LISTENING" \
                        and parts[1].rsplit(":", 1)[-1] == str(port) and parts[4].isdigit():
                    pids.add(int(parts[4]))
        except Exception:
            pass
    return pids


def free_port(port: int, log=print) -> bool:
    """Kill whatever listens on `port`. Returns True when the port is free afterwards."""
    if not port_open(port):
        return True
    me = os.getpid()
    for pid in listening_pids(port) - {0, 4, me}:
        log(f"port {port} is used by PID {pid}, closing it")
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           creationflags=NO_WINDOW, capture_output=True, timeout=15)
        except Exception as e:
            log(f"could not close PID {pid}: {e}")
    for _ in range(20):
        if not port_open(port):
            return True
        time.sleep(0.25)
    return False


def kill_leftovers(log=print):
    """Close cores left behind by a crashed or force-closed earlier session."""
    for name in ("aether.exe", "sing-box.exe", "psiphon-tunnel-core.exe", "lyrebird.exe"):
        try:
            r = subprocess.run(["taskkill", "/F", "/T", "/IM", name], creationflags=NO_WINDOW,
                               capture_output=True, timeout=15)
            if r.returncode == 0:
                log(f"closed leftover {name}")
        except Exception:
            pass


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
    """Start with Windows. The app needs admin rights, and Windows silently skips elevated
    programs listed in the Run key, so a Scheduled Task with the highest privileges is used."""
    if not IS_WIN:
        return
    import tempfile
    import winreg
    try:  # remove the old Run-key entry written by earlier versions
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, APP_NAME)
    except OSError:
        pass
    run = lambda *a: subprocess.run(["schtasks", *a], capture_output=True, creationflags=NO_WINDOW, timeout=30)
    if not on:
        run("/Delete", "/TN", APP_NAME, "/F")
        return
    if getattr(sys, "frozen", False):
        exe, args = sys.executable, "--minimized"
    else:
        exe, args = sys.executable, '"%s" --minimized' % os.path.abspath(sys.argv[0])
    esc = lambda t: t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    user = esc(os.environ.get("USERDOMAIN", "") + "\\" + os.environ.get("USERNAME", ""))
    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers><LogonTrigger><Enabled>true</Enabled><UserId>{user}</UserId><Delay>PT5S</Delay></LogonTrigger></Triggers>
  <Principals><Principal id="Author"><UserId>{user}</UserId><LogonType>InteractiveToken</LogonType><RunLevel>HighestAvailable</RunLevel></Principal></Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <StartWhenAvailable>true</StartWhenAvailable>
  </Settings>
  <Actions Context="Author"><Exec><Command>{esc(exe)}</Command><Arguments>{esc(args)}</Arguments></Exec></Actions>
</Task>"""
    p = os.path.join(tempfile.gettempdir(), "8vpn_task.xml")
    with open(p, "w", encoding="utf-16") as f:
        f.write(xml)
    try:
        run("/Create", "/TN", APP_NAME, "/XML", p, "/F")
    finally:
        try:
            os.remove(p)
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


def socks_download(port: int, host: str, path: str, max_bytes: int, budget: float):
    """Downloads up to max_bytes over plain HTTP through the SOCKS5 port.
    Returns (status, body bytes, ms) or None."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
            s.settimeout(5)
            s.sendall(b"\x05\x01\x00")
            if _read_full(s, 2) != b"\x05\x00":
                return None
            hb = host.encode()
            s.sendall(b"\x05\x01\x00\x03" + bytes([len(hb)]) + hb + b"\x00\x50")
            h = _read_full(s, 4)
            if h[1] != 0:
                return None
            _read_full(s, {1: 6, 4: 18}.get(h[3]) or (_read_full(s, 1)[0] + 2))
            t0 = time.perf_counter()
            s.sendall(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode())
            head, body, status, done = b"", 0, 0, False
            while time.perf_counter() - t0 < budget:
                try:
                    c = s.recv(16384)
                except socket.timeout:
                    break
                if not c:
                    break
                if not done:
                    head += c
                    end = head.find(b"\r\n\r\n")
                    if end >= 0:
                        done = True
                        parts = head.split(b"\r\n", 1)[0].split(b" ")
                        status = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                        body = len(head) - (end + 4)
                    elif len(head) > 8192:
                        break
                else:
                    body += len(c)
                if done and (status != 200 or body >= max_bytes):
                    break
            if not done:
                return None
            return status, body, int((time.perf_counter() - t0) * 1000)
    except OSError:
        return None


# ------------------------------------------------------------ updates
RELEASES_API = "https://api.github.com/repos/Mrmmd2004/8VPN_Windows/releases/latest"


def _ver_parts(v: str):
    out = []
    for p in re.split(r"[.\-_]", (v or "").strip().lstrip("vV")):
        m = re.match(r"\d+", p)
        out.append(int(m.group()) if m else 0)
    return out


def is_newer(remote: str, local: str) -> bool:
    a, b = _ver_parts(remote), _ver_parts(local)
    for i in range(max(len(a), len(b))):
        x = a[i] if i < len(a) else 0
        y = b[i] if i < len(b) else 0
        if x != y:
            return x > y
    return False


def check_update():
    """Asks GitHub for the latest release. Returns (tag, newer, download url). Raises on failure."""
    import urllib.request
    req = urllib.request.Request(RELEASES_API, headers={"Accept": "application/vnd.github+json",
                                                        "User-Agent": "8vpn-windows"})
    with urllib.request.urlopen(req, timeout=15) as r:
        j = json.load(r)
    tag = j["tag_name"]
    page = j.get("html_url") or "https://github.com/Mrmmd2004/8VPN_Windows/releases/latest"
    want = "portable" if CORE_DIR == _c2 else "setup"   # single-file build vs installed / zip build
    url = page
    for a in j.get("assets", []):
        if want in a.get("name", "").lower() and a.get("browser_download_url"):
            url = a["browser_download_url"]
            break
    return tag, is_newer(tag, VERSION), url


# ------------------------------------------------ network change watch
_defroute = re.compile(r"^\s*0\.0\.0\.0\s+0\.0\.0\.0\s+(\S+)\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+)\s*$")


def parse_default_route(text: str):
    """Best (lowest metric) IPv4 default route from `route print` output, ignoring our own TUN.
    Returns (gateway, interface address) or None. The columns are numbers, so this works in every
    Windows language."""
    best = None
    for line in (text or "").splitlines():
        m = _defroute.match(line)
        if not m:
            continue
        gw, ifc, metric = m.group(1), m.group(2), int(m.group(3))
        if ifc.startswith("172.19.0."):  # the 8VPN adapter
            continue
        if best is None or metric < best[0]:
            best = (metric, gw, ifc)
    return (best[1], best[2]) if best else None


def net_signature():
    """Identifies the physical default network (Wi-Fi / Ethernet / another router). None = offline."""
    if not IS_WIN:
        return None
    try:
        out = subprocess.run(["route", "print", "-4", "0.0.0.0"], capture_output=True, text=True,
                             creationflags=NO_WINDOW, timeout=10).stdout
        return parse_default_route(out)
    except Exception:
        return None


# ------------------------------------------------------ Aether / sing-box
def _pt_bin(name):
    p = os.path.join(CORE_DIR, "pt", name)
    return p if os.path.exists(p) else None


def psiphon_dir(slot: int = 0) -> str:
    """Psiphon data folder. A new slot is used when the old one is locked or broken."""
    return os.path.join(DATA_DIR, "aether", "psiphon" if slot == 0 else f"psiphon-{slot}")


def clean_psiphon_dirs(slot: int):
    keep = os.path.basename(psiphon_dir(slot))
    base = os.path.join(DATA_DIR, "aether")
    try:
        for n in os.listdir(base):
            p = os.path.join(base, n)
            if os.path.isdir(p) and (n == "psiphon" or n.startswith("psiphon-")) and n != keep:
                shutil.rmtree(p, ignore_errors=True)
    except OSError:
        pass


def aether_args(s, fresh: bool, psi_slot: int = 0):
    r = route_of(s)
    a = ["--config", os.path.join(DATA_DIR, "aether", "aether.toml"),
         "--bind", f"127.0.0.1:{s.socks_port}"]
    if s.mode == "proxy" and s.system_proxy:
        a += ["--http-proxy", f"127.0.0.1:{s.http_port}"]

    a += {"aether_psiphon": ["--psiphon"], "psiphon_only": ["--psiphon-only"], "psiphon_reverse": ["--psiphon-reverse"],
          "aether_tor": ["--tor"], "tor_only": ["--tor-only"], "tor_reverse": ["--tor-reverse"]}.get(r.name, [])

    if not r.no_warp:
        proto = "masque" if r.reverse else s.protocol  # reverse routes carry MASQUE over HTTP/2
        a += {"wg": ["--protocol", "wg"], "masque": ["--protocol", "masque"],
              "gool": ["--protocol", "gool"], "gool_classic": ["--gool-classic"],
              "mim": ["--protocol", "mim"]}[proto]
        h2 = r.reverse or s.carrier == "h2"
        if r.reverse:
            a.append("--h2")
        elif proto in ("masque", "mim"):
            a.append("--h2" if s.carrier == "h2" else "--h3")

        ep, ep2 = clean_endpoint(s.endpoint), clean_endpoint(s.endpoint2)
        if proto == "masque" and ep:
            a += ["--peer", ep] + (["--h2-peer", ep] if h2 else [])
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

    if r.psiphon:
        exe = _pt_bin("psiphon-tunnel-core.exe")
        if exe:
            a += ["--psiphon-bin", exe]
        a += ["--psiphon-dir", psiphon_dir(psi_slot)]
        if r.name != "psiphon_only":
            a += ["--psiphon-bind", f"127.0.0.1:{PSIPHON_PORT}"]
        a += ["--psiphon-mode", s.psiphon_mode]
        if s.psiphon_region.strip():
            a += ["--psiphon-region", s.psiphon_region.strip().upper()]
    if r.tor:
        a += ["--tor-dir", os.path.join(DATA_DIR, "aether", "tor")]
        if r.name != "tor_only":
            a += ["--tor-bind", f"127.0.0.1:{TOR_PORT}"]
        if s.tor_bridges == "always":
            a.append("--tor-bridges")
        elif s.tor_bridges == "never":
            a.append("--no-tor-bridges")
    if s.perf != "auto":
        a += ["--perf", s.perf]
    a += split_args(s.extra_args)
    return a


def split_names(v: str):
    """Program names from the split-tunnel text (adds .exe when missing)."""
    out = []
    for x in re.split(r"[,\n;]+", v or ""):
        x = x.strip().strip('"')
        if not x:
            continue
        x = os.path.basename(x.replace("\\", "/"))
        out.append(x if x.lower().endswith(".exe") else x + ".exe")
    return list(dict.fromkeys(out))


def singbox_config(s) -> dict:
    r = route_of(s)
    v6 = s.ip_version != "4" and not r.slow
    addr = ["172.19.0.1/30"] + (["fdfe:dcba:9876::1/126"] if v6 else [])
    dns_server = (csv(s.dns).split(",")[0] if s.dns.strip() else "") or "1.1.1.1"
    # Everything that runs from the core folder (aether, psiphon, lyrebird, ...) must leave directly.
    direct_rule = {"process_path_regex": ["(?i)^" + re.escape(CORE_DIR) + r"\\.*"],
                   "process_name": ["aether.exe", "sing-box.exe", "psiphon-tunnel-core.exe", "lyrebird.exe"],
                   "outbound": "direct"}
    rules = [
        {"action": "sniff"},
        direct_rule,
    ]
    apps = split_names(s.split_apps)
    if apps and s.split_mode == "exclude":
        rules.append({"process_name": apps, "outbound": "direct"})
    elif apps and s.split_mode == "include":
        rules.append({"process_name": apps, "invert": True, "outbound": "direct"})
    rules += [
        {"protocol": "dns", "action": "hijack-dns"},
        # Refuse QUIC so apps fall back to TCP at once instead of waiting on a slow UDP relay.
        {"network": "udp", "port": 443, "action": "reject"},
    ]
    if r.tor:
        rules.append({"network": "udp", "action": "reject"})  # Tor has no UDP at all
    rules.append({"ip_is_private": True, "outbound": "direct"})
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
            {"type": "socks", "tag": "proxy", "server": "127.0.0.1", "server_port": exit_port(s), "version": "5"},
            {"type": "direct", "tag": "direct"},
        ],
        "route": {"auto_detect_interface": True, "find_process": True, "rules": rules, "final": "proxy"},
    }


class Fatal(Exception):
    """A problem that retrying cannot fix. The text is a message key for the UI."""


# --------------------------------------------------------- controller
class Controller(QObject):
    status = pyqtSignal(str, int, int)  # phase, attempt, tries
    message = pyqtSignal(str)           # message key shown under the button ("" clears the error);
                                        # "key|arg" carries one number (r_pings|3, r_start|2)
    log = pyqtSignal(str)
    ping = pyqtSignal(int)              # ms, -1 = unknown
    traffic = pyqtSignal(float, float)  # download B/s, upload B/s
    exit_info = pyqtSignal(str)
    speed = pyqtSignal(float)           # link speed B/s, -1 = measuring / unknown

    def __init__(self):
        super().__init__()
        self.phase = "idle"
        self.logs = deque(maxlen=500)
        self._thread = None
        self._stop = threading.Event()
        self._rescan = threading.Event()
        self._net_changed = threading.Event()
        self._td_lock = threading.RLock()
        self._gen = 0                    # bumped on every start, so a late stop() cannot kill a new session
        self._aether = None
        self._singbox = None
        self._sb_started = False
        self._psiphon_ready = False
        self._socks_ready = False        # Aether validated the tunnel and opened its SOCKS port
        self._datastore_failed = False   # Psiphon could not open its database (a helper holds the lock)
        self._psi_slot = 0
        self._proxy_on = False
        self._connected_at = 0.0
        self._last_rx_at = 0.0           # last time data arrived for the apps (VPN mode)
        self._rx_bps = 0.0

    # ---- public
    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            return
        self._gen += 1
        self._stop.clear()
        self._rescan.clear()
        self._net_changed.clear()
        self.message.emit("")
        self._thread = threading.Thread(target=self._run, name="8vpn-controller", daemon=True)
        self._thread.start()

    def stop(self):
        if self.running:
            self._stop.set()
            self._set("stopping")
            # Close the TUN and the core right away: probes blocked on the local SOCKS port then fail
            # at once instead of waiting for their timeouts.
            gen = self._gen
            threading.Thread(target=lambda: self._gen == gen and self._teardown(), daemon=True).start()

    def rescan(self):
        if self.phase == "connected" and route_of(S).family == "aether":
            self._rescan.set()

    def shutdown(self):
        """Blocking stop for application exit."""
        self._stop.set()
        t = self._thread
        self._teardown()
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
        s = Eff(S)
        tries = s.tries()
        failures = cycle = 0
        ever_up = force_fresh = False
        self._psi_slot = 0
        self._net_changed.clear()
        watch_stop = threading.Event()
        threading.Thread(target=self._watch_net, args=(watch_stop,), daemon=True, name="8vpn-netwatch").start()
        try:
            while not self._stop.is_set():
                attempt = failures + 1
                self._set("reconnecting" if ever_up else "connecting", attempt, tries)
                self.message.emit("")
                # A fresh scan only after a real drop or after a whole round of failed attempts.
                fresh = cycle > 0 or force_fresh
                force_fresh = False
                self._log(f"Starting core, attempt {attempt} of {tries}" + (" (fresh scan)" if fresh else ""))
                ok = self._bring_up(s, fresh)
                if self._stop.is_set():
                    break
                if ok:
                    ever_up, failures, cycle = True, 0, 0
                    self._net_changed.clear()
                    self._connected_at = self._last_rx_at = time.time()
                    self._set("connected", 0, tries)
                    self._log(f"Connected via {active_label(s)}")
                    threading.Thread(target=self._after_connect, args=(exit_port(s),), daemon=True).start()
                    stats_stop = threading.Event()
                    if s.mode == "vpn":
                        threading.Thread(target=self._stats, args=(stats_stop,), daemon=True, name="8vpn-stats").start()
                    try:
                        reason = self._monitor(s)
                    finally:
                        stats_stop.set()
                    if self._stop.is_set():
                        break
                    self._log(f"link lost: {reason}")
                    self.ping.emit(-1)
                    self.traffic.emit(0, 0)
                    self.exit_info.emit("")
                    self.speed.emit(-1)
                    self._teardown()
                    if reason == "network":
                        # Wi-Fi <-> Ethernet (or a new router): the old sockets are dead, so reconnect
                        # at once with quick reconnect instead of waiting for the pings to fail.
                        self.message.emit("r_network")
                        self._log("Network changed: reconnecting right away")
                        self._sleep(s.retry_s())
                        continue
                    if reason == "rescan":
                        self.message.emit("r_rescan")
                        self._log("Rescan requested: restarting the core with a fresh scan")
                        force_fresh = True
                        self._sleep(1.0)
                        continue
                    self.message.emit(reason)
                    # The gateway that just dropped is often the very one being throttled.
                    if s.fresh_after_drop:
                        force_fresh = True
                    # QUIC (h3) is often cut by the network after a few seconds, so alternate between
                    # h3 and h2 on each drop to find one that stays up.
                    r = route_of(s)
                    if r.family == "aether" and not r.no_warp and s.protocol in ("masque", "mim"):
                        nxt = "h2" if s.carrier == "h3" else "h3"
                        self._log(f"Link dropped. Trying {nxt.upper()} on the next attempt")
                        s.over(carrier=nxt)
                    self._sleep(s.retry_s())
                    continue

                # the core could not be started / did not become ready
                failures += 1
                self.message.emit(f"r_start|{attempt}")
                if route_of(s).psiphon and self._datastore_failed:
                    self._psi_slot += 1
                    self._log("Psiphon could not open its data folder: the next attempt uses a fresh one")
                self._teardown()
                if failures >= tries:
                    failures = 0
                    cycle += 1
                    if cycle >= 2:
                        self.message.emit("connect_failed")
                        break
                    self._log("No luck. Dropping everything and starting over with a fresh scan")
                self._sleep(s.retry_s())
        except Fatal as e:
            self._log(f"fatal: {e}")
            self.message.emit(str(e))
        except Exception as e:  # never let the worker die silently
            self._log(f"error: {e!r}")
            self.message.emit("connect_failed")
        finally:
            watch_stop.set()
            self._set("stopping") if self._stop.is_set() else None
            self._teardown()
            self.ping.emit(-1)
            self.traffic.emit(0, 0)
            self.exit_info.emit("")
            self.speed.emit(-1)
            self._set("idle")

    def _bring_up(self, s, fresh: bool) -> bool:
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
        r = route_of(s)
        ports = {s.socks_port, exit_port(s)}
        if s.mode == "proxy" and s.system_proxy:
            ports.add(s.http_port)
        if s.free_ports and any(port_open(p) for p in ports):
            kill_leftovers(self._log)
            time.sleep(0.5)
            for p in sorted(ports):
                if port_open(p):
                    free_port(p, self._log)
        busy = [p for p in sorted(ports) if port_open(p)]
        if busy:
            self._log("ports still in use: " + ", ".join(map(str, busy)))
            raise Fatal("port_busy")
        self._psiphon_ready = False
        self._socks_ready = False
        self._datastore_failed = False

        # 1) Aether
        args = aether_args(s, fresh, self._psi_slot)
        os.makedirs(os.path.join(DATA_DIR, "aether"), exist_ok=True)
        if r.psiphon:
            clean_psiphon_dirs(self._psi_slot)  # a failed earlier slot may be broken or locked
        self._log("exec: aether " + " ".join(args))
        self._aether = subprocess.Popen(
            [AETHER_EXE] + args, cwd=os.path.join(DATA_DIR, "aether"),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
        threading.Thread(target=self._pump, args=(self._aether, "aether"), daemon=True).start()

        # First route search may take long on a bad network (Tor most of all).
        limit = 720 if r.tor else 420 if r.psiphon else 300
        port = exit_port(s)
        t0 = time.time()
        while not self._stop.is_set() and time.time() - t0 < limit:
            if self._aether is None or self._aether.poll() is not None:
                code = self._aether.returncode if self._aether else "?"
                self._log(f"core exited (code {code})")
                return False
            waited = time.time() - t0
            # Psiphon / Tor open their port at once; Aether's SOCKS port opens once WARP is validated.
            # For plain Aether the port can accept connections before the tunnel is validated, so wait
            # for Aether's own "validated" line before showing Connected.
            if port_open(port) and (port == s.socks_port or port_open(s.socks_port)) \
                    and (not r.psiphon or self._psiphon_ready or waited > 60) \
                    and (r.name != "aether" or self._socks_ready or waited > 90):
                break
            self._sleep(0.12)
        else:
            return False
        self._log("core is ready")

        # 2) mode specific part
        if vpn:
            return self._start_tun(s)
        if s.system_proxy:
            set_system_proxy(f"127.0.0.1:{s.http_port}")
            self._proxy_on = True
            self._log(f"system proxy set to 127.0.0.1:{s.http_port}")
        return True

    def _start_tun(self, s) -> bool:
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
            if self._singbox is None or self._singbox.poll() is not None:
                self._log("sing-box exited")
                self.message.emit("tun_failed")
                return False
            if self._sb_started:
                return True
            self._sleep(0.1)
        # no "started" line seen but still alive: accept, the monitor will notice real trouble
        return self._singbox is not None and self._singbox.poll() is None

    def _pump(self, proc, tag):
        try:
            for raw in iter(proc.stdout.readline, b""):
                line = raw.decode("utf-8", "replace")
                if tag == "tun" and "started" in line:
                    self._sb_started = True
                if tag == "aether":
                    if "psiphon is ready" in line:
                        self._psiphon_ready = True
                    if "socks5 server listening" in line or "tunnel validated" in line:
                        self._socks_ready = True
                    if "tryDatastoreOpenDB" in line or "openDataStore" in line:
                        self._datastore_failed = True
                self._log(("[tun] " if tag == "tun" else "") + line)
        except Exception:
            pass

    def _after_connect(self, port):
        self._fetch_exit(port)
        self._speed_test(port)

    def _fetch_exit(self, port):
        # The tunnel (especially Psiphon) may need a moment: retry a few times before giving up.
        r = None
        for _ in range(4):
            if self._stop.is_set():
                return
            r = socks_get(port, "www.cloudflare.com", "/cdn-cgi/trace", 15)
            if r:
                break
            self._sleep(3)
        if not r:
            return
        info = dict(l.split("=", 1) for l in r[1].splitlines() if "=" in l)
        ip = info.get("ip")
        if ip:
            self.exit_info.emit(f"{ip} ({info['loc']})" if info.get("loc") else ip)

    def _speed_test(self, port):
        self._sleep(2)  # let the tunnel settle
        for host, path in (("speed.cloudflare.com", "/__down?bytes=1000000"),
                           ("cachefly.cachefly.net", "/1mb.test"),
                           ("ipv4.download.thinkbroadband.com", "/1MB.zip")):
            if self._stop.is_set():
                return
            r = socks_download(port, host, path, 1_000_000, 10)
            if r and r[0] == 200 and r[1] > 0 and r[2] > 0:
                bps = r[1] * 1000 / r[2]
                self._log(f"Speed test: {int(bps / 1024)} KB/s ({r[1]} bytes in {r[2]} ms via {host})")
                self.speed.emit(bps)
                return
        self._log("Speed test: no result")

    def _tun_counters(self):
        try:
            import psutil
            c = psutil.net_io_counters(pernic=True).get("8VPN")
            return (c.bytes_recv, c.bytes_sent) if c else None
        except Exception:
            return None

    def _stats(self, stop_ev):
        """Once a second: speed shown on Home, and the time data last arrived (used by the monitor
        to tell a starved probe from a dead link)."""
        last, last_t = self._tun_counters(), time.time()
        while not stop_ev.wait(1.0) and not self._stop.is_set():
            cur, now = self._tun_counters(), time.time()
            if cur and last:
                dt = max(now - last_t, 0.001)
                rx, tx = max(cur[0] - last[0], 0) / dt, max(cur[1] - last[1], 0) / dt
                self._rx_bps = rx
                self.traffic.emit(rx, tx)
                if rx > 0:
                    self._last_rx_at = now
            last, last_t = cur, now
        self._rx_bps = 0.0

    def _watch_net(self, stop_ev):
        """Watches the physical default network (gateway + local address). A change while connected
        means Wi-Fi <-> Ethernet or a new router, so the monitor reconnects at once."""
        last = None
        while not stop_ev.is_set() and not self._stop.is_set():
            cur = net_signature()
            if cur:
                if last and cur != last and self.phase == "connected" and time.time() - self._connected_at > 3:
                    self._log(f"Default network changed ({last[1]} -> {cur[1]})")
                    self._net_changed.set()
                last = cur
            stop_ev.wait(3)

    def _core_dead(self, s) -> str:
        if self._aether is None or self._aether.poll() is not None:
            return "r_core"
        if s.mode == "vpn" and (self._singbox is None or self._singbox.poll() is not None):
            return "r_tun"
        return ""

    def _monitor(self, s) -> str:
        """Returns the reason when the link is considered dead: core exited, or too many probes in a
        row failed while no data was flowing either.

        Psiphon and Tor often stall a single new connection for many seconds while the rest of the
        traffic is fine, so for those routes the monitor is more patient: longer probe timeout, a
        higher failure limit, a longer pause between probes, and any data that arrived in the last
        20 s proves the link is alive. Dropping a working link is worse than waiting a little longer:
        every drop restarts the core and throws the gateway away."""
        slow = route_of(s).slow
        timeout = 25 if slow else 8
        limit = max(s.ping_limit(), 5) if slow else s.ping_limit()
        every = max(s.ping_every(), 8) if slow else s.ping_every()
        alive_window = 20.0 if slow else 0.0
        fails = 0
        xp = exit_port(s)
        while not self._stop.is_set():
            if self._rescan.is_set():
                self._rescan.clear()
                return "rescan"
            if self._net_changed.is_set():
                self._net_changed.clear()
                return "network"
            dead = self._core_dead(s)
            if dead:
                self._log("Core is not running anymore" if dead == "r_core" else "The VPN adapter is not running anymore")
                return dead

            r = socks_get(xp, "cp.cloudflare.com", "/generate_204", timeout) \
                or socks_get(xp, "www.gstatic.com", "/generate_204", timeout)
            if self._stop.is_set():
                break
            if self._net_changed.is_set():
                self._net_changed.clear()
                return "network"
            now = time.time()
            recent = self._rx_bps > 0 or (alive_window > 0 and now - self._last_rx_at < alive_window)
            if r:
                fails = 0
                self.ping.emit(r[0])
            elif recent:
                # The probe is starved by a busy download or is just slow, but data is arriving.
                fails = 0
                self.ping.emit(-1)
            else:
                fails += 1
                self.ping.emit(-1)
                self._log(f"ping failed ({fails}/{limit}), last data {int(now - self._last_rx_at)} s ago")
                if fails >= limit:
                    return f"r_pings|{limit}"
            # wait, but react to stop / rescan / network change within half a second
            end = time.time() + every
            while time.time() < end and not self._stop.is_set() and not self._rescan.is_set() \
                    and not self._net_changed.is_set():
                time.sleep(0.5)
                if self._core_dead(s):
                    break
        return "stopped"

    def _teardown(self):
        with self._td_lock:
            # TUN first (removes the routes), then the core, then the system proxy.
            for attr in ("_singbox", "_aether"):
                p = getattr(self, attr)
                setattr(self, attr, None)
                if p is not None:
                    self._kill(p)
            if self._proxy_on:
                restore_system_proxy()
                self._proxy_on = False
            if IS_WIN:  # Psiphon/Tor helpers can outlive aether.exe and keep ports busy
                kill_leftovers(lambda m: None)

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
