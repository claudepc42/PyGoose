from __future__ import annotations
from math import sin
import time as _time
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath, QFont, QBrush
from PyQt6.QtCore import Qt, QRectF

from pygoose.goose.props.prop import Prop, PropType, PropState, PROP_REGISTRY
from pygoose.engine.vector2 import Vector2
from pygoose.engine.rig import Rig
from pygoose.goose.renderer import update_rig, render_goose, render_goose_body, render_goose_head

_SHADOW_BRUSH = QBrush(QColor(60, 60, 60, 110), Qt.BrushStyle.Dense4Pattern)


PERSPECTIVE_SCALE = 1.0  # 1px of Z = 1px upward on screen; tune after visuals are in

# --- debug side toggle ---
_debug_side: str = "left"           # "left" or "right"
_debug_flip_rect: tuple | None = None  # (x, y, w, h) screen coords, updated each render frame

_DEBUG_LEFT_CX  = 270   # left-side: left edge of boxes at ~20px
_DEBUG_RIGHT_CX = None  # set at runtime from screen_w; see toggle_debug_side

# --- active prop variant for compass/shadow/attach tests ---
# Change this to "v1", "v2", or "v3" to switch which variant is tested everywhere
_DEBUG_ACTIVE_VARIANT: str = "v2"
_DEBUG_KNIFE_VARIANTS: dict = {
    "v1": dict(heel_gap=0, blade_len=21, handle_len=21),
    "v2": dict(heel_gap=1, blade_len=21, handle_len=21),
    "v3": dict(heel_gap=1, blade_len=28, handle_len=14),
}


def toggle_debug_side(prop: Prop, screen_w: int):
    global _debug_side
    _debug_side = "right" if _debug_side == "left" else "left"
    prop.position = Vector2(
        float(_DEBUG_LEFT_CX) if _debug_side == "left" else float(screen_w - _DEBUG_LEFT_CX),
        prop.position.y,
    )


def get_debug_flip_rect() -> tuple | None:
    return _debug_flip_rect


def render_props(painter: QPainter, props: list[Prop], debug: bool = False):
    for prop in props:
        _render_prop(painter, prop, debug)


def _render_prop(painter: QPainter, prop: Prop, debug: bool):
    screen_y = prop.position.y - (prop.surface_z + prop.z) * PERSPECTIVE_SCALE
    sx = int(prop.position.x)
    sy = int(screen_y)

    if debug:
        _render_debug_box(painter, sx, sy)
        return  # no shadow, no normal render in debug mode

    _render_shadow(painter, prop)
    painter.save()
    painter.translate(sx, sy)
    painter.rotate(prop.angle)
    fn = _RENDER_FNS.get(prop.prop_type)
    if fn:
        fn(painter, prop)
    painter.restore()


# Layout constants (relative to main box center cy):
#   Main box    : 500×280, top = cy-140, bottom = cy+140
#   Separator   : 8px gap, line at cy+144
#   Compass box : 500×500, center = cy+398, top = cy+148, bottom = cy+648
# Default spawn: cx=270, cy=screen_h-698  → compass bottom = screen_h-50 (clears taskbar)

