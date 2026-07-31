import os
import random
from PyQt6.QtWidgets import QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QPainter, QPixmap, QMovie, QColor, QFont

from pygoose.goose.windows.movable_window import MovableWindow
from pygoose.engine.deck import Deck
from pygoose.paths import user_data_path

SUPPORTED_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")

PLACEHOLDER_MESSAGES = [
    "honk. where are the memes. honk.\n\nassets/images/memes/",
    "empty. just like your productivity.\n\nassets/images/memes/",
    "i dragged this window all the way here\nand you put NOTHING in it?\n\nassets/images/memes/",
    "drop images in here you coward\n\nassets/images/memes/",
    "no memes detected. disappointing.\n\nassets/images/memes/",
    "i went offscreen for THIS?\n\nassets/images/memes/",
    "assets/images/memes/ is empty.\nfix it.\n\nassets/images/memes/",
    "the audacity. no memes.\n\nassets/images/memes/",
    "i stole a blank window.\nyou did this to me.\n\nassets/images/memes/",
    "folder empty.\n\nassets/images/memes/",
    "this is embarrassing for both of us.\nadd memes.\n\nassets/images/memes/",
    "nothing?? NOTHING??\n\nassets/images/memes/",
]


def _make_placeholder(text: str) -> QPixmap:
    pix = QPixmap(400, 400)
    pix.fill(QColor(230, 230, 230))
    painter = QPainter(pix)
    painter.setPen(QColor(60, 60, 60))
    painter.setFont(QFont("Arial", 16, QFont.Weight.Bold))
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, text)
    painter.end()
    return pix

WINDOW_TITLES = [
    "honk",
    "your problem now",
    "i made this for you :)",
    "definitely not stolen",
    "free real estate",
    "this is mine now",
    "for your viewing displeasure",
    "behold.",
    "you're welcome",
    "nicked it",
    "hjonk hjonk",
    "a gift (you didn't ask for)",
    "property of the goose",
    "no take backs",
    "surprise!",
    "i found this",
    "not an apology",
    "look what i did",
    "you've been visited",
    "consider this a warning",
    "brought to you by chaos",
    "mine now, actually",
    "you needed this",
    "goose delivery service",
    "esquire, goose at law",
    "this was inevitable",
    "i have no regrets",
    "deal with it",
    "you're welcome, again",
    "i did this on purpose",
    "courtesy of the goose",
    "please enjoy your inconvenience",
    "a surprise, to be sure",
    "stop. read. suffer.",
    "found it on the ground",
    "not my fault",
    "unsolicited content",
    "the goose has spoken",
    "just goose things",
    "terms and conditions apply",
    "this message was beak-delivered",
    "honk. that's it. that's the message.",
]


_placeholder_deck: Deck | None = None
_meme_deck: Deck | None = None


def _get_placeholder_deck() -> Deck:
    global _placeholder_deck
    if _placeholder_deck is None:
        _placeholder_deck = Deck(len(PLACEHOLDER_MESSAGES))
    return _placeholder_deck


def _get_meme_deck(n: int) -> Deck:
    global _meme_deck
    if _meme_deck is None or len(_meme_deck.indices) != n:
        _meme_deck = Deck(n)
    return _meme_deck


def _local_images() -> list[str]:
    d = user_data_path("assets", "images", "memes")
    if not os.path.isdir(d):
        return []
    return [
        os.path.join(d, f)
        for f in os.listdir(d)
        if os.path.splitext(f)[1].lower() in SUPPORTED_EXTS
    ]



class MemeWindow(MovableWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(random.choice(WINDOW_TITLES))
        self.setFixedSize(400, 400)

        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._movie: QMovie | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        images = _local_images()
        if images:
            self._load_local(images[_get_meme_deck(len(images)).next()])
        else:
            msg = PLACEHOLDER_MESSAGES[_get_placeholder_deck().next()]
            self._label.setPixmap(_make_placeholder(msg))

    def _load_local(self, path: str):
        if path.lower().endswith(".gif"):
            movie = QMovie(path)
            self._movie = movie
            self._label.setMovie(movie)
            movie.setScaledSize(self._label.size())
            movie.start()
        else:
            pix = QPixmap(path)
            self._label.setPixmap(
                pix.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
            )

    @pyqtSlot()
    def show_dialog(self):
        self.show()
