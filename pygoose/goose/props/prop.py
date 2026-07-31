from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from pygoose.engine.vector2 import Vector2


class PropType(Enum):
    KNIFE = "knife"


class PropState(Enum):
    CARRIED    = "carried"
    WORN       = "worn"
    FALLING    = "falling"
    TIPPING    = "tipping"
    CLATTERING = "clattering"
    BOUNCING   = "bouncing"
    RISING     = "rising"
    PLACED     = "placed"
    ACTIVE     = "active"
    BROKEN     = "broken"


@dataclass
class Prop:
    prop_type:        PropType
    position:         Vector2
    z:                float     = 0.0
    z_vel:            float     = 0.0
    angle:            float     = 0.0
    velocity:         Vector2   = field(default_factory=Vector2)
    angular_velocity: float     = 0.0
    state:            PropState = PropState.PLACED
    time_in_state:    float     = 0.0
    scale:            float     = 1.0
    prop_data:        object    = None
    surface_z:        float     = 0.0   # Z of the surface this prop rests on; true world height = surface_z + z
    is_owned:         bool      = False  # True = goose retrieves if disturbed; False = litter


@dataclass
class PropDef:
    render_fn:          Callable
    render_broken_fn:   Callable | None = None
    break_fn:           Callable | None = None  # fn(position, velocity) -> list[PropFragment]
    gravity_scale:      float           = 1.0
    restitution:        float           = 0.1
    friction:           float           = 0.6
    mass:               float           = 1.0   # heavier props absorb more collision energy
    can_tip:            bool            = False
    tip_velocity:       float           = 999.0  # impulse threshold to enter TIPPING
    fall_velocity:      float           = 999.0  # impulse threshold to skip TIPPING -> FALLING
    can_break:          bool            = False
    break_velocity:     float           = 999.0  # impulse threshold for instant BROKEN
    bounces_off_edges:  bool            = False
    carry_offset_fn:    Callable | None = None   # fn(fwd, up, right) -> Vector2; None = beak tip
    idle_animation:     bool            = False
    collision_radius:   float           = 10.0
    attachment_point:   str | None      = None   # rig point name for WORN props (e.g. "HEAD")
    shadow_length:      float           = 20.0   # shadow ellipse long axis (along prop.angle)
    shadow_width:       float           = 6.0    # shadow ellipse short axis
    shadow_offset:      float           = 0.0    # center shift along prop.angle from prop.position
    pickup_offset:      float           = 0.0    # offset along prop.angle from prop.position to pickup/handle center


PROP_REGISTRY: dict[PropType, PropDef] = {}
