import os
import sys
from PyQt6.QtWidgets import QTextEdit, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont, QIcon, QPainter, QColor, QPen, QFontDatabase

_DEFAULT_FONT_SIZE = 32 if sys.platform == "darwin" else 25

from pygoose.goose.windows.movable_window import MovableWindow
from pygoose.engine.deck import Deck
from pygoose.paths import resource_path, user_data_path

_fonts_loaded = False
_app_font_families: list[str] = []
_notepad_deck: "Deck | None" = None

def _load_fonts():
    global _fonts_loaded, _app_font_families
    if _fonts_loaded:
        return
    fonts_dir = resource_path("assets", "fonts")
    if os.path.isdir(fonts_dir):
        for fname in os.listdir(fonts_dir):
            if fname.lower().endswith((".ttf", ".otf")):
                font_id = QFontDatabase.addApplicationFont(os.path.join(fonts_dir, fname))
                if font_id >= 0:
                    _app_font_families.extend(QFontDatabase.applicationFontFamilies(font_id))
    _fonts_loaded = True

PAD_YELLOW = QColor(0xFF, 0xF0, 0x80)
LINE_BLUE  = QColor(0xA0, 0xC4, 0xFF, 180)
MARGIN_RED = QColor(0xFF, 0x8A, 0x80, 220)
LINE_SPACING = 22
MARGIN_X = 32
TOP_OFFSET = 30  # height of title bar area before lines start


def _load_phrases() -> list[str]:
    phrases = []
    assets_dir = user_data_path("assets", "text", "notepad_messages")
    if os.path.isdir(assets_dir):
        for fname in os.listdir(assets_dir):
            if fname.endswith(".txt"):
                try:
                    with open(os.path.join(assets_dir, fname), "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            phrases.append(content)
                except Exception:
                    pass
    return phrases or ["honk"]


def _handwriting_font(size: int) -> QFont:
    _load_fonts()
    if _app_font_families:
        return QFont(_app_font_families[0], size)
    import sys
    families = QFontDatabase.families()
    if sys.platform == "darwin":
        for name in ("Chalkboard SE", "Marker Felt", "Noteworthy", "Bradley Hand", "Comic Sans MS"):
            if name in families:
                return QFont(name, size)
    else:
        for name in ("Segoe Print", "Comic Sans MS"):
            if name in families:
                return QFont(name, size)
    return QFont("", size)


class NotepadWindow(MovableWindow):
    def __init__(self, font_size: int = _DEFAULT_FONT_SIZE):
        super().__init__()
        self.setWindowTitle('Goose "Not-epad"')
        self.setFixedSize(260, 200)
        self.setWindowFlag(Qt.WindowType.MSWindowsFixedSizeDialogHint, True)

        phrases = _load_phrases()
        global _notepad_deck
        if _notepad_deck is None or len(_notepad_deck.indices) != len(phrases):
            _notepad_deck = Deck(len(phrases))
        text = phrases[_notepad_deck.next()]

        self._edit = QTextEdit(self)
        self._edit.setFont(_handwriting_font(font_size))
        self._edit.setPlainText(text)
        self._edit.setReadOnly(False)
        self._edit.setFrameStyle(0)
        self._edit.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._edit.setStyleSheet("""
            QTextEdit {
                background: transparent;
                border: none;
                padding-left: 38px;
                padding-top: 4px;
                color: #1a1a2e;
            }
            QScrollBar { width: 0px; height: 0px; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._edit)

        try:
            import sys
            if sys.platform == "win32":
                notepad_path = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "notepad.exe")
                if os.path.exists(notepad_path):
                    self.setWindowIcon(QIcon(notepad_path))
        except Exception:
            pass

    def paintEvent(self, event):
        painter = QPainter(self)

        # Yellow background
        painter.fillRect(self.rect(), PAD_YELLOW)

        # Blue ruled lines
        painter.setPen(QPen(LINE_BLUE, 1))
        y = LINE_SPACING + 8
        while y < self.height():
            painter.drawLine(0, y, self.width(), y)
            y += LINE_SPACING

        # Red margin line
        painter.setPen(QPen(MARGIN_RED, 1))
        painter.drawLine(MARGIN_X, 0, MARGIN_X, self.height())

        painter.end()

    @pyqtSlot()
    def show_dialog(self):
        self.show()
