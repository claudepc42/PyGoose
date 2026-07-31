from __future__ import annotations
import math
import random
# Module-level aliases so hot per-tick task handlers don't re-import every frame
_math = math
_random = random

from dataclasses import dataclass, field
from enum import Enum

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QMetaObject, Qt, QRect
from PyQt6.QtGui import QCursor

from pygoose.engine.vector2 import Vector2
from pygoose.engine.math_utils import lerp, clamp, random_range
from pygoose.engine.easings import cubic_ease_in_out
from pygoose.engine.rig import Rig
from pygoose.engine.deck import Deck
from pygoose.engine.time_keeper import TimeKeeper, DELTA_TIME
from pygoose.goose.renderer import (
    update_rig, render_goose, render_goose_body, render_goose_head,
    render_foot_marks, FOOT_MARK_LIFETIME, FOOT_MARK_SHRINK_TIME,
)
from pygoose.goose.cursor import set_cursor_clip, release_cursor_clip, is_left_mouse_down
from pygoose.goose.sound import Sound
import pygoose.goose.behaviors.wander      as _b_wander
import pygoose.goose.behaviors.track_mud   as _b_track_mud
import pygoose.goose.behaviors.nab_mouse   as _b_nab_mouse
import pygoose.goose.behaviors.watch_mouse  as _b_watch_mouse
import pygoose.goose.behaviors.follow_mouse  as _b_follow_mouse
import pygoose.goose.behaviors.sneak_attack  as _b_sneak_attack
import pygoose.goose.behaviors.sleep         as _b_sleep
import pygoose.goose.behaviors.peek_back     as _b_peek_back
import pygoose.goose.behaviors.collect_window as _b_collect
import pygoose.goose.behaviors.carry_prop    as _b_carry_prop
import pygoose.goose.behaviors.knife_threat  as _b_knife_threat
from pygoose.goose.behaviors.sleep    import SleepStage
from pygoose.goose.behaviors.peek_back import PeekBackStage
from pygoose.goose.behaviors.watch_mouse import WatchSubState
from pygoose.goose.props.prop import Prop, PropType, PropState
from pygoose.goose.props.prop_renderer import render_props
from pygoose.goose.props.physics import tick_props


# ---------------------------------------------------------------------------
# Speed tiers
# ---------------------------------------------------------------------------

class SpeedTier(Enum):
    SNEAK  = "sneak"
    WALK   = "walk"
    RUN    = "run"
    CHARGE = "charge"

SPEEDS = {
    SpeedTier.SNEAK:  {"speed": 28.0,  "acceleration": 600.0,  "step_time": 0.45},
    SpeedTier.WALK:   {"speed": 80.0,  "acceleration": 1300.0, "step_time": 0.2},
    SpeedTier.RUN:    {"speed": 200.0, "acceleration": 1300.0, "step_time": 0.2},
    SpeedTier.CHARGE: {"speed": 400.0, "acceleration": 2300.0, "step_time": 0.1},
}


# ---------------------------------------------------------------------------
# Task enum
# ---------------------------------------------------------------------------

class Task(Enum):
    WANDER                = "wander"
    NAB_MOUSE             = "nab_mouse"
    COLLECT_WINDOW_MEME   = "collect_window_meme"
    COLLECT_WINDOW_NOTEPAD= "collect_window_notepad"
    TRACK_MUD             = "track_mud"
    WATCH_MOUSE           = "watch_mouse"
    FOLLOW_MOUSE          = "follow_mouse"
    SNEAK_ATTACK          = "sneak_attack"
    SLEEP                 = "sleep"
    PEEK_BACK             = "peek_back"
    CARRY_PROP            = "carry_prop"
    KNIFE_THREAT          = "knife_threat"


