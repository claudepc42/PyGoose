from __future__ import annotations
import math as _math
import random as _random
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pygoose.goose.goose import Goose

from pygoose.engine.math_utils import random_range, clamp
from pygoose.engine.vector2 import Vector2

HOLD_DIST_MIN       = 80.0    # px from cursor during stare-down
HOLD_DIST_MAX       = 120.0
STARE_MIN           = 8.0     # seconds before timeout victory
STARE_MAX           = 20.0
STARTLE_DIST        = 45.0    # cursor this close → startle exit
ARRIVE_DIST         = 20.0    # px — close enough to hold position
BOB_INTERVAL_MIN    = 0.25    # seconds between head bobs during stare-down
BOB_INTERVAL_MAX    = 0.7
BOB_DURATION        = 0.35    # seconds of neck extension per bob
LUNGE_INTERVAL_MIN  = 5.0     # seconds between faint lunges
LUNGE_INTERVAL_MAX  = 12.0
LUNGE_DURATION      = 0.35    # seconds of forward dash
VICTORY_WALK_DIST   = 180.0   # px away from cursor after timeout
LAP_RADIUS_MIN      = 70.0
LAP_RADIUS_MAX      = 120.0
LAP_BOB_INTERVAL    = 0.5     # seconds between head bobs during victory lap (2/sec)
LAP_HONK_INTERVAL   = 1.3     # seconds between honks during victory lap
LAP_TARGET_STEP     = 0.35    # radians per waypoint (~20°)
LAP_ARRIVE_DIST     = 40.0    # px to consider a lap waypoint reached


class KnifeThreatStage(Enum):
    APPROACH       = "approach"
    STARE_DOWN     = "stare_down"
    LUNGE_DASH     = "lunge_dash"
    LUNGE_RETREAT  = "lunge_retreat"
    VICTORY_WALK   = "victory_walk"
    VICTORY_LAP    = "victory_lap"


@dataclass
class KnifeThreatState:
    stage: KnifeThreatStage = KnifeThreatStage.APPROACH
    hold_dist: float        = 100.0
    stare_end_time: float   = 0.0
    next_bob_time: float    = 0.0
    bob_end_time: float     = -1.0   # -1=idle, else time when current bob ends
    next_lunge_time: float  = 0.0
    lunge_end_time: float   = -1.0
    retreat_target: Vector2 = field(default_factory=Vector2)
    victory_target: Vector2 = field(default_factory=Vector2)
    lap_center: Vector2     = field(default_factory=Vector2)
    lap_radius: float       = 200.0
    lap_angle: float        = 0.0    # current angle on circle (radians)
    lap_direction: float    = 1.0    # +1 clockwise, -1 counter-clockwise
    lap_covered: float      = 0.0    # accumulated radians; done when >= 2π
    next_honk_time: float   = 0.0


def enter(goose: Goose) -> None:
    from pygoose.goose.goose import SpeedTier
    t = goose.time_keeper.time
    goose._set_speed(SpeedTier.WALK)
    goose.task_state = KnifeThreatState(
        hold_dist      = random_range(HOLD_DIST_MIN, HOLD_DIST_MAX),
        stare_end_time = -1.0,  # set when STARE_DOWN begins, not during approach
        next_bob_time  = t + random_range(BOB_INTERVAL_MIN, BOB_INTERVAL_MAX),
        next_lunge_time= t + random_range(LUNGE_INTERVAL_MIN, LUNGE_INTERVAL_MAX),
    )
    goose.override_extend_neck = True


