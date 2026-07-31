from __future__ import annotations
import random as _random
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pygoose.goose.goose import Goose

from pygoose.engine.math_utils import lerp, clamp, random_range
from pygoose.engine.vector2 import Vector2

WAIT_TIME_MIN = 2.0
WAIT_TIME_MAX = 3.5


class CollectWindowStage(Enum):
    WALKING_TO_EVICT             = "walking_to_evict"
    EVICTING_WINDOW              = "evicting_window"
    WALKING_OFFSCREEN            = "walking_offscreen"
    WAITING_TO_BRING_WINDOW_BACK = "waiting_to_bring_window_back"
    DRAGGING_WINDOW_BACK         = "dragging_window_back"


@dataclass
class CollectWindowState:
    stage: CollectWindowStage = CollectWindowStage.WALKING_OFFSCREEN
    screen_direction: object = None
    main_window: object = None
    window_offset_to_beak: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    wait_start_time: float = 0.0
    secs_to_wait: float = 0.0
    window_closed_early: bool = False
    window_type: str = ""
    evict_window: object = None
    evict_window_offset: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))


def _set_window_offset_for_direction(state: CollectWindowState, direction) -> None:
    from pygoose.goose.goose import ScreenDirection
    w = state.main_window.width() if state.main_window else 200
    h = state.main_window.height() if state.main_window else 150
    if direction == ScreenDirection.LEFT:
        state.window_offset_to_beak = Vector2(float(w), float(h) / 2)
    elif direction == ScreenDirection.TOP:
        state.window_offset_to_beak = Vector2(float(w) / 2, float(h))
    elif direction == ScreenDirection.RIGHT:
        state.window_offset_to_beak = Vector2(0.0, float(h) / 2)


def enter(goose: Goose) -> None:
    from pygoose.goose.goose import Task, SpeedTier
    from pygoose.goose.windows.notepad_window import NotepadWindow
    from pygoose.goose.windows.meme_window import MemeWindow

    if goose.current_task == Task.COLLECT_WINDOW_NOTEPAD:
        window = NotepadWindow(font_size=goose.config.notepad_font_size)
        window_type = "notepad"
    else:
        window = MemeWindow()
        window_type = "meme"

    lst = goose._placed_memes if window_type == "meme" else goose._placed_notepads
    state = CollectWindowState(main_window=window, window_type=window_type)

    if len(lst) >= 2:
        evict_win = _random.choice(lst)
        lst.remove(evict_win)
        if goose._anger_window is evict_win:
            goose._anger_window = None
        wpos = evict_win.pos()
        w = float(evict_win.width())
        h = float(evict_win.height())
        cx = float(wpos.x()) + w / 2
        mid_y = float(wpos.y()) + h / 2
        if cx < goose.screen_w / 2:
            evict_offset = Vector2(w, h / 2)
            grab_x = float(wpos.x()) + w
        else:
            evict_offset = Vector2(0.0, h / 2)
            grab_x = float(wpos.x())
        state.evict_window = evict_win
        state.evict_window_offset = evict_offset
        state.stage = CollectWindowStage.WALKING_TO_EVICT
        goose.task_state = state
        goose.target_pos = Vector2(grab_x, mid_y)
    else:
        goose._set_speed(SpeedTier.WALK)
        goose.task_state = state
        direction = goose._set_target_offscreen()
        state.screen_direction = direction
        _set_window_offset_for_direction(state, direction)


