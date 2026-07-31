from __future__ import annotations
import math as _math
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pygoose.goose.goose import Goose

from pygoose.engine.math_utils import lerp, clamp, random_range
from pygoose.engine.vector2 import Vector2

PEEK_INSET = 14.0


class PeekBackStage(Enum):
    PEEKING_IN  = "peeking_in"
    LOOKING     = "looking"
    WALKING_IN  = "walking_in"
    PAUSING     = "pausing"


@dataclass
class PeekBackState:
    peek_pos: Vector2
    enter_pos: Vector2
    face_dir: float
    sweep_deg: float
    stage: PeekBackStage = PeekBackStage.PEEKING_IN
    look_start_time: float = -1.0
    look_duration: float = 8.8
    walk_in_dist: float = -1.0
    pause_start_time: float = -1.0
    pause_duration: float = 0.0


def enter(goose: Goose) -> None:
    from pygoose.goose.goose import SpeedTier
    goose._set_speed(SpeedTier.SNEAK)
    goose.rig.sit_lerp_percent = 1.0
    goose.rig.neck_tuck_lerp_percent = 1.0
    goose._target_sit_lerp = 1.0
    goose._target_neck_tuck = 1.0

    edge_dists = {
        'left':   goose.position.x,
        'right':  goose.screen_w - goose.position.x,
        'top':    goose.position.y,
        'bottom': goose.screen_h - goose.position.y,
    }
    nearest = min(edge_dists, key=edge_dists.get)
    diag = random_range(80, 180) * __import__('random').choice([-1, 1])
    if nearest == 'left':
        peek_pos  = Vector2(PEEK_INSET, clamp(goose.position.y, 80, goose.screen_h - 80))
        face_dir  = 0.0
        enter_x   = random_range(150, goose.screen_w / 2)
        enter_pos = Vector2(enter_x, clamp(goose.position.y + diag, 80, goose.screen_h - 80))
    elif nearest == 'right':
        peek_pos  = Vector2(goose.screen_w - PEEK_INSET, clamp(goose.position.y, 80, goose.screen_h - 80))
        face_dir  = 180.0
        enter_x   = random_range(goose.screen_w / 2, goose.screen_w - 150)
        enter_pos = Vector2(enter_x, clamp(goose.position.y + diag, 80, goose.screen_h - 80))
    elif nearest == 'top':
        peek_pos  = Vector2(clamp(goose.position.x, 80, goose.screen_w - 80), PEEK_INSET)
        face_dir  = 90.0
        enter_y   = random_range(80, goose.screen_h / 2)
        enter_pos = Vector2(clamp(goose.position.x + diag, 80, goose.screen_w - 80), enter_y)
    else:
        peek_pos  = Vector2(clamp(goose.position.x, 80, goose.screen_w - 80), goose.screen_h - PEEK_INSET)
        face_dir  = -90.0
        enter_y   = random_range(goose.screen_h / 2, goose.screen_h - 80)
        enter_pos = Vector2(clamp(goose.position.x + diag, 80, goose.screen_w - 80), enter_y)

    goose.task_state = PeekBackState(
        peek_pos=peek_pos,
        enter_pos=enter_pos,
        face_dir=face_dir,
        sweep_deg=random_range(45.0, 150.0),
    )
    goose.target_pos = peek_pos


def tick(goose: Goose) -> None:
    from pygoose.goose.goose import Task, SpeedTier
    t = goose.time_keeper.time
    s: PeekBackState = goose.task_state

    if s.stage == PeekBackStage.PEEKING_IN:
        dist = Vector2.distance(goose.position, s.peek_pos)
        goose._set_speed(SpeedTier.SNEAK if dist < 80.0 else SpeedTier.WALK)
        goose._target_sit_lerp = 1.0
        goose._target_neck_tuck = 1.0
        goose.target_pos = s.peek_pos
        if dist < 12.0:
            s.look_start_time = t
            s.stage = PeekBackStage.LOOKING
            goose.rig.sit_lerp_percent = 1.0
            goose.rig.neck_tuck_lerp_percent = 1.0
            goose._target_sit_lerp = 1.0
            goose._target_neck_tuck = 1.0

    elif s.stage == PeekBackStage.LOOKING:
        goose._freeze_position = True
        goose._target_sit_lerp = 1.0
        goose._target_neck_tuck = 1.0
        elapsed = t - s.look_start_time
        t_norm = clamp(elapsed / s.look_duration, 0.0, 1.0)
        ramp = 0.18
        ease_in  = clamp(t_norm / ramp, 0.0, 1.0)
        ease_out = clamp((1.0 - t_norm) / ramp, 0.0, 1.0)
        envelope = min(ease_in * ease_in * (3 - 2 * ease_in),
                       ease_out * ease_out * (3 - 2 * ease_out))
        sweep = _math.sin(t_norm * 2 * _math.pi) * (s.sweep_deg / 2.0) * envelope
        target_dir = s.face_dir + sweep
        rad = _math.radians(target_dir)
        sweep_pt = goose.position + Vector2(_math.cos(rad), _math.sin(rad)) * 300.0
        exit_blend = clamp((t_norm - (1.0 - ramp)) / ramp, 0.0, 1.0)
        goose.target_pos = Vector2(
            lerp(sweep_pt.x, s.enter_pos.x, exit_blend),
            lerp(sweep_pt.y, s.enter_pos.y, exit_blend),
        )
        if elapsed >= s.look_duration:
            goose._freeze_position = False
            s.stage = PeekBackStage.WALKING_IN

    elif s.stage == PeekBackStage.WALKING_IN:
        goose._set_speed(SpeedTier.SNEAK)
        goose.target_pos = s.enter_pos
        dist_remaining = Vector2.distance(goose.position, s.enter_pos)
        if s.walk_in_dist < 0:
            s.walk_in_dist = max(dist_remaining, 1.0)
        progress = clamp(1.0 - dist_remaining / s.walk_in_dist, 0.0, 1.0)
        goose._target_sit_lerp  = 1.0 - progress
        goose._target_neck_tuck = 1.0 - progress
        if dist_remaining < 12.0:
            s.pause_start_time = t
            s.pause_duration = random_range(0.5, 1.5)
            s.stage = PeekBackStage.PAUSING

    elif s.stage == PeekBackStage.PAUSING:
        goose._freeze_position = True
        if t - s.pause_start_time >= s.pause_duration:
            goose._set_task(Task.WANDER)
