from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pygoose.goose.goose import Goose

from pygoose.engine.math_utils import random_range
from pygoose.engine.vector2 import Vector2

WATCH_MOUSE_DURATION_MIN = 8.0
WATCH_MOUSE_DURATION_MAX = 180.0
BOB_INTERVAL_MIN = 1.2
BOB_INTERVAL_MAX = 3.5
BOB_DURATION = 0.35
WATCH_HONK_INTERVAL_MIN = 5.0
WATCH_HONK_INTERVAL_MAX = 12.0
WATCH_SUB_DURATION_MIN = 2.0
WATCH_SUB_DURATION_MAX = 5.0

SIT_MIN_DURATION = 15.0


class WatchSubState(Enum):
    STAND_STILL = "stand_still"
    WALK_SLOW   = "walk_slow"
    SIT         = "sit"
    CRAWL       = "crawl"  # sit pose while moving — reserved for future use


@dataclass
class WatchMouseState:
    start_time: float
    duration: float
    next_bob_time: float
    next_honk_time: float
    bob_end_time: float = -1.0
    sub_state: WatchSubState = WatchSubState.WALK_SLOW
    next_sub_change_time: float = 0.0
    sit_entered_time: float = -1.0


def enter(goose: Goose) -> None:
    from pygoose.goose.goose import SpeedTier
    goose._set_speed(SpeedTier.WALK)
    t = goose.time_keeper.time
    goose.task_state = WatchMouseState(
        start_time=t,
        duration=random_range(WATCH_MOUSE_DURATION_MIN, WATCH_MOUSE_DURATION_MAX),
        next_bob_time=t + random_range(0.5, 1.5),
        next_honk_time=t + random_range(2.0, 4.0),
    )


def tick(goose: Goose) -> None:
    import random as _random
    from pygoose.goose.goose import Task, SpeedTier
    t = goose.time_keeper.time
    w: WatchMouseState = goose.task_state

    if t - w.start_time > w.duration:
        goose._set_task(Task.WANDER)
        return

    cursor_pos = goose._get_cursor_pos()
    to_cursor = cursor_pos - goose.position
    if Vector2.magnitude(to_cursor) > 1.0:
        goose.target_pos = goose.position + Vector2.normalize(to_cursor) * 50.0

    sit_held_long_enough = (w.sub_state != WatchSubState.SIT or
                            w.sit_entered_time < 0 or
                            t - w.sit_entered_time >= SIT_MIN_DURATION)
    if t > w.next_sub_change_time and sit_held_long_enough:
        new_sub = _random.choice([WatchSubState.STAND_STILL, WatchSubState.WALK_SLOW, WatchSubState.SIT])
        if new_sub == WatchSubState.SIT and w.sub_state != WatchSubState.SIT:
            w.sit_entered_time = t
        elif new_sub != WatchSubState.SIT:
            w.sit_entered_time = -1.0
        w.sub_state = new_sub
        w.next_sub_change_time = t + random_range(WATCH_SUB_DURATION_MIN, WATCH_SUB_DURATION_MAX)

    if w.sub_state == WatchSubState.STAND_STILL:
        goose._freeze_position = True
        goose._target_sit_lerp = 0.0
    elif w.sub_state == WatchSubState.WALK_SLOW:
        goose._freeze_position = False
        goose._target_sit_lerp = 0.0
        dist = Vector2.magnitude(to_cursor)
        if dist > 60.0:
            goose._set_speed(SpeedTier.WALK)
            goose.target_pos = goose.position + Vector2.normalize(to_cursor) * 50.0
        else:
            goose._freeze_position = True
    elif w.sub_state == WatchSubState.SIT:
        goose._freeze_position = True
        goose._target_sit_lerp = 1.0
    elif w.sub_state == WatchSubState.CRAWL:
        goose._target_sit_lerp = 1.0
        goose._target_neck_tuck = 1.0

    if w.sub_state != WatchSubState.SIT:
        if w.bob_end_time > 0.0:
            goose.override_extend_neck = True
            if t > w.bob_end_time:
                w.bob_end_time = -1.0
                goose.override_extend_neck = False
                w.next_bob_time = t + random_range(BOB_INTERVAL_MIN, BOB_INTERVAL_MAX)
        elif t > w.next_bob_time:
            w.bob_end_time = t + BOB_DURATION
    else:
        goose.override_extend_neck = False

    if t > w.next_honk_time:
        if _random.random() < 0.30:
            goose.sound.honk()
        w.next_honk_time = t + random_range(WATCH_HONK_INTERVAL_MIN, WATCH_HONK_INTERVAL_MAX)
