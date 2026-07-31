from math import atan2, degrees, sin, pi
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
from PyQt6.QtCore import Qt, QPointF, QRectF

from pygoose.engine.vector2 import Vector2
from pygoose.engine.math_utils import lerp, clamp
from pygoose.engine.rig import Rig

FOOT_MARK_LIFETIME = 8.5
FOOT_MARK_SHRINK_TIME = 1.0

UP = Vector2(0.0, -1.0)

COLOR_WHITE = QColor("white")
COLOR_LIGHT_GRAY = QColor("lightgray")
COLOR_ORANGE = QColor("orange")
COLOR_BLACK = QColor("black")
COLOR_SADDLE_BROWN = QColor(0x8B, 0x45, 0x13)
COLOR_YELLOW = QColor(0xFF, 0xE0, 0x00)

# Hoisted enum values — avoids repeated Qt enum attribute lookups in the hot paint path
_NO_PEN     = Qt.PenStyle.NoPen
_ROUND_CAP  = Qt.PenCapStyle.RoundCap
_ROUND_JOIN = Qt.PenJoinStyle.RoundJoin
_DENSE4     = Qt.BrushStyle.Dense4Pattern

# Cached pens/brushes. Pen params (color, width, round caps) are constant per run,
# so build each combination once and reuse. Identical params => identical pixels.
_pen_cache: dict = {}
_brush_cache: dict = {}

# Constant brushes built once
_SHADOW_BRUSH = QBrush(QColor(80, 80, 80, 80), _DENSE4)
_BLACK_BRUSH  = QBrush(COLOR_BLACK)
_BROWN_BRUSH  = QBrush(COLOR_SADDLE_BROWN)
_YELLOW_BRUSH = QBrush(COLOR_YELLOW)

# Constant pen for the exclamation mark outline (black, width 1.5, round join)
_EXCLAMATION_PEN = QPen(COLOR_BLACK, 1.5)
_EXCLAMATION_PEN.setJoinStyle(_ROUND_JOIN)


def _get_pen(color: QColor, width: int) -> QPen:
    key = (color.rgba(), width)
    pen = _pen_cache.get(key)
    if pen is None:
        pen = QPen(color, width)
        pen.setCapStyle(_ROUND_CAP)
        pen.setJoinStyle(_ROUND_JOIN)
        _pen_cache[key] = pen
    return pen


def _get_brush(color: QColor) -> QBrush:
    key = color.rgba()
    brush = _brush_cache.get(key)
    if brush is None:
        brush = QBrush(color)
        _brush_cache[key] = brush
    return brush


def update_rig(position: Vector2, direction: float, rig: Rig):
    fwd = Vector2.get_from_angle_degrees(direction)
    s = rig.sit_lerp_percent

    rig.underbody_center = position + UP * lerp(9.0, 1.0, s)
    rig.body_center      = position + UP * lerp(14.0, 4.0, s)

    tuck = rig.neck_tuck_lerp_percent
    neck_height  = int(lerp(lerp(20.0, 10.0, rig.neck_lerp_percent), 6.0,  tuck))
    neck_forward = int(lerp(lerp(3.0,  16.0, rig.neck_lerp_percent), 2.0,  tuck))

    rig.neck_center = position + UP * (14 + neck_height)
    rig.neck_base = rig.body_center + fwd * 15.0
    rig.neck_head_point = rig.neck_base + fwd * neck_forward + UP * neck_height

    rig.head1_end_point = rig.neck_head_point + fwd * 3.0 - UP * 1.0
    rig.head2_end_point = rig.head1_end_point + fwd * 5.0


def _pt(v: Vector2) -> QPointF:
    return QPointF(v.x, v.y)


def _set_pen(painter: QPainter, color: QColor, width: int):
    painter.setPen(_get_pen(color, width))


def render_foot_marks(painter: QPainter, foot_marks: list, current_time: float):
    pen_set = False
    for mark in foot_marks:
        if mark.time == 0.0:
            continue
        shrink_start = mark.time + FOOT_MARK_LIFETIME
        p = clamp((current_time - shrink_start) / FOOT_MARK_SHRINK_TIME, 0.0, 1.0)
        radius = lerp(3.0, 0.0, p)
        if radius > 0:
            if not pen_set:
                # Defer state changes until we actually have a mark to draw
                painter.setPen(_NO_PEN)
                painter.setBrush(_BROWN_BRUSH)
                pen_set = True
            painter.drawEllipse(_pt(mark.position), radius, radius)


def render_goose(painter: QPainter, rig: Rig, position: Vector2, direction: float,
                 l_foot_pos: Vector2, r_foot_pos: Vector2,
                 config=None):
    render_goose_body(painter, rig, position, direction, l_foot_pos, r_foot_pos, config)
    render_goose_head(painter, rig, direction, config)


