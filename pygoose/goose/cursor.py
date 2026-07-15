import sys
import ctypes

if sys.platform == "win32":
    class _RECT(ctypes.Structure):
        _fields_ = [
            ("left",   ctypes.c_long),
            ("top",    ctypes.c_long),
            ("right",  ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    def set_cursor_clip(x: float, y: float, w: float, h: float):
        from PyQt6.QtGui import QGuiApplication
        dpr = QGuiApplication.primaryScreen().devicePixelRatio()
        rect = _RECT(int(x * dpr), int(y * dpr), int((x + max(w, 1)) * dpr), int((y + max(h, 1)) * dpr))
        ctypes.windll.user32.ClipCursor(ctypes.byref(rect))

    def release_cursor_clip():
        ctypes.windll.user32.ClipCursor(None)

    def is_left_mouse_down() -> bool:
        return bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)

elif sys.platform == "darwin":
    _cg = ctypes.CDLL(
        '/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics'
    )
    _cg.CGEventSourceButtonState.restype = ctypes.c_bool
    _cg.CGEventSourceButtonState.argtypes = [ctypes.c_int32, ctypes.c_uint32]
    _kCGEventSourceStateHIDSystemState = 1
    _kCGMouseButtonLeft = 0

    def set_cursor_clip(x: float, y: float, w: float, h: float):
        from PyQt6.QtGui import QCursor
        QCursor.setPos(int(x + w / 2), int(y + h / 2))

    def release_cursor_clip():
        pass

    def is_left_mouse_down() -> bool:
        return bool(_cg.CGEventSourceButtonState(
            _kCGEventSourceStateHIDSystemState, _kCGMouseButtonLeft
        ))

else:
    # Linux — fall back to simulation
    def set_cursor_clip(x: float, y: float, w: float, h: float): pass
    def release_cursor_clip(): pass

    try:
        import subprocess

        def is_left_mouse_down() -> bool:
            try:
                out = subprocess.check_output(["xdotool", "getmouselocation"], timeout=0.01)
                return False  # xdotool can't easily check button state; poll via Qt instead
            except Exception:
                return False
    except Exception:
        def is_left_mouse_down(): return False
