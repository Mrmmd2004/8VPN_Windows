# 8 VPN for Windows

Small, light desktop client on the **Aether** core. Same idea as the Android app.

```
VPN mode  : apps -> Wintun (sing-box) -> SOCKS5 127.0.0.1:1819 -> Aether -> internet
Proxy mode: Windows system proxy -> Aether HTTP 127.0.0.1:1822 -> internet
```

- Python + PyQt6, dark/light, Persian (RTL) and English, tray icon, logs window
- Protocols: WireGuard, MASQUE, Gool, Gool classic, MASQUE-in-MASQUE
- Smart reconnect (core dies / pings fail), live ping, exit IP, speed (VPN mode)
- VPN mode asks for administrator rights (UAC); Proxy mode does not
- Credits: [Aether](https://github.com/CluvexStudio/Aether) (AGPL-3.0), [sing-box](https://github.com/SagerNet/sing-box), [Wintun](https://www.wintun.net). Licence: AGPL-3.0.
- Telegram: <https://t.me/Clubapp8>

## Build (GitHub Actions)
1. Upload everything in this folder to the repo root (`Mrmmd2004/8VPN_Windows`).
2. **Actions -> Build Windows -> Run workflow**.
3. Download artifact `8VPN-Windows-x64`, unzip, run `8VPN.exe`.

## ساخت (فارسی)
۱. همه‌ی فایل‌ها را در ریشه‌ی مخزن آپلود کنید. ۲. Actions ← Build Windows ← Run workflow.
۳. فایل `8VPN-Windows-x64` را دانلود و از حالت زیپ خارج کنید و `8VPN.exe` را اجرا کنید.
