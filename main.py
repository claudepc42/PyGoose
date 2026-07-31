import sys
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QPainter
from PyQt6.QtCore import Qt

from pygoose.goose.overlay import Overlay
from pygoose.goose.goose import Goose
from pygoose.goose.config import load_config


def _is_ax_trusted() -> bool:
    try:
        import ctypes
        appservices = ctypes.cdll.LoadLibrary(
            '/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices'
        )
        appservices.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(appservices.AXIsProcessTrusted())
    except Exception:
        return True


def _request_accessibility_macos():
    if not _is_ax_trusted():
        msg = QMessageBox()
        msg.setWindowTitle("Accessibility access needed")
        msg.setText(
            "PyGoose needs Accessibility permission to steal your mouse.\n\n"
            "Go to System Settings → Privacy & Security → Accessibility "
            "and add PyGoose to the list."
        )
        msg.exec()


def _detach_from_terminal():
    """Kill the parent shell so Terminal closes its window.

    Only runs for frozen binaries (Finder-launched). When a developer runs
    `python main.py` their shell IS our PPID — we must not kill it.

    SIGHUP rather than SIGTERM: the shell exits as if its terminal closed,
    which triggers Terminal's "close window on shell exit" behavior. SIGTERM
    exits with code 143 (non-clean) and may leave a "Process completed" banner.
    """
    if not getattr(sys, 'frozen', False):
        return
    import signal
    import threading
    import os
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    ppid = os.getppid()

    def _kill_shell():
        import time
        time.sleep(1)
        try:
            os.kill(ppid, signal.SIGHUP)
        except ProcessLookupError:
            pass

    threading.Thread(target=_kill_shell, daemon=True).start()


def main():
    if sys.platform == "darwin":
        _detach_from_terminal()

    # Ensure Qt uses the exact DPI scale factor (no rounding of e.g. 1.25 → 1)
    # so that logical-pixel geometry and QCursor.pos() stay in the same coordinate space.
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)

    if sys.platform == "darwin":
        _request_accessibility_macos()

    config = load_config()
    goose = Goose(config=config)

    def on_tick():
        goose.tick()

    def render(painter: QPainter):
        goose.render(painter)

    overlay = Overlay(on_tick=on_tick)
    overlay.set_render_fn(render)
    overlay.set_dirty_rect_fn(goose.dirty_rect)
    overlay.grabKeyboard()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