def _render_debug_box(painter: QPainter, cx: int, cy: int):
    global _debug_flip_rect

    bw, bh = 500, 340
    bx, by = cx - bw // 2, cy - bh // 2

    # --- main prop box ---
    painter.fillRect(bx, by, bw, bh, QColor(255, 255, 255, 255))

    # --- flip button (top-center of main box) ---
    btn_w, btn_h = 80, 16
    btn_x = cx - btn_w // 2
    btn_y = by + 4
    _debug_flip_rect = (btn_x, btn_y, btn_w, btn_h)
    painter.setBrush(QColor(220, 220, 220))
    painter.setPen(QPen(QColor(160, 160, 160), 1))
    painter.drawRoundedRect(btn_x, btn_y, btn_w, btn_h, 4, 4)
    painter.setFont(QFont("Arial", 7))
    painter.setPen(QColor(40, 40, 40))
    painter.drawText(QRectF(btn_x, btn_y, btn_w, btn_h), Qt.AlignmentFlag.AlignCenter, "⇄ flip screen pos")

    # Reference geese shifted up ~quarter of box height for more prop room below
    _render_reference_goose(painter, cx + 180, cy - 70, 180.0)
    _render_reference_goose(painter, cx - 180, cy - 70, 45.0)

    # Prop variants — centered, 45px apart, labeled; orange dot marks the active variant
    knife_variants = [
        (cy - 70, "v1"),
        (cy - 25, "v2"),
        (cy + 20, "v3"),
    ]
    painter.setFont(QFont("Arial", 7))
    for row_y, label in knife_variants:
        kv = _DEBUG_KNIFE_VARIANTS[label]
        if label == _DEBUG_ACTIVE_VARIANT:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 140, 0))
            painter.drawEllipse(cx - 48, row_y - 3, 6, 6)
        painter.setPen(QColor(140, 140, 140))
        painter.drawText(QRectF(cx - 40, row_y - 5, 12, 10), Qt.AlignmentFlag.AlignLeft, label)
        painter.save()
        painter.translate(cx, row_y)
        _draw_knife_shape(painter, **kv)
        painter.restore()

    # Right side: prop with its defined attach points only (active variant)
    akv = _DEBUG_KNIFE_VARIANTS[_DEBUG_ACTIVE_VARIANT]
    attach_x = cx + 195
    attach_y = cy + 30
    painter.save()
    painter.translate(attach_x, attach_y)
    _draw_knife_shape(painter, **akv)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 20, 147))
    painter.drawEllipse(-13, -3, 6, 6)   # carry attach pt (knife only has carry)
    painter.restore()

    # Bottom-left corner: shadow previews — prop.position.y is always ground anchor, Z lifts image
    sx = bx + 70

    # Carried (beak height): Z=30 — shadow via live _render_shadow
    beak_z = 30
    beak_ground_y = cy + 55
    painter.setFont(QFont("Arial", 7))
    painter.setPen(QColor(120, 120, 120))
    painter.drawText(QRectF(bx + 4, beak_ground_y - beak_z - 45, 130, 10), Qt.AlignmentFlag.AlignLeft, "prop w/ shadow (carried)")
    _render_shadow(painter, Prop(PropType.KNIFE, Vector2(float(sx), float(beak_ground_y)), z=float(beak_z)))
    painter.save()
    painter.translate(sx, beak_ground_y - beak_z)
    _draw_knife_shape(painter, **akv)
    painter.restore()

    # Placed (ground, Z=0) — shadow via live _render_shadow
    ground_y = cy + 120
    painter.setFont(QFont("Arial", 7))
    painter.setPen(QColor(120, 120, 120))
    painter.drawText(QRectF(bx + 4, ground_y - 45, 130, 10), Qt.AlignmentFlag.AlignLeft, "prop w/ shadow (placed)")
    _render_shadow(painter, Prop(PropType.KNIFE, Vector2(float(sx), float(ground_y)), z=0.0))
    painter.save()
    painter.translate(sx, ground_y)
    _draw_knife_shape(painter, **akv)
    painter.restore()

    # Legend
    legend_y = by + bh - 12
    legend_rx = bx + bw - 8
    painter.setFont(QFont("Arial", 7))
    legend_entries = [
        (QColor(255, 20, 147), "carry attach pt"),
        (QColor(0, 200, 0),    "head attach pt"),
        (QColor(0, 100, 255),  "back attach pt"),
    ]
    for i, (color, label) in enumerate(reversed(legend_entries)):
        row_y = legend_y - i * 13
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(legend_rx - 80, row_y - 4, 6, 6)
        painter.setPen(QColor(0, 0, 0))
        painter.drawText(QRectF(legend_rx - 72, row_y - 6, 72, 12), Qt.AlignmentFlag.AlignLeft, label)

    # Active variant indicator — above the 3 attach point entries
    active_row_y = legend_y - 3 * 13 - 8
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 140, 0))
    painter.drawEllipse(legend_rx - 80, active_row_y - 4, 6, 6)
    painter.setPen(QColor(0, 0, 0))
    painter.drawText(QRectF(legend_rx - 72, active_row_y - 6, 72, 12), Qt.AlignmentFlag.AlignLeft, "currently shown")

    # Bottom-center: two live oscillating shadow previews sharing the same sine Z
    # Left = 90° (vertical orientation), Right = 0° (horizontal)
    osc_z = 15.0 + 15.0 * sin(_time.time() * 1.8)   # ~3.5s period
    osc_ground_y = cy + 148
    painter.setFont(QFont("Arial", 7))
    painter.setPen(QColor(120, 120, 120))
    painter.drawText(QRectF(cx - 60, osc_ground_y - 73, 120, 10), Qt.AlignmentFlag.AlignCenter, "live shadow (sine wave)")
    for prop_x, angle in [(cx - 35, 90.0), (cx + 35, 0.0)]:
        _render_shadow(painter, Prop(PropType.KNIFE, Vector2(float(prop_x), float(osc_ground_y)), z=osc_z, angle=angle))
        painter.save()
        painter.translate(prop_x, osc_ground_y - int(osc_z * PERSPECTIVE_SCALE))
        painter.rotate(angle)
        _draw_knife_shape(painter, **akv)
        painter.restore()

    # --- compass box (directly below main box) ---
    compass_cy = cy + 428
    _render_compass_box(painter, cx, compass_cy)