def tick(goose: Goose) -> None:
    from pygoose.goose.goose import Task, SpeedTier
    t      = goose.time_keeper.time
    s: KnifeThreatState = goose.task_state
    cursor = goose._get_cursor_pos()

    # ---- APPROACH -------------------------------------------------------
    if s.stage == KnifeThreatStage.APPROACH:
        goose._set_speed(SpeedTier.WALK)
        goose.override_extend_neck = True
        to_goose = Vector2.normalize(goose.position - cursor)
        goose.target_pos = cursor + to_goose * s.hold_dist
        if Vector2.distance(goose.position, cursor) <= s.hold_dist + ARRIVE_DIST:
            goose._freeze_position = True
            s.stare_end_time = goose.time_keeper.time + random_range(STARE_MIN, STARE_MAX)
            s.stage = KnifeThreatStage.STARE_DOWN

    # ---- STARE_DOWN -----------------------------------------------------
    elif s.stage == KnifeThreatStage.STARE_DOWN:
        goose._freeze_position = True
        goose.target_pos = goose.position + Vector2.normalize(cursor - goose.position) * 50.0

        # Startle exit
        if Vector2.distance(goose.position, cursor) < STARTLE_DIST:
            _trigger_startle(goose, cursor)
            return

        # Timeout → victory
        if s.stare_end_time > 0 and t >= s.stare_end_time:
            goose.sound.honk()
            _begin_victory_walk(goose, s, cursor)
            return

        # Head bob (same pattern as wander/watch_mouse)
        if s.bob_end_time > 0:
            goose.override_extend_neck = True
            if t >= s.bob_end_time:
                goose.override_extend_neck = False
                s.bob_end_time = -1.0
                s.next_bob_time = t + random_range(BOB_INTERVAL_MIN, BOB_INTERVAL_MAX)
        elif t >= s.next_bob_time:
            s.bob_end_time = t + BOB_DURATION
        else:
            goose.override_extend_neck = False

        # Faint lunge
        if t >= s.next_lunge_time:
            goose._freeze_position = False
            goose._set_speed(SpeedTier.CHARGE)
            goose.target_pos = cursor
            goose.sound.honk()
            s.lunge_end_time = t + LUNGE_DURATION
            s.stage = KnifeThreatStage.LUNGE_DASH

    # ---- LUNGE_DASH -----------------------------------------------------
    elif s.stage == KnifeThreatStage.LUNGE_DASH:
        goose.override_extend_neck = True
        if t >= s.lunge_end_time:
            to_goose = Vector2.normalize(goose.position - cursor)
            s.retreat_target = _clamp_to_screen(
                cursor + to_goose * (s.hold_dist + 20.0), goose
            )
            goose._set_speed(SpeedTier.WALK)
            goose.target_pos = s.retreat_target
            s.stage = KnifeThreatStage.LUNGE_RETREAT

    # ---- LUNGE_RETREAT --------------------------------------------------
    elif s.stage == KnifeThreatStage.LUNGE_RETREAT:
        goose.override_extend_neck = True
        if Vector2.distance(goose.position, s.retreat_target) < ARRIVE_DIST:
            goose._freeze_position = True
            s.next_lunge_time = t + random_range(LUNGE_INTERVAL_MIN, LUNGE_INTERVAL_MAX)
            s.bob_end_time = -1.0
            s.next_bob_time = t + random_range(BOB_INTERVAL_MIN, BOB_INTERVAL_MAX)
            s.stage = KnifeThreatStage.STARE_DOWN

    # ---- VICTORY_WALK ---------------------------------------------------
    elif s.stage == KnifeThreatStage.VICTORY_WALK:
        goose.override_extend_neck = True
        if Vector2.distance(goose.position, s.victory_target) < ARRIVE_DIST:
            _begin_victory_lap(goose, s)

    # ---- VICTORY_LAP ----------------------------------------------------
    elif s.stage == KnifeThreatStage.VICTORY_LAP:
        if s.bob_end_time > 0:
            goose.override_extend_neck = True
            if t >= s.bob_end_time:
                goose.override_extend_neck = False
                s.bob_end_time = -1.0
                s.next_bob_time = t + LAP_BOB_INTERVAL
        elif t >= s.next_bob_time:
            s.bob_end_time = t + BOB_DURATION
        else:
            goose.override_extend_neck = False

        if t >= s.next_honk_time:
            goose.sound.honk()
            s.next_honk_time = t + LAP_HONK_INTERVAL

        if Vector2.distance(goose.position, goose.target_pos) < LAP_ARRIVE_DIST:
            s.lap_angle += LAP_TARGET_STEP * s.lap_direction
            s.lap_covered += LAP_TARGET_STEP
            if s.lap_covered >= 2 * _math.pi:
                goose._release_carried_prop()
                goose._set_task(Task.WANDER, honk=False)
                return
            jitter_r = s.lap_radius + random_range(-30.0, 30.0)
            jitter_a = s.lap_angle + random_range(-0.08, 0.08)
            goose.target_pos = _clamp_to_screen(Vector2(
                s.lap_center.x + _math.cos(jitter_a) * jitter_r,
                s.lap_center.y + _math.sin(jitter_a) * jitter_r,
            ), goose)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trigger_startle(goose: Goose, cursor: Vector2) -> None:
    from pygoose.goose.goose import Task
    goose._release_carried_prop()
    away = Vector2.normalize(goose.position - cursor)
    perp = Vector2(-away.y, away.x)
    off_base = goose.position + away * 400.0
    goose._freak_bounce_a = off_base + perp * 70.0
    goose._freak_bounce_b = off_base - perp * 70.0
    goose._freak_bounce_to_a = True
    goose._freak_out_until = goose.time_keeper.time + 4.0
    goose._freak_out_next_honk = goose.time_keeper.time
    goose._set_task(Task.WANDER, honk=False)


