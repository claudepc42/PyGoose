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

MOUSE_GRAB_DISTANCE = 15.0
MOUSE_SUCC_TIME = 0.06
MOUSE_DROP_DISTANCE = 30.0
GIVE_UP_TIME = 9.0
STRUGGLE_RANGE = Vector2(3.0, 3.0)


class NabMouseStage(Enum):
    SEEKING_MOUSE      = "seeking_mouse"
    DRAGGING_MOUSE_AWAY = "dragging_mouse_away"
    DECELERATING       = "decelerating"


@dataclass
class NabMouseState:
    stage: NabMouseStage = NabMouseStage.SEEKING_MOUSE
    chase_start_time: float = 0.0
    grabbed_time: float = 0.0
    original_vector_to_mouse: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    drag_to: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))


def enter(goose: Goose) -> None:
    from pygoose.goose.goose import SpeedTier
    goose._set_speed(SpeedTier.CHARGE)
    goose.task_state = NabMouseState(chase_start_time=goose.time_keeper.time)


def tick(goose: Goose) -> None:
    from pygoose.goose.goose import Task, SpeedTier
    t = goose.time_keeper.time
    n: NabMouseState = goose.task_state
    cursor_pos = goose._get_cursor_pos()
    beak_tip = goose.rig.head2_end_point

    if n.stage == NabMouseStage.SEEKING_MOUSE:
        goose._set_speed(SpeedTier.CHARGE)
        goose.target_pos = cursor_pos - (beak_tip - goose.position)

        if Vector2.distance(beak_tip, cursor_pos) < MOUSE_GRAB_DISTANCE:
            n.original_vector_to_mouse = cursor_pos - beak_tip
            n.grabbed_time = t
            drag_to = Vector2(goose.position.x, goose.position.y)
            while Vector2.distance(drag_to, goose.position) / 400.0 < 1.2:
                drag_to = Vector2(random_range(0, goose.screen_w), random_range(0, goose.screen_h))
            n.drag_to = drag_to
            goose.target_pos = drag_to
            goose.sound.chomp()
            n.stage = NabMouseStage.DRAGGING_MOUSE_AWAY

        if t > n.chase_start_time + GIVE_UP_TIME:
            n.stage = NabMouseStage.DECELERATING

    elif n.stage == NabMouseStage.DRAGGING_MOUSE_AWAY:
        if Vector2.distance(goose.position, goose.target_pos) < MOUSE_DROP_DISTANCE:
            release_cursor_clip()
            n.stage = NabMouseStage.DECELERATING
        else:
            p = min((t - n.grabbed_time) / MOUSE_SUCC_TIME, 1.0)
            clip_vec = Vector2.lerp(n.original_vector_to_mouse, STRUGGLE_RANGE, p)
            clip_x = beak_tip.x + (clip_vec.x if clip_vec.x >= 0 else clip_vec.x)
            clip_y = beak_tip.y + (clip_vec.y if clip_vec.y >= 0 else clip_vec.y)
            set_cursor_clip(clip_x, clip_y, abs(clip_vec.x), abs(clip_vec.y))

    elif n.stage == NabMouseStage.DECELERATING:
        mag = Vector2.magnitude(goose.velocity)
        if mag > 0.01:
            goose.target_pos = goose.position + Vector2.normalize(goose.velocity) * 5.0
            goose.velocity -= Vector2.normalize(goose.velocity) * goose.current_acceleration * 2.0 * DELTA_TIME
        if mag < 80.0:
            release_cursor_clip()
            goose._set_task(Task.WANDER)