TASK_WEIGHTED_LIST = [
    Task.TRACK_MUD,                 # 2/18
    Task.TRACK_MUD,
    Task.COLLECT_WINDOW_MEME,       # 2/18
    Task.COLLECT_WINDOW_MEME,
    Task.COLLECT_WINDOW_NOTEPAD,    # 2/18
    Task.COLLECT_WINDOW_NOTEPAD,
    Task.NAB_MOUSE,                 # 3/18
    Task.NAB_MOUSE,
    Task.NAB_MOUSE,
    Task.WATCH_MOUSE,               # 2/18
    Task.WATCH_MOUSE,
    Task.FOLLOW_MOUSE,              # 2/18
    Task.FOLLOW_MOUSE,
    Task.SNEAK_ATTACK,              # 1/18
    Task.SLEEP,                     # 1/18
    Task.CARRY_PROP,                # 3/18
    Task.CARRY_PROP,
    Task.CARRY_PROP,
]


# ---------------------------------------------------------------------------
# Screen direction
# ---------------------------------------------------------------------------

class ScreenDirection(Enum):
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"











# ---------------------------------------------------------------------------
# Foot mark
# ---------------------------------------------------------------------------

FOOT_MARK_BUFFER_SIZE = 64

@dataclass
class FootMark:
    position: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    time: float = 0.0


# ---------------------------------------------------------------------------
# Goose
# ---------------------------------------------------------------------------

FEET_DISTANCE_APART = 6.0
OVERSHOOT_FRACTION = 0.4
WANT_STEP_AT_DISTANCE = 5.0

# Dirty-rect extents around the goose position (px). Must fully contain every
# drawn pixel in all states (extended neck, beak, shadow, feet, sleep bubbles,
# exclamation) or repaints would clip. Measured worst-case extents across the
# full state space (all directions, neck/sit/tuck extremes, bubbles, exclamation)
# are L=49.5 R=51.3 U=96.0 D=36.5, so these are comfortably generous. (Shrinking
# the box was measured to give no CPU benefit — Qt re-blits the whole translucent
# layered window per update regardless of region — so we keep the safe margins.)
DIRTY_LEFT  = 100
DIRTY_RIGHT = 100
DIRTY_UP    = 110
DIRTY_DOWN  = 90


# ---------------------------------------------------------------------------
# Behavior dispatch tables — keyed on Task, populated after all imports
# ---------------------------------------------------------------------------

_BEHAVIOR_ENTER: dict = {}
_BEHAVIOR_TICK:  dict = {}


def _build_dispatch_tables():
    _BEHAVIOR_ENTER[Task.WANDER]                 = _b_wander.enter
    _BEHAVIOR_ENTER[Task.TRACK_MUD]              = _b_track_mud.enter
    _BEHAVIOR_ENTER[Task.NAB_MOUSE]              = _b_nab_mouse.enter
    _BEHAVIOR_ENTER[Task.COLLECT_WINDOW_NOTEPAD] = _b_collect.enter
    _BEHAVIOR_ENTER[Task.COLLECT_WINDOW_MEME]    = _b_collect.enter
    _BEHAVIOR_ENTER[Task.WATCH_MOUSE]            = _b_watch_mouse.enter
    _BEHAVIOR_ENTER[Task.FOLLOW_MOUSE]           = _b_follow_mouse.enter
    _BEHAVIOR_ENTER[Task.SNEAK_ATTACK]           = _b_sneak_attack.enter
    _BEHAVIOR_ENTER[Task.SLEEP]                  = _b_sleep.enter
    _BEHAVIOR_ENTER[Task.PEEK_BACK]              = _b_peek_back.enter
    _BEHAVIOR_ENTER[Task.CARRY_PROP]             = _b_carry_prop.enter
    _BEHAVIOR_ENTER[Task.KNIFE_THREAT]           = _b_knife_threat.enter

    _BEHAVIOR_TICK[Task.WANDER]                 = _b_wander.tick
    _BEHAVIOR_TICK[Task.TRACK_MUD]              = _b_track_mud.tick
    _BEHAVIOR_TICK[Task.NAB_MOUSE]              = _b_nab_mouse.tick
    _BEHAVIOR_TICK[Task.COLLECT_WINDOW_NOTEPAD] = _b_collect.tick
    _BEHAVIOR_TICK[Task.COLLECT_WINDOW_MEME]    = _b_collect.tick
    _BEHAVIOR_TICK[Task.WATCH_MOUSE]            = _b_watch_mouse.tick
    _BEHAVIOR_TICK[Task.FOLLOW_MOUSE]           = _b_follow_mouse.tick
    _BEHAVIOR_TICK[Task.SNEAK_ATTACK]           = _b_sneak_attack.tick
    _BEHAVIOR_TICK[Task.SLEEP]                  = _b_sleep.tick
    _BEHAVIOR_TICK[Task.PEEK_BACK]              = _b_peek_back.tick
    _BEHAVIOR_TICK[Task.CARRY_PROP]             = _b_carry_prop.tick
    _BEHAVIOR_TICK[Task.KNIFE_THREAT]           = _b_knife_threat.tick