def _begin_victory_walk(goose: Goose, s: KnifeThreatState, cursor: Vector2) -> None:
    from pygoose.goose.goose import SpeedTier
    goose._freeze_position = False
    goose._set_speed(SpeedTier.WALK)
    away = Vector2.normalize(goose.position - cursor)
    s.victory_target = _clamp_to_screen(goose.position + away * VICTORY_WALK_DIST, goose)
    goose.target_pos = s.victory_target
    s.stage = KnifeThreatStage.VICTORY_WALK


def _begin_victory_lap(goose: Goose, s: KnifeThreatState) -> None:
    from pygoose.goose.goose import SpeedTier
    t = goose.time_keeper.time
    goose._set_speed(SpeedTier.WALK)
    s.lap_radius    = random_range(LAP_RADIUS_MIN, LAP_RADIUS_MAX)
    s.lap_direction = _random.choice([-1.0, 1.0])
    # Place center so goose starts on the circle perimeter
    center_dir = _random.uniform(0, 2 * _math.pi)
    s.lap_center = Vector2(
        goose.position.x + _math.cos(center_dir) * s.lap_radius,
        goose.position.y + _math.sin(center_dir) * s.lap_radius,
    )
    s.lap_angle   = _math.atan2(
        goose.position.y - s.lap_center.y,
        goose.position.x - s.lap_center.x,
    )
    s.lap_covered     = 0.0
    s.next_honk_time  = t + LAP_HONK_INTERVAL * 0.5
    s.bob_end_time    = -1.0
    s.next_bob_time   = t + LAP_BOB_INTERVAL * 0.5
    # First waypoint
    first_angle = s.lap_angle + LAP_TARGET_STEP * s.lap_direction
    goose.target_pos = _clamp_to_screen(Vector2(
        s.lap_center.x + _math.cos(first_angle) * s.lap_radius,
        s.lap_center.y + _math.sin(first_angle) * s.lap_radius,
    ), goose)
    s.stage = KnifeThreatStage.VICTORY_LAP


def _clamp_to_screen(pos: Vector2, goose: Goose) -> Vector2:
    margin = 60.0
    return Vector2(
        clamp(pos.x, margin, goose.screen_w - margin),
        clamp(pos.y, margin + 40.0, goose.screen_h - margin),
    )
