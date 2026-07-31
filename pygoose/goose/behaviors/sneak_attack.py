from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pygoose.goose.goose import Goose

from pygoose.engine.math_utils import random_range
from pygoose.engine.vector2 import Vector2
from pygoose.engine.time_keeper import DELTA_TIME
from pygoose.goose.cursor import set_cursor_clip, release_cursor_clip
from pygoose.goose.behaviors.nab_mouse import (
    MOUSE_GRAB_DISTANCE, MOUSE_SUCC_TIME, MOUSE_DROP_DISTANCE, STRUGGLE_RANGE,
)

SNEAK_STRIKE_DIST  = 65.0
SNEAK_MAX_DURATION = 44.0
SNEAK_HONK_RATE    = 0.32


class SneakAttackStage(Enum):
    SNEAKING     = "sneaking"
    POUNCING     = "pouncing"
    DRAGGING     = "dragging"
    DECELERATING = "decelerating"


@dataclass
class SneakAttackState:
    start_time: float
    give_up_time: float
    stage: SneakAttackStage = SneakAttackStage.SNEAKING
    grabbed_time: float = -1.0
    original_vector_to_mouse: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    drag_to: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    next_honk_time: float = -1.0


def enter(goose: Goose) -> None:
    from pygoose.goose.goose import SpeedTier
    goose._set_speed(SpeedTier.SNEAK)
    t = goose.time_keeper.time
    goose.task_state = SneakAttackState(
        start_time=t,
        give_up_time=t + SNEAK_MAX_DURATION,
    )


def tick(goose: Goose) -> None:
    from pygoose.goose.goose import Task, SpeedTier
    t = goose.time_keeper.time
    s: SneakAttackState = goose.task_state
    cursor_pos = goose._get_cursor_pos()
    to_cursor = cursor_pos - goose.position
    dist = Vector2.magnitude(to_cursor)

    if s.stage == SneakAttackStage.SNEAKING:
        if t >= s.give_up_time:
            goose._set_task(Task.WANDER)
            return

        goose._set_speed(SpeedTier.SNEAK)
        goose._target_sit_lerp = 1.0
        goose._target_neck_tuck = 1.0
        if dist > 1.0:
            goose.target_pos = cursor_pos

        if dist < SNEAK_STRIKE_DIST:
            goose._target_sit_lerp = 0.0
            goose._target_neck_tuck = 0.0
            goose._set_speed(SpeedTier.CHARGE)
            s.stage = SneakAttackStage.POUNCING
            s.next_honk_time = t

    elif s.stage == SneakAttackStage.POUNCING:
        goose._set_speed(SpeedTier.CHARGE)
        beak_tip = goose.rig.head2_end_point
        goose.target_pos = cursor_pos - (beak_tip - goose.position)

        if t >= s.next_honk_time:
            goose.sound.honk()
            s.next_honk_time = t + SNEAK_HONK_RATE

        if Vector2.distance(beak_tip, cursor_pos) < MOUSE_GRAB_DISTANCE:
            s.original_vector_to_mouse = cursor_pos - beak_tip
            s.grabbed_time = t
            drag_to = Vector2(goose.position.x, goose.position.y)
            while Vector2.distance(drag_to, goose.position) / 400.0 < 1.2:
                drag_to = Vector2(random_range(0, goose.screen_w), random_range(0, goose.screen_h))
            s.drag_to = drag_to
            goose.target_pos = drag_to
            goose.sound.chomp()
            s.stage = SneakAttackStage.DRAGGING

        if t >= s.give_up_time + SNEAK_MAX_DURATION:
            goose._set_task(Task.WANDER)

    elif s.stage == SneakAttackStage.DRAGGING:
        beak_tip = goose.rig.head2_end_point
        if Vector2.distance(goose.position, s.drag_to) < MOUSE_DROP_DISTANCE:
            release_cursor_clip()
            s.stage = SneakAttackStage.DECELERATING
        else:
            p = min((t - s.grabbed_time) / MOUSE_SUCC_TIME, 1.0)
            clip_vec = Vector2.lerp(s.original_vector_to_mouse, STRUGGLE_RANGE, p)
            clip_x = beak_tip.x + clip_vec.x
            clip_y = beak_tip.y + clip_vec.y
            set_cursor_clip(clip_x, clip_y, abs(clip_vec.x), abs(clip_vec.y))

        if t >= s.next_honk_time:
            goose.sound.honk()
            s.next_honk_time = t + SNEAK_HONK_RATE

    elif s.stage == SneakAttackStage.DECELERATING:
        mag = Vector2.magnitude(goose.velocity)
        if mag > 0.01:
            goose.target_pos = goose.position + Vector2.normalize(goose.velocity) * 5.0
            goose.velocity -= Vector2.normalize(goose.velocity) * goose.current_acceleration * 2.0 * DELTA_TIME
        if mag < 80.0:
            release_cursor_clip()
            goose._set_task(Task.WANDER)
