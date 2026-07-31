from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pygoose.goose.goose import Goose

from pygoose.engine.math_utils import random_range
from pygoose.engine.vector2 import Vector2

FOLLOW_PREFERRED_DIST_MIN  = 90.0
FOLLOW_PREFERRED_DIST_MAX  = 160.0
FOLLOW_FLEE_DIST           = 45.0
FOLLOW_FLEE_DURATION       = 1.5
FOLLOW_BOREDOM_MIN         = 15.0
FOLLOW_BOREDOM_MAX         = 30.0
FOLLOW_SNAP_GRAB_CHANCE    = 0.05
HONK_MARCH_CHANCE          = 0.12
HONK_MARCH_CHECK_INTERVAL  = 10.0
HONK_MARCH_DURATION        = 2.5
HONK_MARCH_RATE            = 0.38


class FollowMouseStage(Enum):
    RUSHING   = "rushing"
    FOLLOWING = "following"
    FLEEING   = "fleeing"


@dataclass
class FollowMouseState:
    start_time: float
    boredom_time: float
    preferred_dist: float
    stage: FollowMouseStage = FollowMouseStage.RUSHING
    flee_target: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    flee_until: float = -1.0
    honk_march_until: float = -1.0
    next_march_honk_time: float = -1.0
    next_march_check_time: float = 0.0


def enter(goose: Goose) -> None:
    from pygoose.goose.goose import SpeedTier
    goose._set_speed(SpeedTier.RUN)
    t = goose.time_keeper.time
    goose.task_state = FollowMouseState(
        start_time=t,
        boredom_time=t + random_range(FOLLOW_BOREDOM_MIN, FOLLOW_BOREDOM_MAX),
        preferred_dist=random_range(FOLLOW_PREFERRED_DIST_MIN, FOLLOW_PREFERRED_DIST_MAX),
        next_march_check_time=t + random_range(3.0, 6.0),
    )


def tick(goose: Goose) -> None:
    import random as _random
    from pygoose.goose.goose import Task, SpeedTier
    t = goose.time_keeper.time
    f: FollowMouseState = goose.task_state
    cursor_pos = goose._get_cursor_pos()
    to_cursor = cursor_pos - goose.position
    dist = Vector2.magnitude(to_cursor)

    if t >= f.boredom_time:
        if _random.random() < FOLLOW_SNAP_GRAB_CHANCE:
            goose._set_task(Task.NAB_MOUSE)
        else:
            goose._set_task(Task.WANDER)
        return

    FOLLOW_DEADBAND = 35.0

    if f.stage == FollowMouseStage.RUSHING:
        goose._set_speed(SpeedTier.RUN)
        if dist > 1.0:
            goose.target_pos = cursor_pos - Vector2.normalize(to_cursor) * f.preferred_dist
        if dist <= f.preferred_dist + FOLLOW_DEADBAND:
            f.stage = FollowMouseStage.FOLLOWING

    elif f.stage == FollowMouseStage.FOLLOWING:
        if dist < FOLLOW_FLEE_DIST:
            flee_dir = Vector2.normalize(goose.position - cursor_pos) if dist > 1.0 else Vector2(1.0, 0.0)
            f.flee_target = goose.position + flee_dir * 180.0
            f.flee_until = t + FOLLOW_FLEE_DURATION
            f.stage = FollowMouseStage.FLEEING
        elif dist > f.preferred_dist + FOLLOW_DEADBAND:
            goose._set_speed(SpeedTier.WALK)
            goose._freeze_position = False
            if dist > 1.0:
                goose.target_pos = cursor_pos - Vector2.normalize(to_cursor) * f.preferred_dist
        else:
            goose._freeze_position = True
            if dist > 1.0:
                goose.target_pos = goose.position + Vector2.normalize(to_cursor) * 50.0

        march_active = f.honk_march_until > 0 and t < f.honk_march_until
        if t >= f.next_march_check_time and not march_active:
            f.next_march_check_time = t + HONK_MARCH_CHECK_INTERVAL + random_range(-1.0, 2.0)
            if _random.random() < HONK_MARCH_CHANCE:
                f.honk_march_until = t + HONK_MARCH_DURATION
                f.next_march_honk_time = t

        if f.honk_march_until > 0 and t < f.honk_march_until:
            if t >= f.next_march_honk_time:
                goose.sound.honk()
                f.next_march_honk_time = t + HONK_MARCH_RATE

    elif f.stage == FollowMouseStage.FLEEING:
        goose._freeze_position = False
        goose._set_speed(SpeedTier.RUN)
        goose.target_pos = f.flee_target
        if t >= f.flee_until:
            f.stage = FollowMouseStage.FOLLOWING
