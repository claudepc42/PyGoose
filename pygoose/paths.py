import sys
import os


def _frozen() -> bool:
    return getattr(sys, 'frozen', False)


def _bundle_root() -> str:
    """Root for read-only bundled assets (sounds, fonts). Inside _MEIPASS when frozen."""
    if _frozen():
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _user_root() -> str:
    """Root for user-editable content (config, memes, notes). Next to exe when frozen."""
    if _frozen():
        if sys.platform == "darwin":
            # Inside a .app bundle, sys.executable is PyGoose.app/Contents/MacOS/PyGoose.
            # Walk up until we've cleared the .app bundle to find the folder containing it.
            path = os.path.abspath(sys.executable)
            while True:
                parent = os.path.dirname(path)
                if parent == path:
                    break
                if path.endswith('.app'):
                    return parent
                path = parent
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(*parts: str) -> str:
    """Absolute path to a bundled read-only asset."""
    return os.path.join(_bundle_root(), *parts)


def user_data_path(*parts: str) -> str:
    """Absolute path to a user-editable file or folder next to the exe."""
    return os.path.join(_user_root(), *parts)
