# 8 VPN for Windows

Small, light desktop client on the **Aether** core. Same idea as the Android app.

```
VPN mode  : apps -> Wintun (sing-box) -> SOCKS5 127.0.0.1:1819 -> Aether -> internet
Proxy mode: Windows system proxy -> Aether HTTP 127.0.0.1:1822 -> internet
```

- Python + PyQt6, Android-style pages (Home, Settings, Logs, About), dark/light, Persian (RTL) and English, tray icon
- Routes like the Android app: Aether, Aether → Psiphon, Aether → Tor, Psiphon only/→ Aether, Tor only/→ Aether, with Psiphon region and Tor bridge options
- Protocols: WireGuard, MASQUE, Gool, Gool classic, MASQUE-in-MASQUE
- Smart reconnect (core dies / pings fail), live ping, exit IP, speed (VPN mode)
- VPN mode asks for administrator rights (UAC); Proxy mode does not
- Credits: [Aether](https://github.com/CluvexStudio/Aether) (AGPL-3.0), [sing-box](https://github.com/SagerNet/sing-box), [Wintun](https://www.wintun.net). Licence: AGPL-3.0.
- Android version: <https://github.com/Mrmmd2004/8vpn>
- Telegram: <https://t.me/Clubapp8>

## Build (GitHub Actions)
The workflow also saves screenshots of every page as the `ui-preview` artifact.

1. Upload everything in this folder to the repo root (`Mrmmd2004/8VPN_Windows`).
2. **Actions -> Build Windows -> Run workflow**.
3. Download from the run page: `8VPN-Setup` (installer), `8VPN-Portable` (single file), `8VPN-Windows-zip` (folder).

## ساخت (فارسی)
۱. همه‌ی فایل‌ها را در ریشه‌ی مخزن آپلود کنید. ۲. Actions ← Build Windows ← Run workflow.
۳. فایل `8VPN-Windows-x64` را دانلود و از حالت زیپ خارج کنید و `8VPN.exe` را اجرا کنید.
