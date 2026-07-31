from __future__ import annotations
import math as _math
import random as _random
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pygoose.goose.goose import Goose

from pygoose.engine.math_utils import lerp, clamp, random_range
from pygoose.engine.vector2 import Vector2
from pygoose.engine.time_keeper import DELTA_TIME

SLEEP_CIRCLE_RADIUS   = 88.0
SLEEP_CIRCLE_SPEED    = 0.75
SLEEP_CIRCLES_MIN     = 2.0
SLEEP_CIRCLES_MAX     = 3.0
SLEEP_SETTLE_DURATION = 2.2
SLEEP_MIN_DURATION    = 90.0
SLEEP_MAX_DURATION    = 480.0
SLEEP_CORNER_MARGIN   = 165.0


class SleepStage(Enum):
    WALKING_TO_CORNER = "walking_to_corner"
    CIRCLING          = "circling"
    SETTLING          = "settling"
    SLEEPING          = "sleeping"


@dataclass
class SleepState:
    nest_pos: Vector2
    spiral_start_angle: float = 0.0
    stage: SleepStage = SleepStage.WALKING_TO_CORNER
    spiral_t: float = 0.0
    settle_start_time: float = -1.0
    wake_time: float = -1.0
    is_fake_sleep: bool = False
    next_eye_event_time: float = -1.0
    eye_is_open: bool = False
    spotted_time: float = -1.0


def enter(goose: Goose) -> None:
    from pygoose.goose.goose import SpeedTier
    goose._set_speed(SpeedTier.WALK)
    corners = [
        Vector2(SLEEP_CORNER_MARGIN, SLEEP_CORNER_MARGIN),
        Vector2(goose.screen_w - SLEEP_CORNER_MARGIN, SLEEP_CORNER_MARGIN),
        Vector2(goose.screen_w - SLEEP_CORNER_MARGIN, goose.screen_h - SLEEP_CORNER_MARGIN),
    ]
    nest = corners[0] if goose.config.dev_force_task else _random.choice(corners)
    nest += Vector2(random_range(-15, 15), random_range(-15, 15))
    goose.task_state = SleepState(
        nest_pos=nest,
        spiral_start_angle=_random.uniform(0, 2 * _math.pi),
    )
    goose.target_pos = nest


def tick(goose: Goose) -> None:
    from pygoose.goose.goose import Task, SpeedTier
    t = goose.time_keeper.time
    s: SleepState = goose.task_state

    if s.stage == SleepStage.WALKING_TO_CORNER:
        goose._set_speed(SpeedTier.WALK)
        goose.target_pos = s.nest_pos
        if Vector2.distance(goose.position, s.nest_pos) < 8.0:
            s.stage = SleepStage.CIRCLING

    elif s.stage == SleepStage.CIRCLING:
        goose._set_speed(SpeedTier.SNEAK)
        # Advance at constant 40px/s arc speed so target always stays ahead of goose
        arc_len = max(SLEEP_CIRCLE_RADIUS * (1.0 - s.spiral_t) * 1.5 * 2 * _math.pi, 1.0)
        s.spiral_t = min(s.spiral_t + (40.0 / arc_len) * DELTA_TIME, 1.0)
        angle = s.spiral_start_angle + s.spiral_t * 1.5 * 2 * _math.pi
        radius = SLEEP_CIRCLE_RADIUS * (1.0 - s.spiral_t)
        goose.target_pos = Vector2(
            s.nest_pos.x + _math.cos(angle) * radius,
            s.nest_pos.y + _math.sin(angle) * radius,
        )
        if s.spiral_t >= 0.6:
            s.settle_start_time = t
            s.stage = SleepStage.SETTLING

    elif s.stage == SleepStage.SETTLING:
        goose._freeze_position = True
        elapsed = t - s.settle_start_time
        progress = clamp(elapsed / SLEEP_SETTLE_DURATION, 0.0, 1.0)
        goose._target_sit_lerp = progress
        goose._target_neck_tuck = progress

        if elapsed >= SLEEP_SETTLE_DURATION:
            s.wake_time = t + random_range(SLEEP_MIN_DURATION, SLEEP_MAX_DURATION)
            s.is_fake_sleep = goose.config.dev_force_fake_sleep or _random.random() < 0.15
            if s.is_fake_sleep:
                s.next_eye_event_time = t + random_range(5.0, 15.0)
            s.stage = SleepStage.SLEEPING

    elif s.stage == SleepStage.SLEEPING:
        goose._freeze_position = True
        goose._target_sit_lerp = 1.0
        goose._target_neck_tuck = 1.0

        if s.is_fake_sleep:
            if not s.eye_is_open and t >= s.next_eye_event_time:
                goose.rig.peek_eye = _random.choice([1, 2])
                s.eye_is_open = True
                s.next_eye_event_time = t + random_range(0.5, 2.5)
            elif s.eye_is_open and t >= s.next_eye_event_time:
                goose.rig.peek_eye = 0
                s.eye_is_open = False
                s.next_eye_event_time = t + random_range(5.0, 15.0)

            if s.eye_is_open and s.spotted_time < 0 and Vector2.distance(goose.position, goose._get_cursor_pos()) < 150.0:
                s.spotted_time = t
            if s.spotted_time > 0:
                goose._freeze_position = True
                elapsed = t - s.spotted_time
                if elapsed < 0.75:
                    goose.rig.show_exclamation = False
                elif elapsed < 1.5:
                    goose.rig.peek_eye = 3
                    goose.rig.show_exclamation = True
                else:
                    mouse = goose._get_cursor_pos()
                    away = Vector2.normalize(goose.position - mouse)
                    perp = Vector2(-away.y, away.x)
                    off_base = goose.position + away * 400.0
                    goose._freak_bounce_a = off_base + perp * 70.0
                    goose._freak_bounce_b = off_base - perp * 70.0
                    goose._freak_bounce_to_a = True
                    goose._freak_out_until = t + 4.0
                    goose._freak_out_next_honk = t
                    goose._set_task(Task.WANDER, honk=False)
                    return

        if t >= s.wake_time:
            goose._set_task(Task.WANDER)
