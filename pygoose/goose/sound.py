import os
import wave
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QAudioDecoder, QAudioFormat
from PyQt6.QtCore import QUrl

from pygoose.engine.math_utils import get_rng
from pygoose.paths import resource_path, user_data_path

# Looping MP3 decode costs ~2% of a CPU core for the entire session. The music
# is decoded once (in the background, first run) to a PCM WAV cache; subsequent
# sessions play the cache through the identical QMediaPlayer pipeline — same
# decoder output, same volume, same loop — with near-zero per-frame DSP cost.
MUSIC_CACHE_PARTS = ("assets", "music_cache.wav")


def _path(filename: str) -> str:
    return resource_path("assets", "sounds", filename)


def _exists(filename: str) -> bool:
    return os.path.isfile(_path(filename))


def _make_player(volume: float) -> tuple[QMediaPlayer, QAudioOutput]:
    player = QMediaPlayer()
    audio = QAudioOutput()
    audio.setVolume(volume)
    player.setAudioOutput(audio)
    return player, audio


class Sound:
    def __init__(self, silence: bool = False, silence_music: bool = False):
        self._silence = silence
        if silence:
            return

        self._honk_players: list[tuple[QMediaPlayer, QAudioOutput]] = []
        for i in range(1, 5):
            fname = f"Honk{i}.mp3"
            if _exists(fname):
                p, a = _make_player(0.8)
                p.setSource(QUrl.fromLocalFile(_path(fname)))
                self._honk_players.append((p, a))

        self._bite_player: tuple[QMediaPlayer, QAudioOutput] | None = None
        if _exists("BITE.mp3"):
            p, a = _make_player(0.07)
            p.setSource(QUrl.fromLocalFile(_path("BITE.mp3")))
            self._bite_player = (p, a)

        self._mud_player: tuple[QMediaPlayer, QAudioOutput] | None = None
        if _exists("MudSquith.mp3"):
            p, a = _make_player(0.8)
            p.setSource(QUrl.fromLocalFile(_path("MudSquith.mp3")))
            self._mud_player = (p, a)

        self._pat_players: list[tuple[QMediaPlayer, QAudioOutput]] = []
        for i in range(1, 4):
            fname = f"Pat{i}.wav"
            if _exists(fname):
                p, a = _make_player(0.8)
                p.setSource(QUrl.fromLocalFile(_path(fname)))
                self._pat_players.append((p, a))

        self._music_player: tuple[QMediaPlayer, QAudioOutput] | None = None
        self._music_decoder = None
        if _exists("Music.mp3") and not silence_music:
            p, a = _make_player(0.5)
            p.setSource(QUrl.fromLocalFile(self._music_source()))
            p.setLoops(QMediaPlayer.Loops.Infinite)
            self._music_player = (p, a)
            p.play()

    # ------------------------------------------------------------------
    # Music PCM cache
    # ------------------------------------------------------------------

    def _music_source(self) -> str:
        """Path the music player should use: the PCM cache when valid,
        otherwise the MP3 (and kick off a background cache build)."""
        cache = user_data_path(*MUSIC_CACHE_PARTS)
        if self._music_cache_valid(cache):
            return cache
        self._start_music_cache_build(cache)
        return _path("Music.mp3")

    @staticmethod
    def _music_cache_valid(cache: str) -> bool:
        try:
            with wave.open(cache, "rb") as w:
                return w.getnframes() > 0
        except Exception:
            return False

    def _start_music_cache_build(self, cache: str):
        """Decode Music.mp3 to PCM in the background and write the WAV cache
        atomically. Any failure leaves no cache; the MP3 path keeps working."""
        try:
            decoder = QAudioDecoder()
            want = QAudioFormat()
            want.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            want.setChannelCount(2)
            want.setSampleRate(44100)
            decoder.setAudioFormat(want)
            decoder.setSource(QUrl.fromLocalFile(_path("Music.mp3")))
            chunks: list[bytes] = []
            actual: dict = {}

            def on_ready():
                buf = decoder.read()
                f = buf.format()
                actual["sf"] = f.sampleFormat()
                actual["ch"] = f.channelCount()
                actual["rate"] = f.sampleRate()
                ptr = buf.constData()
                ptr.setsize(buf.byteCount())
                chunks.append(bytes(ptr))

            def on_finished():
                try:
                    # Only cache if the backend honoured Int16; the WAV header
                    # must describe the bytes exactly or playback would differ.
                    if chunks and actual.get("sf") == QAudioFormat.SampleFormat.Int16:
                        os.makedirs(os.path.dirname(cache), exist_ok=True)
                        tmp = cache + ".tmp"
                        with wave.open(tmp, "wb") as w:
                            w.setnchannels(actual["ch"])
                            w.setsampwidth(2)
                            w.setframerate(actual["rate"])
                            w.writeframes(b"".join(chunks))
                        os.replace(tmp, cache)  # atomic — never half-written
                except Exception:
                    pass
                self._music_decoder = None

            def on_error(_err):
                self._music_decoder = None

            decoder.bufferReady.connect(on_ready)
            decoder.finished.connect(on_finished)
            decoder.error.connect(on_error)
            decoder.start()
            self._music_decoder = decoder  # keep referenced while decoding
        except Exception:
            self._music_decoder = None

    # ------------------------------------------------------------------

    def honk(self):
        if self._silence or not self._honk_players:
            return
        rng = get_rng()
        p, _ = self._honk_players[int(rng.random() * len(self._honk_players))]
        p.setPosition(0)
        p.play()

    def chomp(self):
        if self._silence or not self._bite_player:
            return
        p, _ = self._bite_player
        p.setPosition(0)
        p.play()

    def play_pat(self):
        if self._silence or not self._pat_players:
            return
        rng = get_rng()
        p, _ = self._pat_players[int(rng.random() * len(self._pat_players))]
        p.setPosition(0)
        p.play()

    def play_mud_squish(self):
        if self._silence or not self._mud_player:
            return
        p, _ = self._mud_player
        p.setPosition(0)
        p.play()
