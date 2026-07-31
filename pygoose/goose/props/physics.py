from __future__ import annotations
import random as _random

from pygoose.engine.vector2 import Vector2
from pygoose.goose.props.prop import Prop, PropState, PROP_REGISTRY

GRAVITY = 220.0   # px/s² (tunable by feel)
MIN_BOUNCE_VEL = 6.0   # below this z_vel after bounce → settle to PLACED


def random_spin(min_deg: float = 400.0, max_deg: float = 700.0) -> float:
    """Random spin rate in deg/s, left or right. Pass to launch_prop_falling."""
    return _random.choice([-1, 1]) * _random.uniform(min_deg, max_deg)


def launch_prop_falling(
    prop: Prop,
    position: Vector2,
    z: float,
    z_vel: float = -80.0,
    velocity: Vector2 | None = None,
    angular_velocity: float = 0.0,
) -> None:
    """Put a prop into FALLING state. Call random_spin() for angular_velocity when a spin is wanted."""
    prop.state            = PropState.FALLING
    prop.position         = position
    prop.z                = max(0.0, z)
    prop.z_vel            = z_vel
    prop.velocity         = velocity if velocity is not None else Vector2(0.0, 0.0)
    prop.angular_velocity = angular_velocity


def tick_props(props: list[Prop], dt: float) -> None:
    for prop in props:
        if prop.state == PropState.FALLING:
            _tick_falling(prop, dt)


def _tick_falling(prop: Prop, dt: float) -> None:
    defn          = PROP_REGISTRY.get(prop.prop_type)
    gravity_scale = defn.gravity_scale if defn else 1.0
    restitution   = defn.restitution   if defn else 0.1
    friction      = defn.friction      if defn else 0.6

    prop.z_vel -= GRAVITY * gravity_scale * dt
    prop.z     += prop.z_vel * dt

    prop.position = Vector2(
        prop.position.x + prop.velocity.x * dt,
        prop.position.y + prop.velocity.y * dt,
    )
    prop.angle += prop.angular_velocity * dt

    if prop.z <= 0.0:
        prop.z = 0.0
        bounce_vel = -prop.z_vel * restitution
        if bounce_vel < MIN_BOUNCE_VEL:
            prop.z_vel            = 0.0
            prop.velocity         = Vector2(prop.velocity.x * friction, prop.velocity.y * friction)
            prop.angular_velocity = 0.0
            prop.state            = PropState.PLACED
        else:
            prop.z_vel    = bounce_vel
            prop.velocity = Vector2(prop.velocity.x * friction, prop.velocity.y * friction)
