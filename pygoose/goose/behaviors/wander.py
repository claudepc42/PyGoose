from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pygoose.goose.goose import Goose

from pygoose.engine.math_utils import random_range
from pygoose.engine.vector2 import Vector2

WANDER_GOOD_ENOUGH_DIST = 20.0


@dataclass
class WanderState:
    wander_start_time: float
    wander_duration: float
    pause_start_time: float = -1.0
    pause_duration: float = 0.0


def enter(goose: Goose) -> None:
    from pygoose.goose.goose import SpeedTier
    goose._set_speed(SpeedTier.WALK)
    duration = goose._get_random_wander_duration()
    goose.task_state = WanderState(
        wander_start_time=goose.time_keeper.time,
        wander_duration=duration,
    )


def tick(goose: Goose) -> None:
    t = goose.time_keeper.time
    w: WanderState = goose.task_state

    if t - w.wander_start_time > w.wander_duration:
        goose._choose_next_task()
        return

    if w.pause_start_time > 0.0:
        if t - w.pause_start_time > w.pause_duration:
            w.pause_start_time = -1.0
            walk_time = random_range(1.0, 6.0)
            max_walk_dist = walk_time * goose.current_speed
            new_target = Vector2(
                random_range(0, goose.screen_w),
                random_range(0, goose.screen_h),
            )
            if Vector2.distance(goose.position, new_target) > max_walk_dist:
                new_target = goose.position + Vector2.normalize(new_target - goose.position) * max_walk_dist
            goose.target_pos = new_target
        else:
            goose.velocity = Vector2(0.0, 0.0)
    else:
        if Vector2.distance(goose.position, goose.target_pos) < WANDER_GOOD_ENOUGH_DIST:
            w.pause_start_time = t
            w.pause_duration = random_range(1.0, 2.0)