_build_dispatch_tables()


class Goose:
    def __init__(self, config=None):
        self.config = config

        screen = QApplication.primaryScreen().geometry()
        self.screen_w = float(screen.width())
        self.screen_h = float(screen.height())

        self.position = Vector2(-20.0, 120.0)
        self.velocity = Vector2.zero
        self.direction = 0.0
        self.target_pos = Vector2(100.0, 150.0)

        self.current_speed = SPEEDS[SpeedTier.WALK]["speed"]
        self.current_acceleration = SPEEDS[SpeedTier.WALK]["acceleration"]
        self.step_time = SPEEDS[SpeedTier.WALK]["step_time"]

        self.rig = Rig()
        self.override_extend_neck = False

        # Feet
        self.l_foot_pos = Vector2(self.position.x - FEET_DISTANCE_APART, self.position.y)
        self.r_foot_pos = Vector2(self.position.x + FEET_DISTANCE_APART, self.position.y)
        self.l_foot_move_origin = Vector2.zero
        self.r_foot_move_origin = Vector2.zero
        self.l_foot_move_dir = Vector2.zero
        self.r_foot_move_dir = Vector2.zero
        self.l_foot_move_time_start = -1.0
        self.r_foot_move_time_start = -1.0

        # Footmarks
        self.foot_marks = [FootMark() for _ in range(FOOT_MARK_BUFFER_SIZE)]
        self.foot_mark_index = 0
        self.track_mud_end_time = -1.0

        # Task
        self.task_picker_deck = Deck(len(TASK_WEIGHTED_LIST))
        self.current_task = Task.WANDER
        self.task_state: object = None

        # Placed windows — up to 2 of each type kept on screen
        self._placed_memes: list = []
        self._placed_notepads: list = []
        # Anger tracking: only the most recently placed window triggers NAB_MOUSE if closed
        self._anger_window = None
        self._anger_time = -1.0
        self._anger_closed = False
        self._anger_permanent = False

        # Props
        self.carrying_prop: Prop | None = None
        self.props: list[Prop] = []
        self._dev_debug_props = False
        self._last_task_name: str = ""
        self._pending_drop = False
        self._pending_drop_deadline = 0.0
        if config and config.dev_force_spawn_prop:
            try:
                pt = PropType(config.dev_force_spawn_prop.lower())
                self.props.append(Prop(
                    prop_type=pt,
                    position=Vector2(270, self.screen_h - 728),
                    state=PropState.PLACED,
                ))
                self._dev_debug_props = True
            except ValueError:
                pass

        # Mouse polling state
        self._last_mouse_down = False

        # Render-skip: signature of the last frame's render-affecting state.
        # When nothing that influences drawn pixels has changed, the overlay can
        # skip the repaint entirely (the layered window keeps the last frame).
        self._last_render_sig = None

        self._target_sit_lerp = 0.0
        self._target_neck_tuck = 0.0
        self._freeze_position = False
        self._freak_out_until = -1.0
        self._freak_out_next_honk = -1.0
        self._freak_bounce_a: Vector2 = Vector2.zero
        self._freak_bounce_b: Vector2 = Vector2.zero
        self._freak_bounce_to_a: bool = True

        self.sound = Sound(silence=config.silence_sounds if config else False,
                           silence_music=config.silence_music if config else False)
        self.time_keeper = TimeKeeper()
        self._set_task(Task.WANDER, honk=False)

    # -----------------------------------------------------------------------
    # Public
    # -----------------------------------------------------------------------

    def tick(self):
        self.time_keeper.tick()
        t = self.time_keeper.time
        tick_props(self.props, self.time_keeper.delta_time)
        if self._pending_drop and self._pending_drop_deadline > 0 and t >= self._pending_drop_deadline:
            self._do_drop_mid_walk()
        self._check_placed_windows()
        self._check_petting()
        self._run_physics()
        self._solve_feet()
        self._update_neck()
        self.rig.sit_lerp_percent       = lerp(self.rig.sit_lerp_percent,       self._target_sit_lerp,  0.06)
        self.rig.neck_tuck_lerp_percent = lerp(self.rig.neck_tuck_lerp_percent, self._target_neck_tuck, 0.06)
        sleeping = (self.current_task == Task.SLEEP
                    and self.task_state is not None
                    and self.task_state.stage == SleepStage.SLEEPING)
        self.rig.is_sleeping = sleeping
        self.rig.show_sleep_bubbles = sleeping and (self.task_state is not None and not self.task_state.is_fake_sleep)
        if not sleeping:
            self.rig.peek_eye = 0
        if sleeping:
            self.rig.sleep_phase += DELTA_TIME

    def render(self, painter):
        render_props(painter, self.props, debug=self._dev_debug_props)
        if self.config and self.config.dev_hide_goose:
            return
        render_foot_marks(painter, self.foot_marks, self.time_keeper.time)
        update_rig(self.position, self.direction, self.rig)
        if self.carrying_prop is not None:
            from pygoose.goose.props.prop_renderer import _render_knife_in_beak, _render_shadow
            fwd = Vector2.get_from_angle_degrees(self.direction)
            knife_angle = self.direction + 90.0
            shadow_prop = self.carrying_prop
            shadow_prop.position = Vector2(
                self.position.x + fwd.x * 31.0,
                self.position.y + fwd.y * 25.0,
            )
            shadow_prop.z     = 30.0
            shadow_prop.angle = knife_angle
            _render_shadow(painter, shadow_prop)
            render_goose_body(
                painter, self.rig, self.position, self.direction,
                self.l_foot_pos, self.r_foot_pos, self.config,
            )
            _render_knife_in_beak(painter, self.rig, self.direction)
            render_goose_head(painter, self.rig, self.direction, self.config)
        else:
            render_goose(
                painter, self.rig, self.position, self.direction,
                self.l_foot_pos, self.r_foot_pos, self.config,
            )
        if self.config and (self.config.dev_force_task or self.config.dev_short_wander
                            or self.config.dev_force_fake_sleep or self.config.dev_hide_goose):
            self._render_dev_hud(painter)

    def _render_dev_hud(self, painter) -> None:
        from PyQt6.QtCore import QRectF
        from PyQt6.QtGui import QColor, QFont
        from PyQt6.QtCore import Qt
        task_name = self.current_task.value if self.current_task else "?"
        stage_name = ""
        if self.task_state and hasattr(self.task_state, "stage"):
            stage_name = f" / {self.task_state.stage.value}"
        current_text = f"now:  {task_name}{stage_name}"
        last_text    = f"last: {self._last_task_name or '—'}"
        font = QFont("Courier New", 9)
        painter.setFont(font)
        fm = painter.fontMetrics()
        pad = 6
        line_h = fm.height()
        w = max(fm.horizontalAdvance(current_text), fm.horizontalAdvance(last_text)) + pad * 2
        h = line_h * 2 + pad * 2
        x = int(self.screen_w // 2 - w // 2)
        y = int(self.screen_h - h - 50)
        w = int(w)
        h = int(h)
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 160))
        painter.drawRoundedRect(x, y, w, h, 4, 4)
        painter.setPen(QColor(220, 220, 220))
        painter.drawText(QRectF(x + pad, y + pad, w - pad * 2, line_h), Qt.AlignmentFlag.AlignLeft, current_text)
        painter.setPen(QColor(160, 160, 160))
        painter.drawText(QRectF(x + pad, y + pad + line_h, w - pad * 2, line_h), Qt.AlignmentFlag.AlignLeft, last_text)
        painter.restore()

    def dirty_rect(self):
        """Decide whether this frame needs repainting and, if so, which region.

        Returns ``None`` when every pixel-affecting input is unchanged from the
        last painted frame (the overlay then skips the repaint — the layered
        window already holds identical pixels). Otherwise returns the QRect to
        invalidate: the goose's box, unioned with any footmarks mid-shrink.

        The signature below is the *complete* set of inputs consumed by
        ``render_foot_marks`` + ``update_rig`` + ``render_goose``. Comparing the
        raw values (not quantized) guarantees a skipped frame is bitwise
        identical, so this can never change what the user sees.
        """
        rig = self.rig
        # sleep_phase only affects pixels while bubbles are shown (real sleep);
        # during fake sleep it still increments but draws nothing, so exclude it.
        sleep_token = rig.sleep_phase if rig.show_sleep_bubbles else 0.0
        sig = (
            self.position.x, self.position.y, self.direction,
            self.l_foot_pos.x, self.l_foot_pos.y,
            self.r_foot_pos.x, self.r_foot_pos.y,
            rig.sit_lerp_percent, rig.neck_tuck_lerp_percent, rig.neck_lerp_percent,
            rig.is_sleeping, rig.show_sleep_bubbles, rig.peek_eye, rig.show_exclamation,
            sleep_token,
        )

        t = self.time_keeper.time
        r = QRect(int(self.position.x) - DIRTY_LEFT, int(self.position.y) - DIRTY_UP,
                  DIRTY_LEFT + DIRTY_RIGHT, DIRTY_UP + DIRTY_DOWN)
        any_mark_animating = False
        for m in self.foot_marks:
            if m.time == 0.0:
                continue
            shrink_start = m.time + FOOT_MARK_LIFETIME
            if shrink_start - 0.1 <= t <= shrink_start + FOOT_MARK_SHRINK_TIME + 0.1:
                any_mark_animating = True
                r = r.united(QRect(int(m.position.x) - 6, int(m.position.y) - 6, 12, 12))

        if self._dev_debug_props or (self.config and (
                self.config.dev_force_task or self.config.dev_short_wander
                or self.config.dev_force_fake_sleep or self.config.dev_hide_goose)):
            self._last_render_sig = sig
            return QRect(0, 0, int(self.screen_w), int(self.screen_h))

        changed = (sig != self._last_render_sig) or any_mark_animating
        self._last_render_sig = sig
        if not changed:
            return None
        return r

    # -----------------------------------------------------------------------
    # Speed
    # -----------------------------------------------------------------------

    def _set_speed(self, tier: SpeedTier):
        self.current_speed = SPEEDS[tier]["speed"]
        self.current_acceleration = SPEEDS[tier]["acceleration"]
        self.step_time = SPEEDS[tier]["step_time"]

    # -----------------------------------------------------------------------
    # Physics
    # -----------------------------------------------------------------------

    def _run_physics(self):
        # Compute target direction before AI updates target_pos (matches original order)
        to_target = Vector2.normalize(self.target_pos - self.position)

        self._run_ai()

        # Freak-out is a physics override, not a task — see _run_physics
        t = self.time_keeper.time
        if self._freak_out_until > 0 and t < self._freak_out_until:
            bounce_target = self._freak_bounce_a if self._freak_bounce_to_a else self._freak_bounce_b
            self.target_pos = bounce_target
            if Vector2.distance(self.position, bounce_target) < 30.0:
                self._freak_bounce_to_a = not self._freak_bounce_to_a
            self._set_speed(SpeedTier.CHARGE)
            self._freeze_position = False
            if t >= self._freak_out_next_honk:
                self.sound.honk()
                self._freak_out_next_honk = t + 0.3
        elif self._freak_out_until > 0:
            self._freak_out_until = -1.0
            self._set_task(Task.PEEK_BACK, honk=False)

        # Turn toward target (lerp angle 25% per frame)
        if not (to_target.x == 0.0 and to_target.y == 0.0):
            current_dir_vec = Vector2.get_from_angle_degrees(self.direction)
            blended = Vector2.lerp(current_dir_vec, to_target, 0.25)
            self.direction = math.degrees(math.atan2(blended.y, blended.x))

        if self._freeze_position:
            self.velocity = Vector2(0.0, 0.0)
            return

        # Cap velocity
        mag = Vector2.magnitude(self.velocity)
        if mag > self.current_speed:
            self.velocity = Vector2.normalize(self.velocity) * self.current_speed

        # Accelerate toward target
        self.velocity += Vector2.normalize(self.target_pos - self.position) * self.current_acceleration * DELTA_TIME

        # Integrate
        self.position += self.velocity * DELTA_TIME

    # -----------------------------------------------------------------------
    # Foot solver
    # -----------------------------------------------------------------------

    def _get_foot_home(self, right_foot: bool) -> Vector2:
        s = self.rig.sit_lerp_percent
        b = 1.0 if right_foot else 0.0
        side = Vector2.get_from_angle_degrees(self.direction + 90.0) * b
        # When crawling: reduce perpendicular spread and push feet downward so
        # they poke below the lowered body in both left and right facing directions.
        perp_dist  = lerp(FEET_DISTANCE_APART, 2.0, s)
        crawl_drop = lerp(0.0, 8.0, s)
        return self.position + side * perp_dist + Vector2(0.0, crawl_drop)

    def _solve_feet(self):
        t = self.time_keeper.time

        if self.l_foot_move_time_start < 0 and self.r_foot_move_time_start < 0:
            if Vector2.distance(self.l_foot_pos, self._get_foot_home(False)) > WANT_STEP_AT_DISTANCE:
                self.l_foot_move_origin = Vector2(self.l_foot_pos.x, self.l_foot_pos.y)
                self.l_foot_move_dir = Vector2.normalize(self._get_foot_home(False) - self.l_foot_pos)
                self.l_foot_move_time_start = t
            elif Vector2.distance(self.r_foot_pos, self._get_foot_home(True)) > WANT_STEP_AT_DISTANCE:
                self.r_foot_move_origin = Vector2(self.r_foot_pos.x, self.r_foot_pos.y)
                self.r_foot_move_dir = Vector2.normalize(self._get_foot_home(True) - self.r_foot_pos)
                self.r_foot_move_time_start = t

        elif self.l_foot_move_time_start > 0:
            target = self._get_foot_home(False) + self.l_foot_move_dir * OVERSHOOT_FRACTION * 5.0
            elapsed = t - self.l_foot_move_time_start
            if elapsed <= self.step_time:
                p = elapsed / self.step_time
                self.l_foot_pos = Vector2.lerp(self.l_foot_move_origin, target, cubic_ease_in_out(p))
            else:
                self.l_foot_pos = target
                self.l_foot_move_time_start = -1.0
                self.sound.play_pat()
                if t < self.track_mud_end_time:
                    self._add_foot_mark(self.l_foot_pos)

        elif self.r_foot_move_time_start > 0:
            target = self._get_foot_home(True) + self.r_foot_move_dir * OVERSHOOT_FRACTION * 5.0
            elapsed = t - self.r_foot_move_time_start
            if elapsed <= self.step_time:
                p = elapsed / self.step_time
                self.r_foot_pos = Vector2.lerp(self.r_foot_move_origin, target, cubic_ease_in_out(p))
            else:
                self.r_foot_pos = target
                self.r_foot_move_time_start = -1.0
                self.sound.play_pat()
                if t < self.track_mud_end_time:
                    self._add_foot_mark(self.r_foot_pos)

    # -----------------------------------------------------------------------
    # Neck lerp
    # -----------------------------------------------------------------------

    def _update_neck(self):
        target_neck = 1.0 if (self.override_extend_neck or self.current_speed >= 200.0) else 0.0
        self.rig.neck_lerp_percent = lerp(self.rig.neck_lerp_percent, target_neck, 0.075)

    # -----------------------------------------------------------------------
    # Foot marks
    # -----------------------------------------------------------------------

    def _add_foot_mark(self, pos: Vector2):
        self.foot_marks[self.foot_mark_index].time = self.time_keeper.time
        self.foot_marks[self.foot_mark_index].position = Vector2(pos.x, pos.y)
        self.foot_mark_index = (self.foot_mark_index + 1) % FOOT_MARK_BUFFER_SIZE

    # -----------------------------------------------------------------------
    # AI dispatcher
    # -----------------------------------------------------------------------

    def _run_ai(self):
        _BEHAVIOR_TICK[self.current_task](self)

    # -----------------------------------------------------------------------
    # Placed window anger check
    # -----------------------------------------------------------------------

    def _check_placed_windows(self):
        if self._anger_window is None:
            return
        t = self.time_keeper.time
        if self._anger_closed:
            self._anger_window = None
            self._anger_closed = False
            self._set_task(Task.NAB_MOUSE)
        elif not self._anger_permanent and t - self._anger_time >= 3.0:
            self._anger_window = None

    def _make_placed_window_close_cb(self, window, window_type: str):
        def on_close():
            lst = self._placed_memes if window_type == "meme" else self._placed_notepads
            if window in lst:
                lst.remove(window)
            if self._anger_window is window:
                self._anger_closed = True
        return on_close

    # -----------------------------------------------------------------------
    # Petting detection
    # -----------------------------------------------------------------------

    def _check_petting(self):
        mouse_down = is_left_mouse_down()
        if mouse_down and not self._last_mouse_down:
            cursor = QCursor.pos()
            mouse_pos = Vector2(float(cursor.x()), float(cursor.y()))

            if self._dev_debug_props and self.props:
                from pygoose.goose.props.prop_renderer import get_debug_flip_rect, toggle_debug_side
                frect = get_debug_flip_rect()
                if frect:
                    fx, fy, fw, fh = frect
                    if fx <= mouse_pos.x <= fx + fw and fy <= mouse_pos.y <= fy + fh:
                        toggle_debug_side(self.props[0], self.screen_w)
                        self._last_mouse_down = mouse_down
                        return

        if (self.current_task != Task.NAB_MOUSE
                and mouse_down
                and not self._last_mouse_down):
            cursor = QCursor.pos()
            mouse_pos = Vector2(float(cursor.x()), float(cursor.y()))
            goose_head = Vector2(self.position.x, self.position.y + 14.0)
            if Vector2.distance(goose_head, mouse_pos) < 30.0:
                if (self.current_task == Task.SLEEP
                        and self.task_state
                        and self.task_state.stage == SleepStage.SLEEPING):
                    self.sound.honk()
                    self._set_task(Task.WANDER)
                elif (self.current_task == Task.WATCH_MOUSE
                        and self.task_state
                        and self.task_state.sub_state == WatchSubState.SIT):
                    r = _random.random()
                    if r < 0.70:
                        self.sound.honk()
                    elif r < 0.90:
                        self._set_task(Task.WANDER)
                    else:
                        self._set_task(Task.NAB_MOUSE)
                else:
                    self._set_task(Task.NAB_MOUSE)
        self._last_mouse_down = mouse_down

    def _set_task(self, task: Task, honk: bool = True):
        self._last_task_name = self.current_task.value if self.current_task else ""
        if self.task_state and hasattr(self.task_state, "stage"):
            self._last_task_name += f" / {self.task_state.stage.value}"
        self.override_extend_neck = False
        self._target_sit_lerp = 0.0
        self._target_neck_tuck = 0.0
        self._freeze_position = False
        self.rig.is_sleeping = False
        self.rig.show_sleep_bubbles = False
        self.rig.peek_eye = 0
        self.rig.show_exclamation = False
        self.rig.sleep_phase = 0.0
        # Drop carried prop on task switch — unless the new task explicitly owns the prop.
        # CARRY_PROP and KNIFE_THREAT both keep the knife in beak across the transition.
        # (_pending_drop=True but deadline still 0 means _begin_end_sequence is mid-flight;
        # let it set the deadline before we fire; any later interrupt clears and drops now).
        _KEEP_PROP = {Task.CARRY_PROP, Task.KNIFE_THREAT}
        if task == Task.KNIFE_THREAT:
            # Threat mode takes ownership of the knife — cancel any pending drop
            self._pending_drop = False
            self._pending_drop_deadline = 0.0
        if task not in _KEEP_PROP and self.carrying_prop is not None:
            if self._pending_drop and self._pending_drop_deadline == 0.0:
                pass  # _begin_end_sequence will commit the deadline on return
            else:
                self._pending_drop = False
                self._pending_drop_deadline = 0.0
                self._release_carried_prop()
        self.current_task = task
        if honk:
            self.sound.honk()
        self.task_state = None
        _BEHAVIOR_ENTER[task](self)

    def _release_carried_prop(self):
        if self.carrying_prop is None:
            return
        from pygoose.goose.props.physics import launch_prop_falling, random_spin
        fwd      = Vector2.get_from_angle_degrees(self.direction)
        beak_tip = self.rig.head2_end_point + fwd * 5.0
        spin = random_spin() if Vector2.magnitude(self.velocity) > 10.0 else 0.0
        launch_prop_falling(
            self.carrying_prop,
            position         = Vector2(beak_tip.x, self.position.y),
            z                = self.position.y - beak_tip.y,
            velocity         = Vector2(_random.uniform(-20.0, 20.0), _random.uniform(-5.0, 5.0)),
            angular_velocity = spin,
        )
        self.props.append(self.carrying_prop)
        self.carrying_prop = None

    def _do_drop_mid_walk(self):
        self._pending_drop = False
        self._pending_drop_deadline = 0.0
        self._freeze_position = False
        self._release_carried_prop()

    def _choose_next_task(self):
        if self.config.dev_force_task:
            self._set_task(Task(self.config.dev_force_task))
            return
        task = TASK_WEIGHTED_LIST[self.task_picker_deck.next()]
        if task not in _BEHAVIOR_TICK:
            task = Task.WANDER
        # Respect attack_randomly config
        attack_ok = (self.config.attack_randomly if self.config else True)
        if not attack_ok and task == Task.NAB_MOUSE:
            task = Task.WANDER
        self._set_task(task)

    def _get_random_wander_duration(self) -> float:
        if self.config.dev_skip_wander:
            return 0.0
        if self.config.dev_short_wander:
            return 3.0
        if self.config:
            return random_range(
                self.config.min_wandering_time_seconds,
                self.config.max_wandering_time_seconds,
            )
        return random_range(20.0, 40.0)

    # -----------------------------------------------------------------------
    # Task: NabMouse
    # -----------------------------------------------------------------------

    def _get_cursor_pos(self) -> Vector2:
        p = QCursor.pos()
        origin = QApplication.primaryScreen().geometry()
        return Vector2(float(p.x() - origin.x()), float(p.y() - origin.y()))

    # -----------------------------------------------------------------------
    # Task: CollectWindow

    def _on_window_closed_early(self):
        if self.task_state is not None:
            self.task_state.window_closed_early = True

    # -----------------------------------------------------------------------
    # Task: WatchMouse
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
    # Task: FollowMouse
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
    # Task: SneakAttack
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
    # Task: TrackMud
    # -----------------------------------------------------------------------

    def _set_target_offscreen(self) -> ScreenDirection:
        if self.position.x > self.screen_w / 2:
            self.target_pos = Vector2(self.screen_w + 50, lerp(self.position.y, self.screen_h / 2, 0.4))
            return ScreenDirection.RIGHT
        else:
            self.target_pos = Vector2(-50, lerp(self.position.y, self.screen_h / 2, 0.4))
            return ScreenDirection.LEFT

