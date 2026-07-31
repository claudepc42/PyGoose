from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pygoose.goose.goose import Goose

from pygoose.engine.math_utils import random_range
from pygoose.engine.vector2 import Vector2
from pygoose.engine.math_utils import clamp

TRACK_MUD_DURATION = 15.0
DIR_CHANGE_INTERVAL = 100.0
AMOK_DURATION = 2.0


class TrackMudStage(Enum):
    DECIDE_TO_RUN    = "decide_to_run"
    RUNNING_OFFSCREEN = "running_offscreen"
    RUNNING_WANDERING = "running_wandering"


@dataclass
class TrackMudState:
    stage: TrackMudStage = TrackMudStage.DECIDE_TO_RUN
    next_dir_change_time: float = 0.0
    time_to_stop_running: float = 0.0


def enter(goose: Goose) -> None:
    goose.task_state = TrackMudState()


def tick(goose: Goose) -> None:
    from pygoose.goose.goose import Task, SpeedTier
    t = goose.time_keeper.time
    m: TrackMudState = goose.task_state

    if m.stage == TrackMudStage.DECIDE_TO_RUN:
        goose._set_target_offscreen()
        goose._set_speed(SpeedTier.RUN)
        m.stage = TrackMudStage.RUNNING_OFFSCREEN

    elif m.stage == TrackMudStage.RUNNING_OFFSCREEN:
        if Vector2.distance(goose.position, goose.target_pos) < 5.0:
            goose.target_pos = Vector2(random_range(0, goose.screen_w), random_range(0, goose.screen_h))
            m.next_dir_change_time = t + DIR_CHANGE_INTERVAL
            m.time_to_stop_running = t + AMOK_DURATION
            goose.track_mud_end_time = t + TRACK_MUD_DURATION
            m.stage = TrackMudStage.RUNNING_WANDERING
            goose.sound.play_mud_squish()

    elif m.stage == TrackMudStage.RUNNING_WANDERING:
        if (Vector2.distance(goose.position, goose.target_pos) < 5.0
                or t > m.next_dir_change_time):
            goose.target_pos = Vector2(random_range(0, goose.screen_w), random_range(0, goose.screen_h))
            m.next_dir_change_time = t + DIR_CHANGE_INTERVAL

        if t > m.time_to_stop_running:
            goose.target_pos = Vector2(
                clamp(goose.position.x + 30.0, 55.0, goose.screen_w - 55.0),
                clamp(goose.position.y + 3.0, 80.0, goose.screen_h - 80.0),
            )
            goose._set_task(Task.WANDER, honk=False)