def _render_compass_box(painter: QPainter, cx: int, cy: int):
    # 8 geese arranged in a circle, each facing outward in their compass direction
    # Goose at top faces north (up=270°), right faces east (0°), etc.
    bw, bh = 500, 500
    painter.fillRect(cx - bw // 2, cy - bh // 2, bw, bh, QColor(255, 255, 255, 255))

    r = 120  # circle radius
    directions = [
        (270.0,   0, -1),   # N  — top,        facing up
        (315.0,   1, -1),   # NE — top-right,  facing upper-right
        (  0.0,   1,  0),   # E  — right,       facing right
        ( 45.0,   1,  1),   # SE — lower-right, facing lower-right
        ( 90.0,   0,  1),   # S  — bottom,      facing down
        (135.0,  -1,  1),   # SW — lower-left,  facing lower-left
        (180.0,  -1,  0),   # W  — left,        facing left
        (225.0,  -1, -1),   # NW — upper-left,  facing upper-left
    ]
    for direction, dx, dy in directions:
        gx = cx + int(dx * r / (1 if dx == 0 or dy == 0 else 1.414))
        gy = cy + int(dy * r / (1 if dx == 0 or dy == 0 else 1.414))
        pos = Vector2(float(gx), float(gy))
        rig = Rig()
        update_rig(pos, direction, rig)
        fwd = Vector2.get_from_angle_degrees(direction)
        beak_tip = rig.head2_end_point + fwd * 5.0
        knife_angle = direction + 90.0
        shadow_x = pos.x + fwd.x * 31.0
        shadow_y = pos.y + fwd.y * 25.0
        l_foot = Vector2(pos.x - 6.0, pos.y)
        r_foot = Vector2(pos.x + 6.0, pos.y)
        # prop shadow first so it sits under the goose body
        _render_shadow(painter, Prop(PropType.KNIFE, Vector2(shadow_x, shadow_y), z=30.0, angle=knife_angle))
        render_goose_body(painter, rig, pos, direction, l_foot, r_foot, None)
        _render_knife_in_beak(painter, rig, direction)
        render_goose_head(painter, rig, direction, None)


def _render_reference_goose(painter: QPainter, x: int, y: int, direction: float) -> Rig:
    pos = Vector2(float(x), float(y))
    rig = Rig()
    update_rig(pos, direction, rig)
    l_foot = Vector2(pos.x - 6.0, pos.y)
    r_foot = Vector2(pos.x + 6.0, pos.y)
    render_goose(painter, rig, pos, direction, l_foot, r_foot, None)
    return rig


def _render_knife_in_beak(painter: QPainter, rig: Rig, direction: float):
    fwd = Vector2.get_from_angle_degrees(direction)
    beak_tip = rig.head2_end_point + fwd * 5.0  # actual beak tip, not beak base
    knife_angle = direction + 90.0  # blade tip to goose's right
    painter.save()
    painter.translate(beak_tip.x, beak_tip.y)
    painter.rotate(knife_angle)
    painter.translate(10, 0)  # shift ~20% of total knife length toward blade tip
    painter.scale(1, -1)      # mirror Y so cutting edge faces away from goose body
    _draw_knife_shape(painter, **_DEBUG_KNIFE_VARIANTS[_DEBUG_ACTIVE_VARIANT])
    painter.restore()


def _render_shadow(painter: QPainter, prop: Prop):
    height = prop.surface_z + prop.z
    scale = max(0.45, 1.0 - height * 0.012)
    defn = PROP_REGISTRY.get(prop.prop_type)
    sl = defn.shadow_length if defn else 20.0
    sw = defn.shadow_width  if defn else 6.0
    so = defn.shadow_offset if defn else 0.0
    w = max(4, int(sl * scale))
    h = max(2, int(sw * scale))
    painter.save()
    painter.translate(int(prop.position.x), int(prop.position.y))
    painter.rotate(prop.angle)
    painter.setBrush(_SHADOW_BRUSH)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(int(so) - w // 2, -h // 2, w, h)
    painter.restore()


def _draw_knife_shape(painter: QPainter, heel_gap: int = 0, blade_len: int = 22, handle_len: int = 22):
    # heel_gap: px of visible silver tang between blade heel and handle
    # blade_len: length of blade portion (tip at +blade_len, heel at 0)
    # handle_len: length of handle (far end at -(heel_gap + handle_len))
    painter.setPen(Qt.PenStyle.NoPen)

    bl = blade_len
    # --- blade ---
    blade = QPainterPath()
    blade.moveTo(0, -2)
    blade.lineTo(bl - 1, -2)            # straight spine to near tip
    blade.quadTo(bl + 1, 1, bl - 6, 4) # tip curves on cutting edge side — elongated
    blade.lineTo(0, 4)                  # cutting edge to heel
    blade.lineTo(0, 2)                  # 90-degree corner
    blade.quadTo(1, 0, 0, -2)          # curve back up to tang width
    painter.setBrush(QColor(200, 200, 210))
    painter.drawPath(blade)

    # --- visible tang ---
    if heel_gap > 0:
        painter.setBrush(QColor(200, 200, 210))
        painter.drawRect(-heel_gap, -2, heel_gap, 3)  # top flush with spine (y=-2)

    # --- handle ---
    painter.setBrush(QColor(210, 180, 130))
    painter.drawRoundedRect(-(heel_gap + handle_len), -3, handle_len, 6, 3, 3)


def _render_knife(painter: QPainter, prop: Prop):
    painter.scale(1, -1)
    _draw_knife_shape(painter)


_RENDER_FNS: dict[PropType, object] = {
    PropType.KNIFE: _render_knife,
}


def _register_prop_defs():
    from pygoose.goose.props.prop import PropDef
    PROP_REGISTRY[PropType.KNIFE] = PropDef(
        render_fn=_render_knife,
        collision_radius=18.0,
        mass=0.5,
        friction=0.4,
        shadow_length=43.0,   # blade(21) + heel_gap(1) + handle(21)
        shadow_width=6.0,
        shadow_offset=-0.5,   # center of knife span from local origin
        pickup_offset=-11.0,  # handle center: 11px negative along prop.angle from heel origin
    )


_register_prop_defs()