def render_goose_body(painter: QPainter, rig: Rig, position: Vector2, direction: float,
                      l_foot_pos: Vector2, r_foot_pos: Vector2, config=None):
    """Shadow, feet, outline, and white fill — everything below the beak layer."""
    fwd = Vector2.get_from_angle_degrees(direction)

    body_color   = COLOR_WHITE
    outline_color = COLOR_LIGHT_GRAY
    beak_color   = COLOR_ORANGE
    if config and config.use_custom_colors:
        body_color    = QColor(config.goose_color_body)
        outline_color = QColor(config.goose_color_underbody)
        beak_color    = QColor(config.goose_color_beak)

    ub_a = _pt(rig.underbody_center + fwd * 7)
    ub_b = _pt(rig.underbody_center - fwd * 7)
    bd_a = _pt(rig.body_center + fwd * 11)
    bd_b = _pt(rig.body_center - fwd * 11)
    nb   = _pt(rig.neck_base)
    nh   = _pt(rig.neck_head_point)
    h1   = _pt(rig.head1_end_point)
    h2   = _pt(rig.head2_end_point)

    # 1. Shadow
    painter.setPen(_NO_PEN)
    painter.setBrush(_SHADOW_BRUSH)
    painter.drawEllipse(QPointF(position.x, position.y), 20.0, 15.0)

    # 2. Feet
    painter.setBrush(_get_brush(beak_color))
    painter.setPen(_NO_PEN)
    painter.drawEllipse(_pt(l_foot_pos), 4.0, 4.0)
    painter.drawEllipse(_pt(r_foot_pos), 4.0, 4.0)

    # 3. Outline layer
    _set_pen(painter, outline_color, 15)
    painter.drawLine(ub_a, ub_b)
    _set_pen(painter, outline_color, 24)
    painter.drawLine(bd_a, bd_b)
    _set_pen(painter, outline_color, 15)
    painter.drawLine(nb, nh)
    _set_pen(painter, outline_color, 17)
    painter.drawLine(nh, h1)
    _set_pen(painter, outline_color, 12)
    painter.drawLine(h1, h2)

    # 4. White fill layer
    _set_pen(painter, body_color, 22)
    painter.drawLine(bd_a, bd_b)
    _set_pen(painter, body_color, 13)
    painter.drawLine(nb, nh)
    _set_pen(painter, body_color, 15)
    painter.drawLine(nh, h1)
    _set_pen(painter, body_color, 10)
    painter.drawLine(h1, h2)


def render_goose_head(painter: QPainter, rig: Rig, direction: float, config=None):
    """Beak, eyes, sleep bubbles, exclamation — drawn on top of props held in beak."""
    fwd   = Vector2.get_from_angle_degrees(direction)
    right = Vector2.get_from_angle_degrees(direction + 90.0)

    beak_color = COLOR_ORANGE
    if config and config.use_custom_colors:
        beak_color = QColor(config.goose_color_beak)

    h2       = _pt(rig.head2_end_point)
    beak_tip = _pt(rig.head2_end_point + fwd * 5)

    # 5. Beak
    _set_pen(painter, beak_color, 11)
    painter.drawLine(h2, beak_tip)

    # 6. Eyes
    b = Vector2(1.3, 0.4)
    left_eye  = rig.neck_head_point + UP * 3 - right * b.x * 3 + fwd * 5
    right_eye = rig.neck_head_point + UP * 3 + right * b.x * 3 + fwd * 5
    painter.setBrush(_BLACK_BRUSH)
    painter.setPen(_NO_PEN)
    if not rig.is_sleeping or rig.peek_eye == 3:
        painter.drawEllipse(_pt(left_eye), 2.0, 2.0)
        painter.drawEllipse(_pt(right_eye), 2.0, 2.0)
    elif rig.peek_eye == 1:
        painter.drawEllipse(_pt(left_eye), 2.0, 1.5)
    elif rig.peek_eye == 2:
        painter.drawEllipse(_pt(right_eye), 2.0, 1.5)

    # 7. Sleep bubbles
    if rig.show_sleep_bubbles:
        _render_sleep_bubbles(painter, rig)

    # 8. Exclamation mark
    if rig.show_exclamation:
        _render_exclamation(painter, rig)


def _render_sleep_bubbles(painter: QPainter, rig: Rig):
    base = rig.neck_head_point + UP * 10.0
    # 3 bubbles with staggered phases, each cycling over 3 seconds
    configs = [
        {"offset": 0.0,  "x_drift":  6.0, "max_r": 3.5},
        {"offset": 1.0,  "x_drift": 11.0, "max_r": 5.0},
        {"offset": 2.0,  "x_drift": 15.0, "max_r": 6.5},
    ]
    cycle = 3.0
    rise  = 28.0
    for cfg in configs:
        p = ((rig.sleep_phase + cfg["offset"]) % cycle) / cycle  # 0→1
        alpha = int(clamp(lerp(220, 0, max(0.0, (p - 0.5) * 2.0)), 0, 255))
        if alpha == 0:
            continue
        r   = lerp(1.5, cfg["max_r"], p)
        pos = Vector2(base.x + cfg["x_drift"], base.y - p * rise)
        color = QColor(255, 255, 255, alpha)
        outline = QColor(160, 200, 255, alpha)
        # Bubble colors vary by alpha; cache keyed on rgba keeps this bounded (<=255 entries)
        painter.setPen(_get_pen(outline, 1))
        painter.setBrush(_get_brush(color))
        painter.drawEllipse(_pt(pos), r, r)


def _render_exclamation(painter: QPainter, rig: Rig):
    base = rig.neck_head_point + UP * 22.0
    painter.setPen(_EXCLAMATION_PEN)
    painter.setBrush(_YELLOW_BRUSH)
    # Vertical bar: tall thin rounded rect
    bar = QRectF(base.x - 3.5, base.y - 14.0, 7.0, 10.0)
    painter.drawRoundedRect(bar, 2.0, 2.0)
    # Dot below
    painter.drawEllipse(QPointF(base.x, base.y), 3.5, 3.5)