def tick(goose: Goose) -> None:
    from PyQt6.QtCore import QMetaObject, Qt
    from pygoose.goose.goose import Task, ScreenDirection
    from pygoose.goose.windows.notepad_window import NotepadWindow
    t = goose.time_keeper.time
    c: CollectWindowState = goose.task_state

    if c.window_closed_early and c.stage not in (
        CollectWindowStage.WALKING_TO_EVICT, CollectWindowStage.EVICTING_WINDOW
    ):
        c.window_closed_early = False
        goose._set_task(Task.NAB_MOUSE)
        return

    if c.stage == CollectWindowStage.WALKING_TO_EVICT:
        if Vector2.distance(goose.position, goose.target_pos) < 15.0:
            ew = c.evict_window
            cx = float(ew.pos().x()) + ew.width() / 2
            if cx < goose.screen_w / 2:
                goose.target_pos = Vector2(-80.0, lerp(goose.position.y, goose.screen_h / 2, 0.3))
            else:
                goose.target_pos = Vector2(goose.screen_w + 80.0, lerp(goose.position.y, goose.screen_h / 2, 0.3))
            c.stage = CollectWindowStage.EVICTING_WINDOW

    elif c.stage == CollectWindowStage.EVICTING_WINDOW:
        offscreen = goose.position.x < -40 or goose.position.x > goose.screen_w + 40
        if offscreen or c.evict_window is None:
            if c.evict_window is not None:
                try:
                    c.evict_window.closing.disconnect()
                except Exception:
                    pass
                c.evict_window.hide()
                c.evict_window.deleteLater()
                c.evict_window = None
            goose.override_extend_neck = False
            direction = goose._set_target_offscreen()
            c.screen_direction = direction
            c.stage = CollectWindowStage.WALKING_OFFSCREEN
            _set_window_offset_for_direction(c, direction)
        else:
            goose.override_extend_neck = True
            window_pos = goose.rig.head2_end_point - c.evict_window_offset
            c.evict_window.move_threadsafe(int(window_pos.x), int(window_pos.y))

    elif c.stage == CollectWindowStage.WALKING_OFFSCREEN:
        if Vector2.distance(goose.position, goose.target_pos) < 5.0:
            c.secs_to_wait = random_range(WAIT_TIME_MIN, WAIT_TIME_MAX)
            c.wait_start_time = t
            c.stage = CollectWindowStage.WAITING_TO_BRING_WINDOW_BACK

    elif c.stage == CollectWindowStage.WAITING_TO_BRING_WINDOW_BACK:
        goose.velocity = Vector2(0.0, 0.0)
        if t - c.wait_start_time > c.secs_to_wait:
            c.main_window.closing.connect(goose._on_window_closed_early)
            QMetaObject.invokeMethod(c.main_window, "show_dialog", Qt.ConnectionType.QueuedConnection)

            d = c.screen_direction
            w = float(c.main_window.width())
            h = float(c.main_window.height())

            if d == ScreenDirection.LEFT:
                tx = w + random_range(15, 300)
                ty = random_range(h + 40, goose.screen_h - 60)
            elif d == ScreenDirection.RIGHT:
                tx = goose.screen_w - (w + random_range(15, 300))
                ty = random_range(h + 40, goose.screen_h - 60)
            else:
                tx = random_range(w + 60, goose.screen_w - w - 60)
                ty = h + random_range(80, 350)

            lst = goose._placed_memes if c.window_type == "meme" else goose._placed_notepads
            if lst:
                if d == ScreenDirection.LEFT:
                    tx += random_range(50, 130)
                    ty += random_range(-150, 150)
                elif d == ScreenDirection.RIGHT:
                    tx -= random_range(50, 130)
                    ty += random_range(-150, 150)
                else:
                    ty += random_range(50, 130)
                    tx += random_range(-150, 150)

            goose.target_pos = Vector2(
                clamp(tx, w + 55, goose.screen_w - w - 55),
                clamp(ty, h + 80, goose.screen_h),
            )
            c.stage = CollectWindowStage.DRAGGING_WINDOW_BACK

    elif c.stage == CollectWindowStage.DRAGGING_WINDOW_BACK:
        if Vector2.distance(goose.position, goose.target_pos) < 5.0:
            lst = goose._placed_memes if c.window_type == "meme" else goose._placed_notepads
            lst.append(c.main_window)
            c.main_window.closing.connect(goose._make_placed_window_close_cb(c.main_window, c.window_type))
            goose._anger_window = c.main_window
            goose._anger_time = t
            goose._anger_closed = False
            goose._anger_permanent = isinstance(c.main_window, NotepadWindow)
            goose._set_task(Task.WANDER)
            return

        goose.override_extend_neck = True
        window_pos = goose.rig.head2_end_point - c.window_offset_to_beak
        c.main_window.move_threadsafe(int(window_pos.x), int(window_pos.y))
