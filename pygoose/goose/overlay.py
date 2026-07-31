import sys
import ctypes
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QFont, QFontMetrics

from pygoose.engine.math_utils import lerp, clamp
from pygoose.engine.easings import exponential_ease_out

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
VK_ESCAPE = 0x1B

QUIT_ALPHA_INCREMENT = 0.00216666679
QUIT_ALPHA_DECREMENT = 0.0166666675
QUIT_THRESHOLD       = 0.99
QUIT_SHOW_THRESHOLD  = 0.2


def _macos_objc_send():
    lib = ctypes.CDLL('libobjc.dylib')
    lib.sel_registerName.restype = ctypes.c_void_p
    lib.sel_registerName.argtypes = [ctypes.c_char_p]
    lib.objc_getClass.restype = ctypes.c_void_p
    lib.objc_getClass.argtypes = [ctypes.c_char_p]

    def send(restype, extra_argtypes, obj, sel_name, *args):
        lib.objc_msgSend.restype = restype
        lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + extra_argtypes
        return lib.objc_msgSend(obj, lib.sel_registerName(sel_name), *args)

    NSApp = send(ctypes.c_void_p, [], lib.objc_getClass(b'NSApplication'), b'sharedApplication')
    windows = send(ctypes.c_void_p, [], NSApp, b'windows')
    count = send(ctypes.c_ulong, [], windows, b'count')
    return send, windows, count


def _macos_setup_overlay():
    """Set up the overlay window: click-through and stays visible when unfocused."""
    try:
        send, windows, count = _macos_objc_send()
        for i in range(count):
            win = send(ctypes.c_void_p, [ctypes.c_ulong], windows, b'objectAtIndex:', i)
            send(None, [ctypes.c_bool], win, b'setIgnoresMouseEvents:', True)
            send(None, [ctypes.c_bool], win, b'setHidesOnDeactivate:', False)
    except Exception:
        pass


def _macos_fix_hides_on_deactivate():
    """Apply setHidesOnDeactivate:False to all windows so meme/note windows
    stay visible when another app gains focus. Does NOT set setIgnoresMouseEvents."""
    try:
        send, windows, count = _macos_objc_send()
        for i in range(count):
            win = send(ctypes.c_void_p, [ctypes.c_ulong], windows, b'objectAtIndex:', i)
            send(None, [ctypes.c_bool], win, b'setHidesOnDeactivate:', False)
    except Exception:
        pass


def _is_esc_held() -> bool:
    if sys.platform == "win32":
        return bool(ctypes.windll.user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000)
    return False


class Overlay(QWidget):
    def __init__(self, on_tick=None):
        super().__init__()
        self._on_tick = on_tick
        self._quit_alpha = 0.0
        self._get_dirty_rect = None
        self._last_dirty_rect = None
        self._setup_window()
        self._apply_click_through()
        self._start_loop()

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self.show()

    def _apply_click_through(self):
        if sys.platform == "win32":
            hwnd = int(self.winId())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT
            )
        elif sys.platform == "darwin":
            _macos_setup_overlay()

    def _start_loop(self):
        self._timer = QTimer()
        self._timer.setInterval(16)  # ~60Hz wakeups; physics steps twice per wake (120Hz sim)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self):
        # Two fixed physics steps per wake keeps the 120Hz simulation rate
        if self._on_tick:
            self._on_tick()
            self._on_tick()
        self._update_quit()
        self._update_quit()

        if self._get_dirty_rect is None:
            self.update()
            return

        # goose returns None when the frame is pixel-identical to the last paint.
        rect = self._get_dirty_rect()
        quit_animating = self._quit_alpha > 0.01

        if rect is None:
            if not quit_animating:
                # Nothing changed and the quit bar is idle — skip the repaint.
                return
            # Only the quit bar is animating; repaint just its region.
            self.update(self._quit_bar_rect())
            return

        union = rect.united(self._last_dirty_rect) if self._last_dirty_rect else self.rect()
        self._last_dirty_rect = rect
        if quit_animating:
            union = union.united(self._quit_bar_rect())
        self.update(union)

    def _update_quit(self):
        if _is_esc_held():
            self._quit_alpha += QUIT_ALPHA_INCREMENT
        else:
            self._quit_alpha -= QUIT_ALPHA_DECREMENT
        self._quit_alpha = clamp(self._quit_alpha, 0.0, 1.0)

        if self._quit_alpha >= QUIT_THRESHOLD:
            QApplication.quit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint(painter)
        if self._quit_alpha > QUIT_SHOW_THRESHOLD:
            self._draw_quit_bar(painter)
        painter.end()

    def _draw_quit_bar(self, painter: QPainter):
        frac = (self._quit_alpha - QUIT_SHOW_THRESHOLD) / (1.0 - QUIT_SHOW_THRESHOLD)
        slide = clamp(frac * 2.0, 0.0, 1.0)
        y = int(lerp(-20, 10, exponential_ease_out(slide)))

        text = "Continue holding ESC to evict goose"
        font = QFont("Arial", 12, QFont.Weight.Bold)
        metrics = QFontMetrics(font)
        text_rect = metrics.boundingRect(text)
        w = text_rect.width() + 20
        h = text_rect.height() + 10

        painter.fillRect(5, y, w, h, QColor("LightBlue"))
        painter.fillRect(5, y, int(lerp(0, w, self._quit_alpha)), h, QColor("LightPink"))

        alpha_byte = int(256 * self._quit_alpha)
        painter.setPen(QColor(alpha_byte, alpha_byte, alpha_byte))
        painter.setFont(font)
        painter.drawText(15, y + text_rect.height(), text)

    def _quit_bar_rect(self):
        from PyQt6.QtCore import QRect
        return QRect(0, 0, 420, 60)

    def _paint(self, painter: QPainter):
        pass

    def set_render_fn(self, fn):
        self._paint = fn

    def set_dirty_rect_fn(self, fn):
        self._get_dirty_rect = fn
