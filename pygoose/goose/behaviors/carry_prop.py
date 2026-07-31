from __future__ import annotations
import random as _random
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pygoose.goose.goose import Goose

from pygoose.engine.math_utils import random_range, clamp
from pygoose.engine.vector2 import Vector2
from pygoose.goose.props.prop import Prop, PropType, PropState


HOLD_MIN         = 5.0    # seconds, roughly one wander cycle
HOLD_MAX         = 11.0   # seconds, roughly one wander cycle
PLACE_CHANCE     = 0.5    # probability of a gentle place vs. drop at hold end
THREAT_CHANCE    = 0.40   # probability of entering knife threat when a knife is available
OFFSCREEN_DIST   = 50.0   # px past screen edge before we spawn the prop
ARRIVE_DIST      = 10.0   # px close enough to consider a wander target reached
PICKUP_DIST      = 40.0   # px to stop before the prop (knife ahead of body, not under)
PICKUP_DIP_TIME  = 1.0    # minimum seconds to hold the dip before snatching
PLACE_DIP_TIME   = 1.0    # minimum seconds to hold the dip before placing/dropping
PAUSE_MIN        = 1.0
PAUSE_MAX        = 3.0


class CarryPropStage(Enum):
    EXITING      = "exiting"      # walking to screen edge
    WAITING      = "waiting"      # brief off-screen pause before entering
    ENTERING     = "entering"     # walking back on screen with prop already in beak
    PICKUP_WALK  = "pickup_walk"  # walking to an existing placed prop to retrieve it
    PICKUP_STOP  = "pickup_stop"  # brief pause in front of prop before dipping
    PICKUP_DIP   = "pickup_dip"   # crouching dip to scoop prop off ground
    WANDERING    = "wandering"    # wander around carrying prop; hold timer running
    PAUSING      = "pausing"      # brief pause mid-wander
    PLACING      = "placing"      # crouching dip to set prop on ground


@dataclass
class CarryPropState:
    stage:          CarryPropStage = CarryPropStage.EXITING
    prop_type:      PropType       = PropType.KNIFE
    screen_direction: object       = None
    hold_duration:  float          = 60.0   # committed upfront in enter()
    hold_end_time:  float          = 0.0    # set when wandering begins
    will_place:     bool           = True   # False = drop; forced False on interrupt
    wait_start:     float          = 0.0
    wait_duration:  float          = 0.0
    pause_start:    float          = 0.0
    pause_duration: float          = 0.0
    pickup_target:  object         = None   # Prop being retrieved (PICKUP_WALK stage)
    pickup_stop_start: float       = 0.0
    pickup_dip_start:  float       = 0.0
    place_dip_start:   float       = 0.0
    for_threat:        bool        = False  # if True, hand off to KNIFE_THREAT after pickup


def enter(goose: Goose) -> None:
    from pygoose.goose.goose import SpeedTier

    prop_type = PropType.KNIFE
    state = CarryPropState(
        prop_type     = prop_type,
        hold_duration = random_range(HOLD_MIN, HOLD_MAX),
        will_place    = _random.random() < PLACE_CHANCE,
    )
    goose.task_state = state
    goose._set_speed(SpeedTier.WALK)

    # Count placed and carried knives to inform both threat and cap logic.
    placed = [p for p in goose.props if p.prop_type == prop_type and p.state == PropState.PLACED]
    carrying_same = (goose.carrying_prop is not None and goose.carrying_prop.prop_type == prop_type)

    # Threat mode: if a knife is available and the random check passes, go menacing.
    if (placed or carrying_same) and _random.random() < THREAT_CHANCE:
        from pygoose.goose.goose import Task
        if carrying_same:
            goose._set_task(Task.KNIFE_THREAT)
            return
        # Knife on ground — pick it up first, then hand off to KNIFE_THREAT.
        state.for_threat = True
        state.pickup_target = placed[0]
        state.stage = CarryPropStage.PICKUP_WALK
        goose.target_pos = _handle_pos(placed[0])
        return

    # At cap: retrieve an existing knife rather than fetching a new one.
    if len(placed) + (1 if carrying_same else 0) >= 2 and placed:
        p = placed[0]
        state.pickup_target = p
        state.stage = CarryPropStage.PICKUP_WALK
        goose.target_pos = _handle_pos(p)
        return

    state.screen_direction = goose._set_target_offscreen()


