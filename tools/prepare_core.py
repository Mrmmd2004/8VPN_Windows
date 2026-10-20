"""Downloads Aether, sing-box and Wintun and lays them out in ./core (used by the GitHub workflow).

    core/aether.exe, core/pt/...   (whole Aether folder: Psiphon and Tor transports live in pt/)
    core/sing-box.exe
    core/wintun.dll
    core/versions.txt
"""
import json
import os
import shutil
import sys
import urllib.request
import zipfile

AETHER_REF = os.environ.get("AETHER_REF", "v2.3.0")
SINGBOX_VERSION = os.environ.get("SINGBOX_VERSION", "1.13.21")
WINTUN_VERSION = os.environ.get("WINTUN_VERSION", "0.14.1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE, DL = os.path.join(ROOT, "core"), os.path.join(ROOT, "dl")


def get(url, dest, headers=None, tries=4):
    import time
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) 8vpn-build"
    last = None
    for i in range(1, tries + 1):
        print(f"GET {url} (try {i}/{tries})", flush=True)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua, **(headers or {})})
            with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
                shutil.copyfileobj(r, f)
            print("  ->", os.path.getsize(dest), "bytes", flush=True)
            return
        except Exception as e:  # noqa: BLE001
            last = e
            print("  failed:", e, flush=True)
            time.sleep(3 * i)
    raise SystemExit(f"download failed after {tries} tries: {url}\n{last}")


def unzip(path, to):
    with zipfile.ZipFile(path) as z:
        z.extractall(to)


def find(root, name):
    for d, _, files in os.walk(root):
        if name in files:
            return os.path.join(d, name)
    raise SystemExit(f"{name} not found under {root}")


def aether_asset_url():
    base = f"https://github.com/CluvexStudio/Aether/releases/download/{AETHER_REF}/aether-windows-x86_64.zip"
    try:  # ask the API for the real asset name first (in case it was renamed)
        h = {"Accept": "application/vnd.github+json"}
        if os.environ.get("GITHUB_TOKEN"):
            h["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
        req = urllib.request.Request(
            f"https://api.github.com/repos/CluvexStudio/Aether/releases/tags/{AETHER_REF}", headers={"User-Agent": "8vpn-build", **h})
        data = json.load(urllib.request.urlopen(req, timeout=60))
        names = [a for a in data.get("assets", []) if a["name"].lower().endswith(".zip")]
        for a in names:
            n = a["name"].lower()
            if "windows" in n and ("x86_64" in n or "amd64" in n or "x64" in n) and "legacy" not in n:
                return a["browser_download_url"]
        print("assets seen:", [a["name"] for a in data.get("assets", [])])
    except Exception as e:
        print("release lookup failed, using the default name:", e)
    return base


def main():
    shutil.rmtree(CORE, ignore_errors=True)
    shutil.rmtree(DL, ignore_errors=True)
    os.makedirs(CORE)
    os.makedirs(DL)

    get(aether_asset_url(), os.path.join(DL, "aether.zip"))
    get(f"https://github.com/SagerNet/sing-box/releases/download/v{SINGBOX_VERSION}/sing-box-{SINGBOX_VERSION}-windows-amd64.zip",
        os.path.join(DL, "singbox.zip"))
    get(f"https://www.wintun.net/builds/wintun-{WINTUN_VERSION}.zip", os.path.join(DL, "wintun.zip"))
    for n in ("aether", "singbox", "wintun"):
        unzip(os.path.join(DL, n + ".zip"), os.path.join(DL, n))

    aether_exe = find(os.path.join(DL, "aether"), "aether.exe")
    shutil.copytree(os.path.dirname(aether_exe), CORE, dirs_exist_ok=True)   # aether.exe + pt/ + ...
    shutil.copy2(find(os.path.join(DL, "singbox"), "sing-box.exe"), os.path.join(CORE, "sing-box.exe"))
    wt = [os.path.join(d, "wintun.dll") for d, _, fs in os.walk(os.path.join(DL, "wintun"))
          if "wintun.dll" in fs and os.path.basename(d).lower() == "amd64"]
    if not wt:
        raise SystemExit("wintun.dll (amd64) not found")
    shutil.copy2(wt[0], os.path.join(CORE, "wintun.dll"))
    with open(os.path.join(CORE, "versions.txt"), "w", encoding="utf-8") as f:
        f.write(f"aether={AETHER_REF}\nsingbox={SINGBOX_VERSION}\nwintun={WINTUN_VERSION}\n")

    print("\ncore/ now contains:")
    for d, _, fs in os.walk(CORE):
        for fn in fs:
            p = os.path.join(d, fn)
            print("  ", os.path.relpath(p, CORE), os.path.getsize(p))
    if not os.path.isdir(os.path.join(CORE, "pt")):
        print("WARNING: core/pt is missing - Psiphon and Tor routes will not work with this Aether archive.")


if __name__ == "__main__":
    sys.exit(main())
