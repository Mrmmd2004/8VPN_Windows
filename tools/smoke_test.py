"""Opens every page offscreen and saves screenshots to ./preview (used by the GitHub workflow)."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PyQt6.QtWidgets import QApplication  # noqa: E402

import core  # noqa: E402
import main  # noqa: E402

app = QApplication([])
out = os.path.join(ROOT, "preview")
os.makedirs(out, exist_ok=True)
w = main.MainWindow(core.Controller())
w.show()


def snap(widget, name):
    app.processEvents()
    widget.grab().save(os.path.join(out, name + ".png"))


for lang in ("en", "fa"):
    core.S.d["language"] = lang
    core.S.d["theme"] = "dark"
    core.S.d["route"] = "aether"
    w.refresh()
    w.go_home()
    snap(w, f"{lang}-home")
    core.S.d["route"] = "aether_psiphon"
    w.home._panel_open = True
    w.refresh()
    snap(w, f"{lang}-home-psiphon-panel")
    w.open_settings(); snap(w, f"{lang}-settings")
    assert w.settings.section is None, "Settings must open on the list of sections"
    for key, _t, _i in main.SECTIONS:
        w.settings.open_section(key); snap(w, f"{lang}-settings-{key}")
    w.settings.close_section()
    w.open_logs(); snap(w, f"{lang}-logs")
    w.open_about(); snap(w, f"{lang}-about")
    sheet = main.RegionSheet(w, "DE", lambda cc: None)
    sheet.show(); snap(sheet, f"{lang}-region")
    sheet.close()

# Settings while a connection is running: the option groups must stay enabled
w.ctl.phase = "connected"
w.mark_dirty("settings"); w.open_settings(); snap(w, "en-settings-running")
assert all(b.isEnabled() for b in w.settings.findChildren(main.Btn)
           if b.variant == "chip"), "chips must not be locked while connected"
w.ctl.phase = "idle"
w.mark_dirty("settings")

core.S.d.update(language="en", theme="light", route="aether")
w.refresh(); w.go_home(); snap(w, "light-home")
print("UI smoke test OK ->", out)