def tick(goose: Goose) -> None:
    from pygoose.goose.goose import Task, SpeedTier

    t  = goose.time_keeper.time
    c: CarryPropState = goose.task_state

    # ---- EXITING: walk to screen edge ----------------------------------
    if c.stage == CarryPropStage.EXITING:
        offscreen = (goose.position.x < -OFFSCREEN_DIST
                     or goose.position.x > goose.screen_w + OFFSCREEN_DIST)
        if offscreen:
            goose.carrying_prop = Prop(
                prop_type = c.prop_type,
                position  = Vector2(goose.position.x, goose.position.y),
                state     = PropState.CARRIED,
            )
            c.wait_start    = t
            c.wait_duration = random_range(0.5, 1.5)
            c.stage         = CarryPropStage.WAITING

    # ---- WAITING: pause off-screen before entering ---------------------
    elif c.stage == CarryPropStage.WAITING:
        goose.velocity = Vector2(0.0, 0.0)
        if t - c.wait_start >= c.wait_duration:
            goose._set_speed(SpeedTier.WALK)
            _set_enter_target(goose, c)
            c.stage = CarryPropStage.ENTERING

    # ---- PICKUP_WALK: walk to an existing placed prop and grab it ------
    elif c.stage == CarryPropStage.PICKUP_WALK:
        if Vector2.distance(goose.position, goose.target_pos) < PICKUP_DIST:
            if goose._pending_drop:
                goose._do_drop_mid_walk()  # swap: drop carried knife just before pickup
            goose.velocity         = Vector2(0.0, 0.0)
            goose._freeze_position = True
            c.pickup_stop_start    = t
            c.stage                = CarryPropStage.PICKUP_STOP

    # ---- PICKUP_STOP: pause briefly in front of prop -------------------
    elif c.stage == CarryPropStage.PICKUP_STOP:
        goose.velocity = Vector2(0.0, 0.0)
        if t - c.pickup_stop_start > 0.5:
            c.pickup_dip_start = t
            c.stage = CarryPropStage.PICKUP_DIP

    # ---- PICKUP_DIP: full crouch + neck extend, grab when reached ------
    elif c.stage == CarryPropStage.PICKUP_DIP:
        goose.override_extend_neck = True
        goose._target_sit_lerp     = 1.0
        dip_done = (t - c.pickup_dip_start >= PICKUP_DIP_TIME
                    and goose.rig.neck_lerp_percent > 0.85
                    and goose.rig.sit_lerp_percent > 0.85)
        if dip_done:
            if c.pickup_target in goose.props:
                goose.props.remove(c.pickup_target)
            goose.carrying_prop            = c.pickup_target
            goose.carrying_prop.state      = PropState.CARRIED
            goose.override_extend_neck     = False
            goose._target_sit_lerp         = 0.0
            goose._freeze_position         = False
            if c.for_threat:
                from pygoose.goose.goose import Task
                goose._set_task(Task.KNIFE_THREAT)
                return
            c.hold_end_time = t + c.hold_duration
            c.stage         = CarryPropStage.WANDERING
            _pick_wander_target(goose)

    # ---- ENTERING: walk on screen with prop in beak --------------------
    elif c.stage == CarryPropStage.ENTERING:
        if Vector2.distance(goose.position, goose.target_pos) < ARRIVE_DIST:
            c.hold_end_time = t + c.hold_duration
            c.stage         = CarryPropStage.WANDERING
            _pick_wander_target(goose)

    # ---- WANDERING: carry prop, pick random targets --------------------
    elif c.stage == CarryPropStage.WANDERING:
        if Vector2.distance(goose.position, goose.target_pos) < ARRIVE_DIST:
            c.pause_start    = t
            c.pause_duration = random_range(PAUSE_MIN, PAUSE_MAX)
            c.stage          = CarryPropStage.PAUSING
            return
        if t >= c.hold_end_time:
            _begin_end_sequence(goose, c)

    # ---- PAUSING: brief stop mid-wander --------------------------------
    elif c.stage == CarryPropStage.PAUSING:
        goose.velocity = Vector2(0.0, 0.0)
        if t - c.pause_start >= c.pause_duration:
            if t >= c.hold_end_time:
                _begin_end_sequence(goose, c)
            else:
                c.stage = CarryPropStage.WANDERING
                _pick_wander_target(goose)

    # ---- PLACING: crouch dip until sit reaches ground, then place ------
    elif c.stage == CarryPropStage.PLACING:
        goose.override_extend_neck = True
        goose._target_sit_lerp     = 1.0
        dip_done = (t - c.place_dip_start >= PLACE_DIP_TIME
                    and goose.rig.sit_lerp_percent > 0.9
                    and goose.rig.neck_lerp_percent > 0.85)
        if dip_done:
            _finish_place(goose)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_enter_target(goose: Goose, c: CarryPropState) -> None:
    from pygoose.goose.goose import ScreenDirection
    margin = 100.0
    if c.screen_direction == ScreenDirection.LEFT:
        tx = random_range(margin, goose.screen_w * 0.45)
    elif c.screen_direction == ScreenDirection.RIGHT:
        tx = random_range(goose.screen_w * 0.55, goose.screen_w - margin)
    else:
        tx = random_range(goose.screen_w * 0.2, goose.screen_w * 0.8)
    ty = random_range(goose.screen_h * 0.3, goose.screen_h - 80.0)
    goose.target_pos = Vector2(
        clamp(tx, margin, goose.screen_w - margin),
        clamp(ty, 100.0, goose.screen_h - 40.0),
    )


def _pick_wander_target(goose: Goose) -> None:
    margin = 80.0
    goose.target_pos = Vector2(
        random_range(margin, goose.screen_w - margin),
        random_range(goose.screen_h * 0.25, goose.screen_h - margin),
    )


def _begin_end_sequence(goose: Goose, c: CarryPropState) -> None:
    if c.will_place:
        goose.velocity         = Vector2(0.0, 0.0)
        goose._freeze_position = True
        c.place_dip_start      = goose.time_keeper.time
        c.stage                = CarryPropStage.PLACING
    else:
        # Pending drop: choose the next task now; drop 0.7 s into the new walk cycle.
        # For WANDER the goose freezes briefly in place before dropping.
        goose._pending_drop          = True
        goose._pending_drop_deadline = 0.0   # signal to _set_task: skip immediate drop
        goose._choose_next_task()
        goose._pending_drop_deadline = goose.time_keeper.time + 0.7
        if goose.current_task.value == "wander":
            goose.velocity         = Vector2(0.0, 0.0)
            goose._freeze_position = True


def _finish_place(goose: Goose) -> None:
    from pygoose.goose.goose import Task
    if goose.carrying_prop is not None:
        fwd      = Vector2.get_from_angle_degrees(goose.direction)
        beak_tip = goose.rig.head2_end_point + fwd * 5.0
        prop          = goose.carrying_prop
        prop.state    = PropState.PLACED
        prop.position = Vector2(beak_tip.x, beak_tip.y)
        prop.z        = 0.0
        goose.props.append(prop)
        goose.carrying_prop = None
    goose.override_extend_neck = False
    goose._target_sit_lerp     = 0.0
    goose._freeze_position     = False
    goose._set_task(Task.WANDER)


def _handle_pos(prop: object) -> Vector2:
    from pygoose.goose.props.prop import PROP_REGISTRY
    defn   = PROP_REGISTRY.get(prop.prop_type)
    offset = defn.pickup_offset if defn else 0.0
    fwd    = Vector2.get_from_angle_degrees(prop.angle)
    return Vector2(prop.position.x + fwd.x * offset, prop.position.y + fwd.y * offset)


