# PyGoose — Product Requirements Document
**Version:** 0.33
**Status:** Active Development
**Source:** Reverse-engineered from decompiled Desktop Goose v0.31 (arkangel-dev/desktop-goose-source) + original PyGoose implementation

---

## 1. Project Overview

PyGoose is a cross-platform, open-source reimplementation of samperson's Desktop Goose. It places a procedurally-animated goose on top of all windows on the user's desktop. The goose wanders autonomously, steals the cursor, tracks mud, and drags fake windows onto the screen. It supports user-customizable memes, notepad messages, and a plugin-based modding API.

The original is closed-source, Windows-only, and unmaintained. This project recreates full feature parity and adds cross-platform support and a cleaner mod API.

---

## 2. Target Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| Windows 10/11 | Required | Primary target. Click-through overlay via Qt |
| macOS 12+ | Required | Requires Accessibility permission prompt on first launch |
| Linux (X11) | Required | Wayland unsupported by design; show error if Wayland detected with no XWayland |

**Linux Wayland note:** Display an error dialog on startup if `WAYLAND_DISPLAY` is set and `DISPLAY` is not. Do not silently fail.

---

## 3. Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.11+ | Cross-platform, readable, easy modding |
| GUI / overlay | PyQt6 | Native transparent always-on-top windows, Qt painter for drawing |
| Cursor control | `pyautogui` + platform ctypes | Cross-platform cursor position/move |
| Sound | `pygame.mixer` | Cross-platform MP3/WAV, simple API |
| Config | INI via `configparser` | Match original format, user-editable |
| Packaging | PyInstaller | Single-folder distribution per platform |
| Mod API | Python `importlib` plugins | Drop-in `.py` files, cleaner than DLL injection |

---

## 4. Repository Structure

```
pygoose/
├── main.py                        # Entry point
├── config.ini                     # User configuration file
├── goose/
│   ├── __init__.py
│   ├── game.py                    # Main game loop (Init, Update, Render)
│   ├── goose.py                   # TheGoose: state machine, physics, rendering
│   ├── renderer.py                # Pure drawing functions (update_rig, render_goose, etc.)
│   ├── config.py                  # GooseConfig: load/save config.ini
│   ├── sound.py                   # Sound: honk, chomp, pat, mud squish
│   ├── overlay.py                 # Transparent always-on-top Qt window
│   ├── cursor.py                  # Platform cursor clip/release/query helpers
│   ├── mod_loader.py              # Plugin discovery and loading
│   └── windows/
│       ├── __init__.py
│       ├── notepad_window.py      # SimpleTextForm equivalent
│       ├── meme_window.py         # SimpleImageForm equivalent
│       └── movable_window.py      # Base movable/resizable window
├── engine/
│   ├── __init__.py
│   ├── vector2.py                 # Vector2 math class
│   ├── math_utils.py              # lerp, clamp, random_range
│   ├── easings.py                 # All easing functions
│   ├── deck.py                    # Shuffle-deck random selector
│   ├── rig.py                     # Rig dataclass: all joint positions + animation state
│   └── time_keeper.py             # Frame timer, delta time, elapsed time
├── assets/
│   ├── fonts/                     # .ttf/.otf handwriting fonts for notepad
│   ├── sounds/
│   │   ├── Honk1.mp3
│   │   ├── Honk2.mp3
│   │   ├── Honk3.mp3
│   │   ├── Honk4.mp3
│   │   ├── BITE.mp3
│   │   ├── MudSquish.mp3
│   │   ├── Music.mp3              # Optional background music
│   │   ├── Pat1.wav
│   │   ├── Pat2.wav
│   │   └── Pat3.wav
│   ├── images/
│   │   └── memes/                 # User drops meme images/GIFs here
│   └── text/
│       └── notepad_messages/      # User drops .txt files here
└── mods/                          # User mod folders go here
    └── example_mod/
        ├── mod.py
        └── README.md
```

---

## 5. Engine Layer (`engine/`)

### 5.1 `vector2.py` — Vector2

Exact port of the original `SamEngine.Vector2` struct. All operations must match precisely since the rig math depends on them.

```python
class Vector2:
    x: float
    y: float
    zero = Vector2(0.0, 0.0)

    # Operators: +, -, unary -, * (vec*vec), * (vec*float), / (vec/float)
    # Static methods:
    @staticmethod
    def get_from_angle_degrees(angle: float) -> Vector2:
        # angle * 0.0174532924  (deg2rad constant)
        return Vector2(cos(angle * 0.0174532924), sin(angle * 0.0174532924))

    @staticmethod
    def distance(a, b) -> float: ...

    @staticmethod
    def lerp(a, b, p) -> Vector2: ...

    @staticmethod
    def dot(a, b) -> float: ...

    @staticmethod
    def normalize(a) -> Vector2:
        # Guard: if x==0 and y==0, return Vector2.zero

    @staticmethod
    def magnitude(a) -> float: ...
```

### 5.2 `math_utils.py` — SamMath

```python
DEG2RAD = 0.0174532924
RAD2DEG = 57.2957764

def random_range(min: float, max: float) -> float:
    return min + random.random() * (max - min)

def lerp(a: float, b: float, p: float) -> float:
    return a * (1.0 - p) + b * p

def clamp(a: float, min_val: float, max_val: float) -> float:
    return min(max(a, min_val), max_val)
```

Single shared `random.Random()` instance throughout the app.

### 5.3 `easings.py` — Easing Functions

Implement all of the following exactly as in the original `Easings.cs`. Only `CubicEaseInOut` and `ExponentialEaseOut` are used by the goose, but implement the full set for mod authors.

Used by goose code:
- `cubic_ease_in_out(p)` — foot movement animation
- `exponential_ease_out(p)` — ESC quit progress bar

Full list to implement:
`linear`, `quadratic_ease_in/out/in_out`, `cubic_ease_in/out/in_out`,
`quartic_ease_in/out/in_out`, `quintic_ease_in/out/in_out`,
`sine_ease_in/out/in_out`, `circular_ease_in/out/in_out`,
`exponential_ease_in/out/in_out`, `elastic_ease_in/out/in_out`,
`back_ease_in/out/in_out`, `bounce_ease_in/out/in_out`

### 5.4 `deck.py` — Shuffle Deck

Fisher-Yates shuffle-on-exhaust deck. Exact behavior match is required because the task weighting depends on it.

```python
class Deck:
    def __init__(self, length: int):
        self.indices = list(range(length))
        self._i = 0
        self.reshuffle()

    def reshuffle(self):
        # Fisher-Yates: for i in range(length): swap indices[i] with indices[randint(0, i)]
        # NOTE: original uses random_range(0, i) which can return i itself — preserve this

    def next(self) -> int:
        result = self.indices[self._i]
        self._i += 1
        if self._i >= len(self.indices):
            self.reshuffle()
            self._i = 0
        return result
```

### 5.5 `time_keeper.py` — Time

```python
TARGET_FRAMERATE = 120          # Hz
DELTA_TIME = 1.0 / 120.0       # 0.008333334 seconds — FIXED, not measured

# time: float — seconds since app start, updated once per frame via time.perf_counter()
# delta_time is ALWAYS 0.008333334 regardless of actual frame timing
# This matches original exactly — the original uses a fixed delta
```

Delta time is always the fixed constant, not the measured frame time. This is how the original works and affects all physics values. The simulation runs at 120 Hz (two fixed steps per 16 ms timer wake), while rendering runs at 60 Hz with dirty-rect partial repaints — see §7.4 for the actual loop. `TimeKeeper.sleep_remainder()` is retained for reference but unused; pacing comes from the `QTimer` interval.

---

## 6. Configuration (`config.py` + `config.ini`)

### 6.1 `config.ini` format

```ini
[Goose]
Version=1
EnableMods=False
SilenceSounds=False
Task_CanAttackMouse=True
AttackRandomly=False
UseCustomColors=False
GooseColorBody=#ffffff
GooseColorUnderbody=#d3d3d3
GooseColorBeak=#ffa500
MinWanderingTimeSeconds=20
MaxWanderingTimeSeconds=40
FirstWanderTimeSeconds=20
NotepadFontSize=25
```

`Version` is a schema version integer. If the loaded version doesn't match the current app version, delete and regenerate with defaults. Show a messagebox warning the user.

### 6.2 `GooseConfig` class

```python
@dataclass
class GooseConfig:
    version: int = 1
    enable_mods: bool = False
    silence_sounds: bool = False
    task_can_attack_mouse: bool = True
    attack_randomly: bool = False
    use_custom_colors: bool = False
    goose_color_body: str = "#ffffff"
    goose_color_underbody: str = "#d3d3d3"
    goose_color_beak: str = "#ffa500"
    min_wandering_time_seconds: float = 20.0
    max_wandering_time_seconds: float = 40.0
    first_wander_time_seconds: float = 20.0
    notepad_font_size: int = 25
```

If `config.ini` does not exist, create it silently with defaults (no messagebox). If config fails to parse, show messagebox, delete corrupt file, recreate with defaults.

---

## 7. Overlay Window (`overlay.py`)

The overlay is a single frameless, transparent, always-on-top, click-through window covering the entire primary monitor.

### 7.1 Qt window flags (all platforms)

```python
flags = (
    Qt.WindowType.FramelessWindowHint |
    Qt.WindowType.WindowStaysOnTopHint |
    Qt.WindowType.Tool |              # hides from taskbar
    Qt.WindowType.NoDropShadowWindowHint
)
setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)  # click-through
```

### 7.2 Platform-specific click-through

**Windows:** Additionally call `SetWindowLong` with `WS_EX_LAYERED | WS_EX_TRANSPARENT` via ctypes after the window is shown. This is required — Qt's `WA_TransparentForMouseEvents` alone is insufficient on Windows for all click-through scenarios.

```python
import ctypes
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020

hwnd = int(window.winId())
style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)
```

**macOS:** `WA_TransparentForMouseEvents` alone is insufficient. After `show()`, call `setIgnoresMouseEvents_(True)` on each NSWindow via PyObjC (`AppKit.NSApp.windows()`). This is required for reliable click-through on macOS. Accessibility permission is also required for cursor manipulation — detect via `Quartz.AXIsProcessTrusted()` and prompt on startup if not granted.

**Linux/X11:** `WA_TransparentForMouseEvents` is sufficient. No extra steps.

### 7.3 Window sizing

Cover `QScreen.primaryScreen().geometry()` exactly. Do not use `availableGeometry()` (that excludes taskbar). The goose should be able to walk behind/under the taskbar visually — the taskbar will cover it naturally since it's a separate OS window.

### 7.4 Render loop

The loop is driven by a single `QTimer` and is decoupled into a **120 Hz simulation** and a **60 Hz render** to cut CPU without changing motion or appearance:

```
- QTimer with interval=16 (~60 wakeups/sec)
- Each wake (_tick in overlay.py):
    - on_tick() called TWICE (two fixed 1/120 s physics steps → 120 Hz sim preserved)
    - _update_quit() called twice (ESC-hold alpha advances at sim rate)
    - schedule a partial repaint over the dirty rect (see below), not the whole screen
- paintEvent(): game.render(painter) — only the invalidated region is repainted
```

Physics still advances with the fixed `DELTA_TIME = 1/120` constant (two steps per wake), so all motion values are identical to a true 120 Hz loop. Only the *render* cadence dropped to 60 Hz, which is imperceptible for this content.

**Dirty-rect repainting:** `Goose.dirty_rect()` returns the bounding box of the goose plus any footmarks currently mid-shrink. `overlay._tick()` unions the current rect with the previous frame's rect (to erase the trail) and calls `self.update(region)` instead of a full-screen `self.update()`. When the ESC quit bar is visible, its rect is unioned in as well. The box extents (`DIRTY_LEFT/RIGHT/UP/DOWN` in `goose.py`) are sized to contain every drawn pixel across all states; measured worst-case extents are L≈50 R≈51 U≈96 D≈37 px from the goose position (the up-extent is driven by sleep bubbles). Note: shrinking the box below those generous values yields **no** measurable CPU saving, because Qt re-blits the whole translucent layered window per update regardless of the invalidated region — so the lever is *update frequency*, not region area.

**Identical-frame skipping (the main idle-CPU win):** `Goose.dirty_rect()` returns `None` when nothing that affects drawn pixels has changed since the last painted frame, and `overlay._tick()` then skips the repaint entirely (the layered window already holds identical pixels). The decision compares an exact, un-quantized signature of *every* render input — position, direction, both feet, the three rig lerps, `is_sleeping`/`show_sleep_bubbles`/`peek_eye`/`show_exclamation`, `sleep_phase` (only while bubbles are shown), and whether any footmark is mid-shrink. Because the comparison is bitwise, a skipped frame is provably identical, so this can never change what the user sees. During static behaviours (sit, fake-sleep, stand-still) this drops the goose from ~10% of one core to ~2%. The ESC quit bar animates independently, so the overlay still repaints its region while `_quit_alpha` is non-zero even when the goose is skipping.

**Cached paint objects:** `renderer.py` builds each `QPen`/`QBrush` once (keyed by colour+width) and hoists Qt enum values (`NoPen`, `RoundCap`, `RoundJoin`, …) to module constants, instead of constructing pens and re-looking-up enums on every one of the ~15 draw calls per frame. Line endpoints shared between the outline and fill passes are computed once. These are pure-overhead removals with identical output and cut the Python render cost ~20%.

`TimeKeeper.sleep_remainder()` exists for a sleep-based loop but is **not** used — the `QTimer` interval provides pacing instead, letting the Qt event loop idle between wakes.

Use `QPainter` with `RenderHint.Antialiasing` enabled.

---

## 8. Goose Rendering — The Rig

The goose is **100% procedurally drawn** using lines and ellipses. There are no sprite images. All shapes use round line caps.

### 8.1 Rig dataclass (`engine/rig.py`)

```python
@dataclass
class Rig:
    # Animation lerp values (0.0=relaxed/standing, 1.0=extended/crouched)
    neck_lerp_percent: float = 0.0       # 0.0=relaxed, 1.0=extended/running
    sit_lerp_percent: float = 0.0        # 0.0=standing, 1.0=fully crouched/sitting
    neck_tuck_lerp_percent: float = 0.0  # 0.0=normal neck, 1.0=head tucked down (crawl)

    # Pose flags
    is_sleeping: bool = False            # True only during SleepStage.SLEEPING
    show_sleep_bubbles: bool = False     # True only during real (non-fake) sleep
    peek_eye: int = 0                    # 0=no eyes, 1=left eye only, 2=right eye only, 3=both eyes
    show_exclamation: bool = False       # True during fake-sleep freak-out phase 2

    # Sleep bubble animation phase (accumulates DELTA_TIME while sleeping)
    sleep_phase: float = 0.0

    # Joint positions (updated each frame by update_rig)
    underbody_center: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    body_center: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    neck_center: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    neck_base: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    neck_head_point: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    head1_end_point: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    head2_end_point: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
```

### 8.2 `update_rig(position, direction, rig)` — exact math

`sit_lerp_percent` and `neck_tuck_lerp_percent` from the Rig are factored in:

```python
UP = Vector2(0.0, -1.0)
fwd = Vector2.get_from_angle_degrees(direction)
s = rig.sit_lerp_percent
tuck = rig.neck_tuck_lerp_percent

# Body lowers when sitting/crouching
rig.underbody_center = position + UP * lerp(9.0, 1.0, s)
rig.body_center      = position + UP * lerp(14.0, 4.0, s)

# Neck height and forward offset interpolate with both lerps
neck_height  = int(lerp(lerp(20.0, 10.0, rig.neck_lerp_percent), 6.0,  tuck))
neck_forward = int(lerp(lerp(3.0,  16.0, rig.neck_lerp_percent), 2.0,  tuck))

rig.neck_center     = position + UP * (14 + neck_height)
rig.neck_base       = rig.body_center + fwd * 15.0
rig.neck_head_point = rig.neck_base + fwd * neck_forward + UP * neck_height

rig.head1_end_point = rig.neck_head_point + fwd * 3.0 - UP * 1.0
rig.head2_end_point = rig.head1_end_point + fwd * 5.0
```

### 8.3 `render_goose(painter, rig, position, direction, l_foot_pos, r_foot_pos, config)` — draw order and exact sizes

Draw order (back to front):

1. **Shadow** — hatched dark gray ellipse under body: center=(pos.x, pos.y), radii=(20, 15). Use `Qt.BrushStyle.Dense4Pattern` at color `QColor(80, 80, 80, 80)`. Drawn with `fillEllipse`.
2. **Feet** — two filled orange circles, radius=4, at `l_foot_pos` and `r_foot_pos`. Color matches `beak_color`.
3. **Outline layer** (LightGray, drawn first so white overwrites):
   - Underbody line: LightGray, width=15, from `underbody_center + fwd*7` to `underbody_center - fwd*7`
   - Body line: LightGray, width=24, from `body_center + fwd*11` to `body_center - fwd*11`
   - Neck line: LightGray, width=15, from `neck_base` to `neck_head_point`
   - Head1 line: LightGray, width=17, from `neck_head_point` to `head1_end_point`
   - Head2 line: LightGray, width=12, from `head1_end_point` to `head2_end_point`
4. **White fill layer** (overwrites outline):
   - Body line: White, width=22
   - Neck line: White, width=13
   - Head1 line: White, width=15
   - Head2 line: White, width=10
5. **Beak** — Orange, width=11, from `head2_end_point` to `head2_end_point + fwd*5`
6. **Eyes** — controlled by `rig.peek_eye` and `rig.is_sleeping`:
   - `left_eye  = neck_head_point + UP*3 - right*b.x*3 + fwd*5`  where `b = Vector2(1.3, 0.4)`
   - `right_eye = neck_head_point + UP*3 + right*b.x*3 + fwd*5`
   - Both eyes drawn if `not rig.is_sleeping or rig.peek_eye == 3`
   - Left eye only if `rig.peek_eye == 1`
   - Right eye only if `rig.peek_eye == 2`
   - No eyes if `rig.is_sleeping` and `rig.peek_eye == 0`
7. **Sleep bubbles** — drawn if `rig.show_sleep_bubbles` (see §8.4)
8. **Exclamation mark** — drawn if `rig.show_exclamation` (see §8.5)

All lines use `Qt.PenCapStyle.RoundCap` and `Qt.PenJoinStyle.RoundJoin`.

**Custom colors:** When `UseCustomColors=True`, replace body color with `GooseColorBody`, outline color with `GooseColorUnderbody`, and beak/feet color with `GooseColorBeak`.

**Foot marks** are rendered separately via `render_foot_marks()` before `render_goose()` is called (see §10.3).

### 8.4 Sleep bubbles (`_render_sleep_bubbles`)

Three animated "z" bubbles float upward from above the head. Each has a staggered phase offset.

```python
base = rig.neck_head_point + UP * 10.0
configs = [
    {"offset": 0.0, "x_drift":  6.0, "max_r": 3.5},
    {"offset": 1.0, "x_drift": 11.0, "max_r": 5.0},
    {"offset": 2.0, "x_drift": 15.0, "max_r": 6.5},
]
cycle = 3.0   # seconds per bubble cycle
rise  = 28.0  # px of upward travel

for cfg in configs:
    p = ((rig.sleep_phase + cfg["offset"]) % cycle) / cycle   # 0→1
    # Fade out in second half of cycle
    alpha = int(clamp(lerp(220, 0, max(0.0, (p - 0.5) * 2.0)), 0, 255))
    r   = lerp(1.5, cfg["max_r"], p)
    pos = Vector2(base.x + cfg["x_drift"], base.y - p * rise)
    color   = QColor(255, 255, 255, alpha)
    outline = QColor(160, 200, 255, alpha)
```

### 8.5 Exclamation mark (`_render_exclamation`)

Yellow anime-style "!" drawn above the head during fake-sleep freak-out phase 2.

```python
base = rig.neck_head_point + UP * 22.0
# Vertical bar: tall thin rounded rect
bar = QRectF(base.x - 3.5, base.y - 14.0, 7.0, 10.0)
painter.drawRoundedRect(bar, 2.0, 2.0)    # yellow fill, black outline (width=1.5)
# Dot below
painter.drawEllipse(QPointF(base.x, base.y), 3.5, 3.5)

COLOR_YELLOW = QColor(0xFF, 0xE0, 0x00)
```

### 8.6 Neck lerp behavior

```python
# Each frame (in tick()):
target_neck = 1.0 if (override_extend_neck or current_speed >= 200.0) else 0.0
rig.neck_lerp_percent = lerp(rig.neck_lerp_percent, target_neck, 0.075)

# sit_lerp_percent and neck_tuck_lerp_percent are lerped toward _target_sit_lerp
# and _target_neck_tuck at rate 0.06 per frame:
rig.sit_lerp_percent       = lerp(rig.sit_lerp_percent,       _target_sit_lerp,  0.06)
rig.neck_tuck_lerp_percent = lerp(rig.neck_tuck_lerp_percent, _target_neck_tuck, 0.06)
```

`override_extend_neck` is set to `True` during `CollectWindow.DraggingWindowBack` task and during `SNEAK_ATTACK.POUNCING`/`DRAGGING` stages.

---

## 9. Goose Physics and Movement

### 9.1 Speed tiers

```python
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
```

`SNEAK` is used during fake-sleep post-freak-out peek behavior, sneak attack approach, and sleep circling. Slow speed (28px/s), wide step timing (0.45s), produces a careful creeping walk.

### 9.2 Physics update (called every frame, `DELTA_TIME = 0.008333334`)

```python
# 1. Compute target_direction (normalized vector toward target_pos)
to_target = Vector2.normalize(target_pos - position)

# 2. Run AI (updates target_pos, may set override_extend_neck, _freeze_position)
run_ai()

# 3. Freak-out override (see §9.4) — overrides target_pos and speed if active

# 4. Turn toward target (lerp angle, 25% per frame)
current_dir_vec = Vector2.get_from_angle_degrees(direction)
blended = Vector2.lerp(current_dir_vec, to_target, 0.25)
direction = degrees(atan2(blended.y, blended.x))

# 5. If _freeze_position: zero velocity, return early
if _freeze_position:
    velocity = Vector2.zero
    return

# 6. Cap velocity to current_speed
if Vector2.magnitude(velocity) > current_speed:
    velocity = Vector2.normalize(velocity) * current_speed

# 7. Accelerate toward target
velocity += Vector2.normalize(target_pos - position) * current_acceleration * DELTA_TIME

# 8. Integrate position
position += velocity * DELTA_TIME
```

### 9.3 `_freeze_position` flag

When `_freeze_position = True`, the physics integration step is skipped (velocity zeroed, position unchanged). The direction lerp still runs so the goose can face its target while standing still. Tasks use this flag to hold the goose in place during e.g. watching, sleeping, or sweeping.

### 9.4 Freak-out override

When the goose is caught fake-sleeping, it transitions to a 4-second freak-out before returning. This is implemented as a physics-layer override that runs in `_run_physics` after the AI dispatcher, so it takes full control regardless of the current task.

```python
# Two bounce points 400px away from the goose (in the direction away from mouse),
# offset ±70px perpendicular:
away = Vector2.normalize(position - mouse_pos)
perp = Vector2(-away.y, away.x)
off_base = position + away * 400.0
_freak_bounce_a = off_base + perp * 70.0
_freak_bounce_b = off_base - perp * 70.0

# Each frame while freak-out is active:
if _freak_out_until > 0 and t < _freak_out_until:
    bounce_target = _freak_bounce_a if _freak_bounce_to_a else _freak_bounce_b
    target_pos = bounce_target
    if distance(position, bounce_target) < 30.0:
        _freak_bounce_to_a = not _freak_bounce_to_a    # toggle target
    _set_speed(SpeedTier.CHARGE)
    _freeze_position = False
    if t >= _freak_out_next_honk:
        sound.honk()
        _freak_out_next_honk = t + 0.3    # honk every 0.3 seconds

# When freak-out expires:
elif _freak_out_until > 0:
    _freak_out_until = -1.0
    _set_task(Task.PEEK_BACK, honk=False)
```

### 9.5 Petting detection

```python
# In tick(), before running AI:
mouse_down = is_left_mouse_down()
if mouse_down and not last_frame_mouse_button_pressed:
    cursor_pos = QCursor.pos()
    goose_head = Vector2(position.x, position.y + 14.0)
    if distance(goose_head, cursor_pos) < 30.0:
        if current_task == Task.SLEEP and task_sleep.stage == SleepStage.SLEEPING:
            # Clicking sleeping goose wakes it with a honk
            sound.honk()
            set_task(Task.WANDER)
        elif current_task == Task.WATCH_MOUSE and sub_state == WatchSubState.SIT:
            r = random()
            if r < 0.70:   sound.honk()
            elif r < 0.90: set_task(Task.WANDER)
            else:           set_task(Task.NAB_MOUSE)
        else:
            set_task(Task.NAB_MOUSE)
last_frame_mouse_button_pressed = mouse_down
```

---

## 10. Footmarks

### 10.1 Ring buffer

```python
FOOT_MARK_BUFFER_SIZE = 64

@dataclass
class FootMark:
    position: Vector2 = Vector2.zero
    time: float = 0.0             # timestamp when mark was placed

foot_marks: list[FootMark] = [FootMark() for _ in range(64)]
foot_mark_index: int = 0          # wraps around
```

### 10.2 Placement

A footmark is placed whenever a foot completes a step AND `time.time < track_mud_end_time`.

```python
def add_foot_mark(pos: Vector2):
    foot_marks[foot_mark_index].time = time.time
    foot_marks[foot_mark_index].position = pos
    foot_mark_index = (foot_mark_index + 1) % FOOT_MARK_BUFFER_SIZE
```

### 10.3 Rendering

```python
FOOT_MARK_LIFETIME = 8.5    # seconds before shrink begins
FOOT_MARK_SHRINK_TIME = 1.0 # seconds to shrink from radius 3 to 0

for mark in foot_marks:
    if mark.time == 0.0:
        continue
    shrink_start = mark.time + FOOT_MARK_LIFETIME
    p = clamp((time.time - shrink_start) / FOOT_MARK_SHRINK_TIME, 0.0, 1.0)
    radius = lerp(3.0, 0.0, p)
    if radius > 0:
        painter.drawEllipse(center=mark.position, radius=radius, color=SaddleBrown)
```

---

## 11. Foot Solver

Feet are solved using a two-foot IK system that alternates steps.

### 11.1 Foot home position

The foot home adapts to the crawl/sit pose via `rig.sit_lerp_percent`:

```python
FEET_DISTANCE_APART = 6.0
OVERSHOOT_FRACTION = 0.4
WANT_STEP_AT_DISTANCE = 5.0

def get_foot_home(right_foot: bool) -> Vector2:
    s = rig.sit_lerp_percent
    b = 1.0 if right_foot else 0.0
    side = Vector2.get_from_angle_degrees(direction + 90.0) * b
    # When crawling: reduce perpendicular spread and push feet downward
    perp_dist  = lerp(FEET_DISTANCE_APART, 2.0, s)
    crawl_drop = lerp(0.0, 8.0, s)
    return position + side * perp_dist + Vector2(0.0, crawl_drop)
```

### 11.2 Step logic (called every frame)

Only one foot moves at a time. Steps alternate: when neither foot is moving, check left foot first.

```python
if l_foot_move_time_start < 0 and r_foot_move_time_start < 0:
    # Check if left foot needs to step
    if distance(l_foot_pos, get_foot_home(False)) > WANT_STEP_AT_DISTANCE:
        l_foot_move_origin = l_foot_pos
        l_foot_move_dir = normalize(get_foot_home(False) - l_foot_pos)
        l_foot_move_time_start = time.time
    # Else check right foot
    elif distance(r_foot_pos, get_foot_home(True)) > WANT_STEP_AT_DISTANCE:
        r_foot_move_origin = r_foot_pos
        r_foot_move_dir = normalize(get_foot_home(True) - r_foot_pos)
        r_foot_move_time_start = time.time

elif l_foot_move_time_start > 0:
    target = get_foot_home(False) + l_foot_move_dir * OVERSHOOT_FRACTION * 5.0
    elapsed = time.time - l_foot_move_time_start
    if elapsed <= step_time:
        p = elapsed / step_time
        l_foot_pos = Vector2.lerp(l_foot_move_origin, target, cubic_ease_in_out(p))
    else:
        l_foot_pos = target
        l_foot_move_time_start = -1.0
        sound.play_pat()
        if time.time < track_mud_end_time:
            add_foot_mark(l_foot_pos)

elif r_foot_move_time_start > 0:
    # (same as left)
```

`step_time` comes from the current speed tier (0.45 for Sneak, 0.2 for Walk/Run, 0.1 for Charge).

---

## 12. Task System

### 12.1 Task enum

```python
class Task(Enum):
    WANDER                  = "wander"
    NAB_MOUSE               = "nab_mouse"
    COLLECT_WINDOW_MEME     = "collect_window_meme"
    COLLECT_WINDOW_NOTEPAD  = "collect_window_notepad"
    COLLECT_WINDOW_EXEC     = "collect_window_exec"   # internal, not picked directly
    TRACK_MUD               = "track_mud"
    WATCH_MOUSE             = "watch_mouse"
    FOLLOW_MOUSE            = "follow_mouse"
    SNEAK_ATTACK            = "sneak_attack"
    SLEEP                   = "sleep"
    PEEK_BACK               = "peek_back"             # internal, triggered by fake-sleep freak-out
```

**PEEK_BACK** is never picked from the weighted list — it is only triggered automatically at the end of a fake-sleep freak-out sequence.

### 12.2 Weighted task list and deck

```python
TASK_WEIGHTED_LIST = [
    Task.TRACK_MUD,                 # 2/16
    Task.TRACK_MUD,
    Task.COLLECT_WINDOW_MEME,       # 2/16
    Task.COLLECT_WINDOW_MEME,
    Task.COLLECT_WINDOW_NOTEPAD,    # 3/16
    Task.COLLECT_WINDOW_NOTEPAD,
    Task.COLLECT_WINDOW_NOTEPAD,
    Task.NAB_MOUSE,                 # 3/16
    Task.NAB_MOUSE,
    Task.NAB_MOUSE,
    Task.WATCH_MOUSE,               # 2/16
    Task.WATCH_MOUSE,
    Task.FOLLOW_MOUSE,              # 2/16
    Task.FOLLOW_MOUSE,
    Task.SNEAK_ATTACK,              # 1/16
    Task.SLEEP,                     # 1/16
]
# 16 entries total

task_picker_deck = Deck(len(TASK_WEIGHTED_LIST))
```

### 12.3 `choose_next_task()`

```python
def choose_next_task():
    if DEV_FORCE_TASK:
        set_task(Task(DEV_FORCE_TASK))
        return

    task = TASK_WEIGHTED_LIST[task_picker_deck.next()]

    # Skip any unimplemented tasks (fall back to wander)
    if task not in implemented_tasks:
        task = Task.WANDER

    # If AttackRandomly=False, skip NabMouse picks
    if not config.attack_randomly and task == Task.NAB_MOUSE:
        task = Task.WANDER

    set_task(task)
```

### 12.4 `_set_task(task, honk=True)` — common reset

Every task transition resets these Rig fields and flags:

```python
override_extend_neck = False
_target_sit_lerp = 0.0
_target_neck_tuck = 0.0
_freeze_position = False
rig.is_sleeping = False
rig.show_sleep_bubbles = False
rig.peek_eye = 0
rig.show_exclamation = False
rig.sleep_phase = 0.0
current_task = task
if honk:
    sound.honk()
# Then initialize task-specific state...
```

---

### 12.5 Behavior Module System

All behavior logic lives in `pygoose/goose/behaviors/`. Each behavior is a self-contained module — one file per behavior — containing its `State` dataclass, optional `Stage` enum, constants, and two functions: `enter(goose)` and `tick(goose)`.

`goose.py` holds two dispatch dicts:

```python
_BEHAVIOR_ENTER: dict[Task, Callable] = { Task.WANDER: wander.enter, ... }
_BEHAVIOR_TICK:  dict[Task, Callable] = { Task.WANDER: wander.tick,  ... }
```

`_set_task` calls `_BEHAVIOR_ENTER[task](self)`, and the main `tick()` calls `_BEHAVIOR_TICK[self.current_task](self)` every frame. Per-behavior state is stored in `goose.task_state` (typed `object`), cast inside the behavior file.

**Circular import pattern:** behavior files use `TYPE_CHECKING` guards for type hints and defer all runtime imports from `goose.py` inside function bodies:

```python
if TYPE_CHECKING:
    from pygoose.goose.goose import Goose

def tick(goose: Goose) -> None:
    from pygoose.goose.goose import SpeedTier, SPEEDS  # deferred runtime import
    ...
```

#### 12.5.1 Override slot pattern

Behaviors communicate with core systems through designated **override slots** — plain attributes on `Goose` or `Rig` that the behavior writes and core methods read, without branching on behavior identity. This keeps core methods generic and behavior logic contained.

**Rules:**
- Behaviors write to override slots; core reads them blindly — no `if waddling:` or `if self.current_task == X:` in core methods
- All override slots are reset to their neutral values in `_set_task` so they never bleed into the next behavior
- To add a new override slot: add a neutral-default attribute to `Goose.__init__`, reset it in `_set_task`, read it generically in the relevant core method

**Existing override slots:**

| Slot | Lives on | Neutral | Used by | Read by |
|------|----------|---------|---------|---------|
| *(none currently assigned)* | | | | |

This table fills in as behaviors adopt the pattern. Add a row here whenever a new slot is introduced.

**Adding a behavior-specific step distance** (example):

```python
# goose.py __init__
self.step_distance_override: float = 0.0  # 0 = use default

# goose.py _set_task reset block
self.step_distance_override = 0.0

# goose.py _solve_feet (reads blindly — no behavior check)
threshold = self.step_distance_override or WANT_STEP_AT_DISTANCE

# wander.py (behavior sets it)
goose.step_distance_override = 12.0
```

**What NOT to do:**
- Do not modify `_solve_feet` logic for a specific behavior
- Do not add `if waddling:` / behavior identity checks to any core method
- Do not add override slots without resetting them in `_set_task`

---

## 12.6 Prop System

Props are physical objects the goose carries in, leaves on the desk, and interacts with. The system is designed around a registry pattern — adding a new prop type means writing a render function and one registry entry, nothing else.

### 12.6.1 World space and Z

PyGoose uses a loose isometric-style 2D view from slightly above:
- **Screen up = away from viewer** (goose walking toward top is walking into the distance)
- **Screen down = toward viewer**
- **Prop Z = height off the desk floor toward the viewer** — a separate axis, not the same as screen-up/away

The shadow resolves the visual ambiguity: `screen_y = ground_y - z * perspective_scale`. Shadow stays pinned at `prop.position` (ground). The gap between shadow and object reads as height.

`perspective_scale` is tuned after rendering is in — start at 1.0.

### 12.6.2 PropState

| State | Description |
|-------|-------------|
| `CARRIED` | Attached to beak, position driven by rig each frame |
| `WORN` | Attached to a rig point (e.g. hat on head), moves with it, click-transparent |
| `FALLING` | Z decreasing under gravity, shadow pinned at ground |
| `TIPPING` | Pre-fall wobble for heavy props — spring oscillator rocks prop before committing to FALLING. Gives user anticipation. Only props with `can_tip=True`. |
| `CLATTERING` | Hit ground, skidding/tumbling with friction before settling |
| `BOUNCING` | Elastic Z bounce, loses height each hit, eventually settles |
| `RISING` | Balloon released, Z increasing, drifts off top of screen |
| `PLACED` | Static at rest on surface |
| `ACTIVE` | Functional animation running (fan spinning, etc.) |
| `BROKEN` | Destroyed form, static remains |

### 12.6.3 Prop dataclass (per-instance, mutable)

```python
@dataclass
class Prop:
    prop_type: PropType
    position: Vector2        # ground position — where shadow sits
    z: float = 0.0           # height above surface (0 = resting on surface)
    z_vel: float = 0.0
    angle: float = 0.0
    velocity: Vector2 = field(default_factory=Vector2)
    angular_velocity: float = 0.0
    state: PropState = PropState.PLACED
    time_in_state: float = 0.0
    scale: float = 1.0
    prop_data: object = None          # type-specific state (fan angle, bounce count, etc.)
    surface_z: float = 0.0           # Z of the surface this prop rests on:
                                     #   0.0 = desk floor
                                     #   WINDOW_Z_HEIGHT = on a goose window
                                     #   prop_below.surface_z + prop_below.z = stacked on another prop
                                     # True world height = surface_z + z
    is_owned: bool = False            # True = goose retrieves if disturbed/dragged; False = litter, click to sweep
```

### 12.6.4 PropDef dataclass (per-type, static — lives in PROP_REGISTRY)

```python
@dataclass
class PropDef:
    render_fn: Callable
    render_broken_fn: Callable | None = None
    break_fn: Callable | None = None          # fn(position, velocity) → list[PropFragment]
    gravity_scale: float = 1.0               # 1.0=fall, -0.6=balloon rises
    restitution: float = 0.1
    friction: float = 0.6
    mass: float = 1.0                        # affects collision energy transfer — heavier absorbs more
    can_tip: bool = False                    # whether prop has TIPPING pre-fall state
    tip_velocity: float = 999.0             # minimum impulse to enter TIPPING
    fall_velocity: float = 999.0            # minimum impulse to skip TIPPING → straight FALLING
    can_break: bool = False
    break_velocity: float = 999.0           # minimum impulse → instant BROKEN
    bounces_off_edges: bool = False
    carry_offset_fn: Callable = default_carry_offset
    idle_animation: bool = False
    collision_radius: float = 10.0          # radius for prop-to-prop collision detection
    attachment_point: str | None = None     # rig point name for WORN props (e.g. "HEAD")
```

`PROP_REGISTRY: dict[PropType, PropDef]` — adding a new prop = write render fn + add one entry.

### 12.6.5 Prop physics (props/physics.py)

Prop physics lives in `pygoose/goose/props/physics.py`. `goose.py` calls `tick_props(props, fragments, goose_state, dt)` once per frame.

**Physics philosophy:** PyGoose is a personality engine, not a physics simulation. Thresholds (`tip_velocity`, `fall_velocity`, `break_velocity`) are design levers tuned by feel. Collision response is a single scalar multiply (velocity × mass ratio). TIPPING uses a spring oscillator for organic feel. This keeps overhead minimal and behavior predictable.

**Collision detection:** radius check between all prop pairs each tick. O(n²) but negligible at max 7 props (15 pairs). Both moving and stationary props checked. Outcome determined by velocity threshold stack.

**Render layering:**
- Prop at Z=0 (desk) → renders under goose windows
- Prop at Z = WINDOW_Z_HEIGHT → on window surface, renders over window
- Prop at Z > WINDOW_Z_HEIGHT → above window surface, renders over window
- Render order follows `surface_z + z`, not a flat "props always on top" rule

### 12.6.6 Prop ownership

Props are either **goose's property** (`is_owned=True`) or **litter** (`is_owned=False`). Tracked per-instance so ownership can change.

- **Owned:** goose retrieves if knocked over or dragged. High-priority task injection (same pattern as window interactions). Draggable by user — goose chases and retrieves.
- **Litter:** click to sweep. Goose doesn't care.

Which props are owned vs litter TBD per type. Ownership can change (e.g. balloon weight becomes litter after string is cut).

### 12.6.7 Task selection

`CARRY_PROP` is a single entry in `TASK_WEIGHTED_LIST` like any other task. When the deck picks it, `carry_prop.enter()` makes all further decisions:

- **Props already on screen?** Pick an interaction: play with it, remove it, or break it — weighted by prop type (breakables favor break, ball favors play, old/excess props favor removal).
- **No props on screen?** Carry a new one in — pick type from an internal weighted list: **common** (knife, fork, spoon), **medium** (balloon, hat), **very rare** (skateboard).

No dynamic injection into the task picker. `_choose_next_task` and the deck are untouched. All decisions live inside `carry_prop.py`. Max 7 props on screen (tunable).

### 12.6.8 Files

| File | Contents |
|------|----------|
| `pygoose/goose/props/__init__.py` | Empty package marker |
| `pygoose/goose/props/prop.py` | `PropType`, `PropState`, `FragmentShape`, `FragmentState`, `Prop`, `PropDef`, `PropFragment`, `PROP_REGISTRY` |
| `pygoose/goose/props/prop_renderer.py` | `render_prop`, `render_fragment` dispatch + per-type render fns |
| `pygoose/goose/props/physics.py` | `tick_props(props, fragments, goose_state, dt)` |
| `pygoose/goose/behaviors/carry_prop.py` | Carry-in, drop, pickup with internal prop type weighted list |

**Modified files:** `goose.py` (props/fragments lists, Task.CARRY_PROP, dispatch, physics tick call), `overlay.py` (render props and fragments)

### 12.6.9 Per-prop implementation process

For each new prop, in this order:

1. **Scaffolding** — add `PropType` enum value, stub entry in `PROP_REGISTRY`, stub render function returning nothing.
2. **DEV flag** — set `DEV_ForceSpawnProp = <prop_name>` and `DEV_HideGoose = True` in config.ini. This spawns the prop at the debug position with the full debug visualization active.
3. **Visual iteration** — run the goose and iterate QPainter shapes, colors, line weights until the prop looks right. Do not move on until the visual is locked.
4. **Derive everything else** — carry offset, collision radius, attachment point, break fragment shapes and colors all come directly from the finalized visual. Do not guess these upfront.
5. **Implement physics states and behavior** — add states, transitions, and carry_prop behavior logic.

**Why this order:** the visual is what everything else derives from. Designing physics before the visual means reworking all interaction points every time the shape changes.

### 12.6.10 Debug visualization system

Triggered by `DEV_ForceSpawnProp` in config.ini. Also set `DEV_HideGoose = True` and `DEV_ForceTask = wander` when using this mode. Implemented in `prop_renderer.py` `_render_debug_box`.

**Layout:** two white boxes stacked vertically — main box on top, compass below — no separator between them. Default position: left side of screen, with the stack anchored at `(270, screen_h - 728)` so the compass bottom clears the taskbar by ~50px. A **"⇄ flip screen pos"** button inside the top of the main box toggles the entire stack to the right side (`screen_w - 270`) and back, so the user can expose whichever side of the desktop they need. Click detection is handled in `_check_petting` using the stored `_debug_flip_rect`.

In `dirty_rect()`, when `_dev_debug_props` is True the full-screen rect is always returned, bypassing the dirty-rect optimization. This ensures the debug boxes repaint every frame regardless of where the invisible goose wanders.

**Main box (500×340):** up to three prop variants centered vertically, each labeled (v1/v2/v3) with the currently active variant marked by an orange dot. Two reference geese (facing 180° and 45°) in the upper portion for body-size reference. Right side (at `cx+195`, vertically mid-box): a single prop copy showing only its defined attach points as colored dots — hot pink for carry, full green for head, full blue for back. Bottom-left: two shadow previews labeled "prop w/ shadow (carried)" (Z=30, smaller shadow) and "prop w/ shadow (placed)" (Z=0, full-size shadow) to validate the dithered ellipse shadow at different heights — both call `_render_shadow` directly so they always match the live system. Bottom-center: two live oscillating shadow previews sharing the same sine-wave Z (period ~3.5s, range 0→30→0): left prop at 90° (vertical orientation), right prop at 0° (horizontal), both centered under the "live shadow (sine wave)" label at `cx±35`. Both use `_render_shadow` for the shadow and call `_draw_knife_shape` with `painter.rotate(angle)` for the sprite. Bottom-right legend: orange dot "currently shown" (active variant), then three colored dot entries for attach point types.

`_DEBUG_ACTIVE_VARIANT` in `prop_renderer.py` controls which variant is rendered in the compass, shadow previews, and attach point view simultaneously. Change it to "v1", "v2", or "v3" and restart to switch all test views at once.

**Compass box (500×500):** eight reference geese arranged in a circle, each facing outward in their exact compass direction (N/NE/E/SE/S/SW/W/NW). Each goose has the prop placed in carry position using the same rig math that runs in the live behavior — `rig.head2_end_point + fwd * 5` for the beak tip, `direction + 90` for the carry angle, and the same translate offset. This is a free integration test: if the prop looks right on all 8 geese, it will look right at runtime at any angle without per-direction tuning. Without it, a carry position that looks fine facing left may clip the neck facing up-right.

Each compass goose also renders a prop shadow beneath its body shadow, using `_render_shadow` with the same shadow dimensions as the live system. Shadow position formula:

```python
shadow_x = pos.x + fwd.x * 31.0
shadow_y = pos.y + fwd.y * 25.0
```

The facing direction (`fwd`) is used rather than the carry direction, so the shadow always appears directly ahead of the goose — where the beak and knife are. The x/y values differ (31 vs 25) because the body shadow ellipse is wider than it is tall: the same pixel gap looks proportionally larger vertically, so the y offset is dialed down to produce consistent perceived spacing in all 8 views. These values are tuned by eye with E/W as the reference.

**Compass draw order:**
```
_render_shadow(prop_shadow)  # prop shadow under everything
render_goose_body(...)       # goose shadow, feet, outline, white fill
_render_<prop>_in_beak(...)  # prop sits above body
render_goose_head(...)       # beak and eyes on top of prop
```

### 12.6.11 Carry attach point

In `_render_<prop>_in_beak`:

```python
fwd = Vector2.get_from_angle_degrees(direction)
beak_tip = rig.head2_end_point + fwd * 5.0   # actual tip — head2_end_point is the beak BASE
painter.save()
painter.translate(beak_tip.x, beak_tip.y)
painter.rotate(direction + 90)   # prop faces goose's right
painter.translate(N, 0)          # prop's x=0 sits N px ahead of beak tip along carry axis
painter.scale(1, -1)             # mirror Y so cutting edge faces away from body
_draw_prop_shape(painter, ...)
painter.restore()
```

`N` is the carry offset: the prop's local x=0 (grip junction) is `N` px ahead of the beak tip. The beak grips at local x = `-N`. Increase N to slide further toward the tip; decrease to grip further toward the back. The hot pink dot in the debug main box is drawn at x = `-N` on the horizontally-displayed prop so you can see exactly where the beak makes contact.

### 12.6.12 Render layering for carried props

Props held in the beak must render above the body but below the beak and eyes. `render_goose` in `renderer.py` is split for this purpose:

- `render_goose_body(painter, rig, position, direction, l_foot, r_foot, config)` — shadow, feet, outline layer, white fill layer
- `render_goose_head(painter, rig, direction, config)` — beak, eyes, sleep bubbles, exclamation mark
- `render_goose(...)` — wrapper calling both in sequence; existing callers unaffected

The live carry behavior must follow the same order: draw body → draw prop → draw head. Never draw a carried prop after `render_goose` — it will appear on top of the beak and eyes.

### 12.6.13 Adding a new prop — checklist

- [ ] `PropType` enum value added to `prop.py`
- [ ] Stub render function written and registered in `PROP_REGISTRY`
- [ ] Prop added to compass box and main debug box variants in `prop_renderer.py`
- [ ] Visual iterated to final state using debug system
- [ ] Carry attach offset (`N`) confirmed via hot pink dot in debug box
- [ ] `_render_<prop>_in_beak` written using `render_goose_body` / `render_goose_head` split
- [ ] Collision radius derived from finalized visual
- [ ] Physics states implemented in `props/physics.py`
- [ ] `carry_prop.enter()` updated to include new prop type in weighted selection

### 12.6.14 Planned: prop-agnostic debug system

The correct mental model: the debug box is a **prop design tool that any prop lives inside**. It is not something the knife owns. The knife was just the first prop to use it and served as the reference implementation to establish the system. Every future prop — fork, spoon, vase, balloon — should slot into the same tool with zero changes to the debug rendering code itself.

The debug box is currently knife-specific: `_draw_knife_shape`, `_render_knife_in_beak`, and `_DEBUG_KNIFE_VARIANTS` are all hardcoded to the knife. This is intentional — the knife was the reference implementation and its visual design is now locked. The refactor is queued but deferred until the second prop is added (see trigger below).

**Once the knife is fully locked**, refactor the debug system so it drives any prop through the registry instead of knife-specific calls:

- `_DEBUG_ACTIVE_PROP: PropType` replaces `_DEBUG_ACTIVE_VARIANT: str`
- Variant definitions (shape params, labels) move into `PropDef` or a companion `debug_variants` structure on each prop
- The compass calls `PropDef.carry_render_fn(painter, rig, direction)` instead of `_render_knife_in_beak`
- The shadow previews and attach point view call `PropDef.render_fn` instead of `_draw_knife_shape`
- The main box variant rows iterate `PropDef.debug_variants` instead of `_DEBUG_KNIFE_VARIANTS`

End state: changing `_DEBUG_ACTIVE_PROP` to any registered prop type repoints all test views — variants, compass, shadows, attach points — with zero changes to the debug rendering code.

**Trigger:** when adding the second prop. That's the natural moment — two props force the abstraction and provide a concrete second case to design against.

### 12.6.15 carry_prop behavior design

**Carry-in sequence:**
1. Goose walks off screen like collecting a notepad — no special exit animation.
2. Knife appears in beak while off-screen (rendered from the moment the goose re-enters the edge), exactly like how the notepad window pre-renders off-screen before drag-in. The goose never "picks it up" on-screen; he already has it.
3. Goose wanders back onto the desktop carrying the knife.

**Wander-with-knife phase:**
- Goose wanders normally (same speed, same pauses) with the knife visible in beak the whole time.
- Hold duration committed upfront on carry-in: random draw, weighted toward shorter end, range roughly 20s–3min.
- At the end of the hold duration (or on interrupt), goose drops or places the knife.

**Drop types (chosen randomly, except on interrupt):**
- *Place* — head dips down until beak tip reaches the knife's grab point at ground level; knife transfers cleanly to Z=0. Deliberate and calm.
- *Drop* — releases from carry height (Z=30); knife falls and bounces per physics. Casual or abrupt.
- Panic/startle always forces a drop (never a place).

**Pickup animation:**
When the goose later retrieves a placed or dropped knife, his head dips down until the beak tip reaches the knife's ground-level grab point, then lifts back up with the knife in beak. Dip depth is driven by the knife's actual `position.y` — beak must physically reach it.

**Note/meme surface interaction (planned, Z system not yet implemented):**
If a note or meme window is on screen, the probability of carrying the knife up to that surface increases. The goose can:
- Walk up to the note surface (using future z-climbing behavior), carry the knife onto it, and either place it on the edge immediately or drop it there during a later wander.
- The knife sitting on a note edge is then a candidate for the "nudge off edge" behavior — goose returns, nudges it, knife falls to desktop with a bounce.
Design this as a weight modifier on the drop-destination choice, not a separate task.

### 12.6.16 Knife threat mode

**Trigger:** Available in the task deck whenever the knife is on-screen in any state (carried or placed). Two entry paths:
- Goose already carrying knife → transitions directly into threat mode.
- Knife placed/dropped on screen → goose runs to knife, performs pickup animation, then transitions into threat mode.

**Approach phase:**
- Goose faces cursor and walks slowly toward it, knife out.
- Stops at a close-ish distance (~80–120px, tunable).

**Stare-down phase:**
- Holds position facing cursor.
- Occasional head jab toward cursor (quick forward-bob of the head, pull back).
- Occasional faint lunge with a honk — short forward dash toward cursor, then retreats to hold distance.
- All posturing — no actual cursor interaction.

**Exit A — cursor invades (startle):**
- If the cursor comes within a very close distance to the goose (as if trying to steal the knife back), goose startles, drops knife immediately (always a drop, never a place), and runs away in a full freak-out.

**Exit B — timeout (goose wins):**
1. Triumphant honk.
2. Walks a short distance away.
3. Walks a full victory lap circle, head bobbing continuously up and down the entire time, honking throughout. Knife remains in beak.
4. Lap complete → drops knife with no ceremony, mid-stride. Transitions to normal wander.

### 12.6.17 carry_prop.enter() — generalized decision model

When the deck picks `CARRY_PROP`, all decisions are made inside `carry_prop.enter()`. The deck and `_choose_next_task` are untouched. The model has three layers.

**Layer 1 — Assess world state**

Count what is on screen: by prop type, by state (PLACED, FALLING, CARRIED, etc.), and total count vs. the global cap. This snapshot drives everything below.

**Layer 2 — Decide: interact, remove, or fetch**

- Props with available interactions on screen → weighted toward interaction
- At or above global prop cap → weighted toward removal
- Nothing on screen → fetch new

These are weights, not hard rules — a nearly-full screen still has a chance to fetch, and a single prop still has a chance to be removed if it has no interesting interactions.

**Layer 3 — Execute**

- **Long-running interaction** (own stages, own state machine) → `_set_task(Task.X)` immediately. `carry_prop` hands off entirely; the new behavior file owns everything from that point.
- **Short interaction** (nudge, walk past, brief animation) → runs inline inside existing `carry_prop` stages. No new task or behavior file needed.
- **Fetch new** → pick type from internal weighted list (common / medium / rare tiers). Exit offscreen, re-enter carrying the prop. Uses the existing EXITING → WAITING → ENTERING stage flow.
- **Remove** → walk to the oldest or most numerous prop of a type, retrieve it (PICKUP_WALK → PICKUP_STOP → PICKUP_DIP), then exit offscreen without re-entering.

**Per-prop interaction registration**

Each prop type declares its supported interactions directly in its `PropDef` entry in `PROP_REGISTRY` — a list of `(weight, Task)` pairs for long-running interactions, plus a `can_remove` flag governing whether removal is a candidate for that type. `carry_prop.enter()` iterates all props currently on screen, builds a weighted pool from their registered interactions, and picks. A prop type with no interactions registered is only ever a candidate for removal or fetch — never for a dedicated behavior.

**File ownership**

- `props/` — what props *are*: data (`prop.py`), rendering (`prop_renderer.py`), physics (`physics.py`)
- `behaviors/` — what the goose *does*: `carry_prop.py` (decision layer + carry stages) and one file per long-running prop interaction (e.g. `knife_threat.py`)

**What never changes regardless of how many prop types exist**

- Single `CARRY_PROP` entry in `TASK_WEIGHTED_LIST`
- `_choose_next_task` and the deck untouched
- All existing `carry_prop` stages (EXITING, WAITING, ENTERING, PICKUP_WALK, PICKUP_STOP, PICKUP_DIP, WANDERING, PAUSING, PLACING) stay as-is
- New prop-specific behaviors are new files in `behaviors/`, dispatched via the existing `_BEHAVIOR_ENTER` / `_BEHAVIOR_TICK` tables

---

## 13. Task: Wander

```python
@dataclass
class WanderState:
    wander_start_time: float
    wander_duration: float
    pause_start_time: float = -1.0
    pause_duration: float = 0.0

# Duration constants:
MIN_PAUSE = 1.0       # seconds
MAX_PAUSE = 2.0       # seconds
GOOD_ENOUGH_DIST = 20.0

def get_random_wander_duration() -> float:
    if DEV_SHORT_WANDER:
        return 3.0
    return random_range(config.min_wandering_time_seconds, config.max_wandering_time_seconds)
```

```python
def run_wander():
    # If wander duration expired, choose next task
    if t - task_wander.wander_start_time > task_wander.wander_duration:
        choose_next_task()
        return

    if task_wander.pause_start_time > 0.0:
        if t - task_wander.pause_start_time > task_wander.pause_duration:
            task_wander.pause_start_time = -1.0
            walk_time = random_range(1.0, 6.0)
            max_walk_dist = walk_time * current_speed
            new_target = Vector2(random_range(0, screen_w), random_range(0, screen_h))
            if distance(position, new_target) > max_walk_dist:
                new_target = position + normalize(new_target - position) * max_walk_dist
            target_pos = new_target
        else:
            velocity = Vector2.zero   # freeze during pause
    else:
        if distance(position, target_pos) < GOOD_ENOUGH_DIST:
            task_wander.pause_start_time = t
            task_wander.pause_duration = random_range(1.0, 2.0)
```

---

## 14. Task: NabMouse

Three stages: `SEEKING_MOUSE` → `DRAGGING_MOUSE_AWAY` → `DECELERATING`

```python
MOUSE_GRAB_DISTANCE = 15.0    # px, beak tip to cursor
MOUSE_SUCC_TIME = 0.06        # seconds to transition clamp rect
MOUSE_DROP_DISTANCE = 30.0    # px, when to release
GIVE_UP_TIME = 9.0            # seconds before goose gives up chasing
STRUGGLE_RANGE = Vector2(3.0, 3.0)
```

```python
def run_nab_mouse():
    cursor_pos = get_cursor_pos()
    beak_tip = rig.head2_end_point

    if stage == SEEKING_MOUSE:
        set_speed(CHARGE)
        target_pos = cursor_pos - (beak_tip - position)

        if distance(beak_tip, cursor_pos) < MOUSE_GRAB_DISTANCE:
            original_vector_to_mouse = cursor_pos - beak_tip
            grabbed_time = t
            # Pick drag destination at least 1.2 charge-seconds away
            drag_to = position
            while distance(drag_to, position) / 400.0 < 1.2:
                drag_to = Vector2(random() * screen_w, random() * screen_h)
            target_pos = drag_to
            sound.chomp()
            stage = DRAGGING_MOUSE_AWAY

        if t > chase_start_time + GIVE_UP_TIME:
            stage = DECELERATING

    elif stage == DRAGGING_MOUSE_AWAY:
        if distance(position, target_pos) < MOUSE_DROP_DISTANCE:
            release_cursor_clip()
            stage = DECELERATING
        else:
            p = min((t - grabbed_time) / MOUSE_SUCC_TIME, 1.0)
            clip_vec = Vector2.lerp(original_vector_to_mouse, STRUGGLE_RANGE, p)
            set_cursor_clip(beak_tip.x + clip_vec.x, beak_tip.y + clip_vec.y,
                            abs(clip_vec.x), abs(clip_vec.y))

    elif stage == DECELERATING:
        target_pos = position + normalize(velocity) * 5.0
        velocity -= normalize(velocity) * current_acceleration * 2.0 * DELTA_TIME
        if magnitude(velocity) < 80.0:
            release_cursor_clip()
            set_task(Task.WANDER)
```

### 14.1 Platform cursor clip implementations

**Windows:** `ctypes.windll.user32.ClipCursor(ctypes.byref(RECT(left, top, right, bottom)))`. Release with `ClipCursor(None)`.

**macOS:** No `ClipCursor` equivalent. Simulate by moving cursor to the center of the clip rect each frame via `QCursor.setPos()`. Requires Accessibility permission — silently does nothing if not granted (graceful degradation).

**Linux:** Use `XGrabPointer` or the macOS simulation approach with `Xlib`.

---

## 15. Task: CollectWindow (Meme + Notepad)

### 15.1 Multi-window limit

The goose keeps up to **2 meme windows** and **2 notepad windows** on screen simultaneously (4 total). Each type has its own independent pool — a meme and a notepad do not compete. Windows are not auto-closed when the goose fetches a new one; they stay until the user closes them or the goose evicts one.

### 15.2 Stages

Full stage sequence:

```
(if 2 of this type already on screen)
WALKING_TO_EVICT → EVICTING_WINDOW →
WALKING_OFFSCREEN → WAITING_TO_BRING_WINDOW_BACK → DRAGGING_WINDOW_BACK
```

When fewer than 2 of this type are on screen, the eviction stages are skipped and the flow starts at `WALKING_OFFSCREEN`.

```python
WAIT_TIME_MIN = 2.0
WAIT_TIME_MAX = 3.5
```

### 15.3 Eviction (`WALKING_TO_EVICT` + `EVICTING_WINDOW`)

When 2 windows of the target type are already on screen, the goose picks one at random to evict before fetching the new window.

**Walk target:** The goose walks to the **grab edge** of the evict window (right edge for a left-side window, left edge for a right-side window), not the center. This avoids a snap when dragging begins.

```python
if window_center_x < screen_w / 2:
    evict_offset = Vector2(window_width, window_height / 2)  # beak at right edge
    grab_x = window.pos().x + window_width
else:
    evict_offset = Vector2(0, window_height / 2)             # beak at left edge
    grab_x = window.pos().x
target_pos = Vector2(grab_x, window_center_y)
stage = WALKING_TO_EVICT
```

**Eviction drag:** Once the goose reaches the grab edge, it extends its neck, attaches the window to its beak (same `move_threadsafe` mechanism as normal dragging), and walks toward the nearest screen edge (−80px past left or +80px past right). When the goose goes offscreen, the evict window is hidden and deleted; the goose then transitions to `WALKING_OFFSCREEN` for the new window.

The evicted window's `closing` signal is disconnected before hiding to prevent any anger callback from firing — the goose is the one removing it.

### 15.4 `_set_target_offscreen()`

```python
def _set_target_offscreen() -> ScreenDirection:
    if position.x > screen_w / 2:
        target_pos = Vector2(screen_w + 50, lerp(position.y, screen_h / 2, 0.4))
        return ScreenDirection.RIGHT
    else:
        target_pos = Vector2(-50, lerp(position.y, screen_h / 2, 0.4))
        return ScreenDirection.LEFT
```

### 15.5 Window offset (beak attachment point)

```python
if direction == ScreenDirection.LEFT:
    window_offset_to_beak = Vector2(window_width, window_height / 2)
elif direction == ScreenDirection.TOP:
    window_offset_to_beak = Vector2(window_width / 2, window_height)
elif direction == ScreenDirection.RIGHT:
    window_offset_to_beak = Vector2(0, window_height / 2)
```

### 15.6 Placement position

The drop target is chosen in `WAITING_TO_BRING_WINDOW_BACK`:

- **First window of its type:** placed with wide random spread — up to 300px from the entry edge, full vertical range (clamped to screen bounds).
- **Second window of its type:** same base position plus a messy offset (50–130px further from edge, ±150px perpendicular jitter). The goose is not neat.

```python
if d == ScreenDirection.LEFT:
    tx = w + random_range(15, 300)
    ty = random_range(h + 40, screen_h - 60)
elif d == ScreenDirection.RIGHT:
    tx = screen_w - (w + random_range(15, 300))
    ty = random_range(h + 40, screen_h - 60)
else:  # TOP
    tx = random_range(w + 60, screen_w - w - 60)
    ty = h + random_range(80, 350)

if another_of_same_type_on_screen:
    # Extra messy offset
    tx ± random_range(50, 130)   # further from edge
    ty ± random_range(-150, 150)  # perpendicular jitter
```

### 15.7 `run_collect_window()`

```python
def run_collect_window():
    if stage == WALKING_TO_EVICT:
        if distance(position, target_pos) < 15.0:
            # Set offscreen target for eviction
            stage = EVICTING_WINDOW

    elif stage == EVICTING_WINDOW:
        if offscreen or evict_window gone:
            hide and delete evict_window
            direction = _set_target_offscreen()
            stage = WALKING_OFFSCREEN
        else:
            override_extend_neck = True
            evict_window.move_threadsafe(beak - evict_window_offset)

    elif stage == WALKING_OFFSCREEN:
        if distance(position, target_pos) < 5.0:
            stage = WAITING_TO_BRING_WINDOW_BACK

    elif stage == WAITING_TO_BRING_WINDOW_BACK:
        velocity = Vector2.zero
        if t - wait_start_time > secs_to_wait:
            QMetaObject.invokeMethod(main_window, "show_dialog", QueuedConnection)
            main_window.closing.connect(on_window_closed_early)
            # compute placement target (see §15.6)
            stage = DRAGGING_WINDOW_BACK

    elif stage == DRAGGING_WINDOW_BACK:
        if distance(position, target_pos) < 5.0:
            placed_list.append(main_window)
            main_window.closing.connect(placed_window_close_callback)
            anger_window = main_window
            set_task(Task.WANDER)
            return
        override_extend_neck = True
        main_window.move_threadsafe(beak - window_offset_to_beak)
```

### 15.8 Placed window anger

The most recently placed window is the "anger window." If the user closes it:
- **Notepad window**: goose attacks indefinitely (no timeout)
- **Meme window**: goose gets angry only within 3 seconds of placing

Both trigger `set_task(Task.NAB_MOUSE)`. Closing any other (non-anger) placed window just removes it from the tracking list with no reprisal. The anger window reference updates whenever a new window is placed.

---

## 16. Task: TrackMud

Three stages: `DECIDE_TO_RUN` → `RUNNING_OFFSCREEN` → `RUNNING_WANDERING`

```python
TRACK_MUD_DURATION = 15.0       # seconds of mud tracking
DIR_CHANGE_INTERVAL = 100.0     # seconds (effectively never changes direction)
AMOK_DURATION = 2.0             # seconds of manic running before slowing
```

```python
def run_track_mud():
    if stage == DECIDE_TO_RUN:
        _set_target_offscreen()
        set_speed(RUN)
        stage = RUNNING_OFFSCREEN

    elif stage == RUNNING_OFFSCREEN:
        if distance(position, target_pos) < 5.0:
            target_pos = Vector2(random(0, screen_w), random(0, screen_h))
            next_dir_change_time = t + DIR_CHANGE_INTERVAL
            time_to_stop_running = t + AMOK_DURATION
            track_mud_end_time = t + TRACK_MUD_DURATION
            stage = RUNNING_WANDERING
            sound.play_mud_squish()

    elif stage == RUNNING_WANDERING:
        if distance(position, target_pos) < 5.0 or t > next_dir_change_time:
            target_pos = Vector2(random(0, screen_w), random(0, screen_h))
            next_dir_change_time = t + DIR_CHANGE_INTERVAL

        if t > time_to_stop_running:
            target_pos = Vector2(
                clamp(position.x + 30.0, 55.0, screen_w - 55.0),
                clamp(position.y + 3.0, 80.0, screen_h - 80.0),
            )
            set_task(Task.WANDER, honk=False)
```

`track_mud_end_time` is a float initialized to `-1.0`. Footmarks are added only while `t < track_mud_end_time`.

---

## 17. Task: WatchMouse

The goose sits near the cursor and watches it. Transitions between sub-states every few seconds.

```python
WATCH_MOUSE_DURATION_MIN = 8.0
WATCH_MOUSE_DURATION_MAX = 180.0
BOB_INTERVAL_MIN = 1.2
BOB_INTERVAL_MAX = 3.5
BOB_DURATION = 0.35
WATCH_HONK_INTERVAL_MIN = 5.0
WATCH_HONK_INTERVAL_MAX = 12.0
WATCH_SUB_DURATION_MIN = 2.0
WATCH_SUB_DURATION_MAX = 5.0
SIT_MIN_DURATION = 15.0     # goose will not leave SIT state before this long

class WatchSubState(Enum):
    STAND_STILL = "stand_still"
    WALK_SLOW   = "walk_slow"
    SIT         = "sit"

@dataclass
class WatchMouseState:
    start_time: float
    duration: float
    next_bob_time: float
    next_honk_time: float
    bob_end_time: float = -1.0
    sub_state: WatchSubState = WatchSubState.WALK_SLOW
    next_sub_change_time: float = 0.0
    sit_entered_time: float = -1.0
```

**Behavior per sub-state:**

- `STAND_STILL`: `_freeze_position = True`, standing pose
- `WALK_SLOW`: walk toward cursor at WALK speed if `dist > 60px`, otherwise freeze
- `SIT`: `_freeze_position = True`, `_target_sit_lerp = 1.0` (crouches down)

**Head bob:** Every `BOB_INTERVAL_MIN`–`BOB_INTERVAL_MAX` seconds (except while SIT), override neck extension for `BOB_DURATION` seconds to do a quick head bob.

**Rare honk:** Every `WATCH_HONK_INTERVAL_MIN`–`WATCH_HONK_INTERVAL_MAX` seconds, 30% chance to actually honk.

**Petting while sitting:** 70% honk, 20% wander away, 10% attack mouse.

**Always faces cursor** by setting `target_pos = position + normalize(cursor - position) * 50.0`.

---

## 18. Task: FollowMouse

The goose rushes to the cursor's preferred distance, then follows it. Can flee if cursor gets too close.

```python
FOLLOW_PREFERRED_DIST_MIN  = 90.0
FOLLOW_PREFERRED_DIST_MAX  = 160.0
FOLLOW_FLEE_DIST           = 45.0
FOLLOW_FLEE_DURATION       = 1.5
FOLLOW_BOREDOM_MIN         = 15.0
FOLLOW_BOREDOM_MAX         = 30.0
FOLLOW_SNAP_GRAB_CHANCE    = 0.05   # chance to transition to NAB_MOUSE on boredom
HONK_MARCH_CHANCE          = 0.12   # chance per check to start a honk march
HONK_MARCH_CHECK_INTERVAL  = 10.0
HONK_MARCH_DURATION        = 2.5
HONK_MARCH_RATE            = 0.38   # seconds between honks during march

class FollowMouseStage(Enum):
    RUSHING   = "rushing"
    FOLLOWING = "following"
    FLEEING   = "fleeing"
```

**Stages:**

- `RUSHING`: CHARGE toward cursor's preferred distance; transitions to FOLLOWING once in range
- `FOLLOWING`: Maintains preferred distance. Freezes when in comfortable zone (±35px deadband). Flees if cursor < 45px away. Occasionally starts a honk march (rapid honking for 2.5s). Returns to WALKING if drifts > preferred_dist + deadband.
- `FLEEING`: Runs 180px away from cursor at RUN speed for 1.5s, then returns to FOLLOWING

**Boredom:** After 15–30 seconds, 5% chance to snap into NAB_MOUSE, otherwise wander.

---

## 19. Task: SneakAttack

The goose crouches low (crawl pose) and sneaks toward the cursor. Pounces and grabs when close enough.

```python
SNEAK_STRIKE_DIST  = 65.0   # px to trigger pounce
SNEAK_MAX_DURATION = 44.0   # seconds before giving up
SNEAK_HONK_RATE    = 0.32   # seconds between honks during pounce/drag

class SneakAttackStage(Enum):
    SNEAKING     = "sneaking"
    POUNCING     = "pouncing"
    DRAGGING     = "dragging"
    DECELERATING = "decelerating"
```

**Stages:**

- `SNEAKING`: SNEAK speed, `_target_sit_lerp = 1.0`, `_target_neck_tuck = 1.0`. Creeps toward cursor. When within `SNEAK_STRIKE_DIST`, snap to standing pose and switch to POUNCING.
- `POUNCING`: CHARGE speed. Chase cursor like NabMouse SEEKING. Honk every `SNEAK_HONK_RATE`. Grab on `MOUSE_GRAB_DISTANCE`. If still not grabbed after `SNEAK_MAX_DURATION` extra time, give up to WANDER.
- `DRAGGING`: Same as NabMouse DRAGGING_MOUSE_AWAY. Continue honking. Release at `MOUSE_DROP_DISTANCE`.
- `DECELERATING`: Same as NabMouse DECELERATING.

---

## 20. Task: Sleep

The goose walks to a corner of the screen, circles down in a shrinking spiral, settles, and sleeps. Has a 15% chance of fake sleep (eyes open periodically, panics if spotted).

```python
SLEEP_CIRCLE_RADIUS   = 88.0
SLEEP_SETTLE_DURATION = 2.2
SLEEP_MIN_DURATION    = 90.0    # seconds minimum sleep
SLEEP_MAX_DURATION    = 480.0   # seconds maximum sleep (8 minutes)
SLEEP_CORNER_MARGIN   = 165.0   # px inset from screen edge for nest position

class SleepStage(Enum):
    WALKING_TO_CORNER = "walking_to_corner"
    CIRCLING          = "circling"
    SETTLING          = "settling"
    SLEEPING          = "sleeping"

@dataclass
class SleepState:
    nest_pos: Vector2
    spiral_start_angle: float = 0.0    # random start angle (radians)
    stage: SleepStage = SleepStage.WALKING_TO_CORNER
    spiral_t: float = 0.0              # 0→1 parametric progress along spiral
    settle_start_time: float = -1.0
    wake_time: float = -1.0
    is_fake_sleep: bool = False
    next_eye_event_time: float = -1.0  # when to open/close peeking eye
    eye_is_open: bool = False
    spotted_time: float = -1.0         # when cursor was spotted (triggers freak-out)
```

**Stages:**

**WALKING_TO_CORNER:** WALK speed toward one of three corners (top-left, top-right, bottom-right), each inset by `SLEEP_CORNER_MARGIN` px. Corner chosen randomly (or top-left in DEV mode). Slight random jitter (±15px) added to nest position.

**CIRCLING:** SNEAK speed. Target advances along a shrinking spiral at constant arc speed (40px/s), ensuring the goose always has a target slightly ahead of itself without overshooting. The spiral runs for 1.5 revolutions. Formula:
```python
arc_len = max(SLEEP_CIRCLE_RADIUS * (1.0 - spiral_t) * 1.5 * 2 * pi, 1.0)
spiral_t = min(spiral_t + (40.0 / arc_len) * DELTA_TIME, 1.0)
angle = spiral_start_angle + spiral_t * 1.5 * 2 * pi
radius = SLEEP_CIRCLE_RADIUS * (1.0 - spiral_t)
target_pos = nest_pos + Vector2(cos(angle) * radius, sin(angle) * radius)
# Transition to SETTLING when spiral_t >= 0.6
```

**SETTLING:** Freeze position. Over `SLEEP_SETTLE_DURATION` (2.2s), lerp `_target_sit_lerp` and `_target_neck_tuck` from 0→1 (goose crouches down and tucks head). At end, roll 15% chance for fake sleep.

**SLEEPING:** Freeze position, maintain full crawl pose. Wake after `wake_time`.

**Fake sleep behavior (is_fake_sleep=True):**
- No sleep bubbles rendered
- Every 5–15 seconds: open one eye (random left=1 or right=2) for 0.5–2.5 seconds, then close
- While any eye is open and cursor is within 150px: start spotted sequence
  - 0–0.75s: hold still (one eye open, no exclamation)
  - 0.75–1.5s: open both eyes (`peek_eye = 3`) + show exclamation mark
  - >1.5s: trigger freak-out (see §9.4)

**Real sleep behavior (is_fake_sleep=False):**
- Sleep bubbles rendered (`rig.show_sleep_bubbles = True`)
- Clicking the goose wakes it up (honk, transition to WANDER)

---

## 21. Task: PeekBack

After a fake-sleep freak-out, the goose returns to the nearest screen edge, peeks back in cautiously, sweeps its gaze, then walks back onto the screen normally.

```python
PEEK_INSET = 14.0   # px from screen edge for the peek position

@dataclass
class PeekBackState:
    peek_pos: Vector2       # position just inside screen edge
    enter_pos: Vector2      # position to walk toward when fully returning
    face_dir: float         # direction facing inward (0=right, 180=left, 90=down, -90=up)
    sweep_deg: float        # total sweep angle (45–150 degrees)
    stage: str = "peeking_in"
    look_start_time: float = -1.0
    look_duration: float = 8.8       # seconds for the sweep
    walk_in_dist: float = -1.0       # measured on first frame of walking_in
    pause_start_time: float = -1.0
    pause_duration: float = 0.0
```

**Setup (in `_set_task`):**
- Find nearest screen edge
- `peek_pos`: 14px inside that edge, clamped 80px from perpendicular edges
- `enter_pos`: random distance into the screen (150px to screen_w/2 or similar), with ±80–180px perpendicular diagonal offset (random direction), clamped to screen bounds
- `face_dir`: 0° for left edge, 180° for right edge, 90° for top edge, -90° for bottom edge
- `sweep_deg`: `random_range(45.0, 150.0)`
- Rig snapped immediately to full crawl: `rig.sit_lerp_percent = 1.0`, `rig.neck_tuck_lerp_percent = 1.0`

**Stages:**

- `peeking_in`: Walk to `peek_pos`. WALK speed until within 80px, then SNEAK speed. Full crawl pose. Transition to `looking` when within 12px.
- `looking`: Freeze position. Hold full crawl pose. Sweep gaze left/right using sine wave over `look_duration` seconds. The sweep uses a smoothstep ease-in/ease-out envelope over the first/last 18% of the duration, with linear exit blend to `enter_pos` direction in the final 18%:
  ```python
  t_norm = clamp(elapsed / look_duration, 0.0, 1.0)
  ramp = 0.18
  ease_in  = smoothstep(t_norm / ramp)
  ease_out = smoothstep((1.0 - t_norm) / ramp)
  envelope = min(ease_in, ease_out)
  sweep = sin(t_norm * 2π) * (sweep_deg / 2.0) * envelope
  target_dir = face_dir + sweep
  exit_blend = linear clamp of last ramp fraction
  target_pos = lerp(sweep_point, enter_pos, exit_blend)
  ```
- `walking_in`: SNEAK speed. Walk to `enter_pos`. Gradually stand up: `_target_sit_lerp` and `_target_neck_tuck` lerp from 1→0 proportional to distance remaining. Transition to `pausing` when within 12px.
- `pausing`: Freeze 0.5–1.5 seconds, then transition to WANDER.

---

## 22. Notepad Window (`notepad_window.py`)

### 22.1 Built-in phrases

```python
BUILTIN_PHRASES = [
    "am goose hjonk",
    "good work",
    "nsfdafdsaafsdjl\nasdas       sorry\nhard to type withh feet",
    "i cause problems on purpose",
    '"peace was never an option"\n   -the goose (me)',
    "\n\n  >o) \n    (_>",
]
```

### 22.2 Custom messages

Load all `.txt` files from `assets/text/notepad_messages/`. Merge with built-in phrases into a single Deck. If directory doesn't exist or is empty, use only built-in phrases.

The Deck is module-level and persists across `NotepadWindow` instances so the goose cycles through all phrases before repeating, even across multiple windows in the same session.

### 22.3 Window appearance

- Size: 200×150 px
- Title: `Goose "Not-epad"`
- Contains a multiline text box filling the client area
- Font: custom handwriting font loaded from `assets/fonts/`. Search for TTF/OTF files; prefer any font whose family name contains "fonty" or "notestar". Fall back to system default if none found.
- Font size: from `config.notepad_font_size` (default 25)
- `TopMost = True`

### 22.4 Custom font loading

```python
# On startup, scan assets/fonts/ for .ttf/.otf files
# Load via QFontDatabase.addApplicationFont()
# Prefer font with family name containing "fonty" or "notestar" (case-insensitive)
# Apply to notepad QTextEdit via QFont(family_name, font_size)
```

---

## 23. Meme Window (`meme_window.py`)

### 23.1 Local images

Load all files from `assets/images/memes/`. Supported formats: PNG, JPG, JPEG, GIF, BMP, WEBP.

Use a Deck for selection (no repeats until all shown). The Deck is module-level and persists across `MemeWindow` instances so the goose cycles through all images before repeating, even across multiple windows in the same session.

GIFs must animate — use `QMovie` for animated GIF playback inside a `QLabel`.

### 23.2 Window appearance

- Size: 400×400 px
- No title bar text
- Image displayed with `Qt.AspectRatioMode.KeepAspectRatio`
- `TopMost = True`
- Not resizable

---

## 24. Base Movable Window (`movable_window.py`)

Both NotepadWindow and MemeWindow inherit from this.

```python
class MovableWindow(QWidget):
    closing = pyqtSignal()    # emitted when user closes window

    def move_threadsafe(self, x: int, y: int):
        QMetaObject.invokeMethod(self, "_do_move", QueuedConnection,
                                 Q_ARG(int, x), Q_ARG(int, y))

    @pyqtSlot(int, int)
    def _do_move(self, x, y):
        self.move(x, y)

    def closeEvent(self, event):
        self.closing.emit()
        super().closeEvent(event)
```

NotepadWindow uses standard window chrome. MemeWindow is frameless.

---

## 25. Sound (`sound.py`)

### 25.1 Sound files

```
assets/sounds/Honk1.mp3   through   Honk4.mp3
assets/sounds/BITE.mp3
assets/sounds/MudSquish.mp3
assets/sounds/Pat1.wav
assets/sounds/Pat2.wav
assets/sounds/Pat3.wav
assets/sounds/Music.mp3    (optional — loop at 50% volume from startup)
```

### 25.2 Sound API

```python
class Sound:
    def init(self): ...         # pygame.mixer.init(), load/preload all files

    def honk(self):
        # Pick random from Honk1–4, play at volume 0.8
        # Stop previous honk before playing new one

    def chomp(self):
        # Play BITE.mp3 at volume 0.07

    def play_pat(self):
        # Pick random from Pat1–3 WAV pool, rewind to start, play

    def play_mud_squish(self):
        # Seek MudSquish.mp3 to start and play
```

### 25.3 Silence mode

If `config.silence_sounds = True`, all `Sound` methods are no-ops.

### 25.4 Music PCM cache

Looping `Music.mp3` through QMediaPlayer costs ~2% of a CPU core for the whole
session (continuous MP3 decode) — it was the entire measured CPU floor of an
otherwise-idle goose. On first run, `Sound` decodes the MP3 once in the
background (`QAudioDecoder` → Int16 PCM) and writes `assets/music_cache.wav`
(user-data side, gitignored, ~24 MB) via an atomic temp-file rename. Subsequent
sessions feed the WAV to the *same* QMediaPlayer pipeline — identical audio,
volume, and looping, with near-zero decode cost (static goose: ~2.0% → ~0.5% of
a core). The cache is only written if the decoder honours Int16; any failure or
a corrupt/missing cache silently falls back to the MP3 path. First session is
behaviourally identical to before (MP3 plays immediately while the cache builds).

---

## 26. Quit Mechanic

Hold ESC for ~5 seconds to quit. Progress bar slides in from top.

```python
QUIT_ALPHA_INCREMENT = 0.00216666679  # per frame while ESC held
QUIT_ALPHA_DECREMENT = 0.0166666675   # per frame while ESC released
QUIT_THRESHOLD = 0.99
QUIT_SHOW_THRESHOLD = 0.2
```

```python
def update_quit(painter, keys_pressed):
    if Key_Escape in keys_pressed:
        quit_alpha += QUIT_ALPHA_INCREMENT
    else:
        quit_alpha -= QUIT_ALPHA_DECREMENT
    quit_alpha = clamp(quit_alpha, 0.0, 1.0)

    if quit_alpha > QUIT_SHOW_THRESHOLD:
        frac = (quit_alpha - 0.2) / 0.8
        y = int(lerp(-15, 10, exponential_ease_out(frac * 2)))
        # LightBlue background, LightPink progress fill, dark text
        text = "Continue holding ESC to evict goose"

    if quit_alpha > QUIT_THRESHOLD:
        QApplication.quit()
```

---

## 27. Modding API (`mod_loader.py`)

### 27.1 Mod structure

```
mods/
└── MyModName/
    ├── mod.py          # Required. Must contain a class named Mod.
    └── assets/         # Optional.
```

### 27.2 Mod interface

```python
class Mod:
    def __init__(self, api: GooseAPI): ...
    def on_load(self): ...
    def on_tick(self): ...
    def on_render(self, painter: QPainter): ...
    def on_task_changed(self, task: Task): ...
    def on_unload(self): ...
```

All methods are optional — `mod_loader` checks `hasattr` before calling.

### 27.3 GooseAPI surface

```python
class GooseAPI:
    @property
    def position(self) -> Vector2: ...
    @property
    def velocity(self) -> Vector2: ...
    @property
    def direction(self) -> float: ...
    @property
    def current_task(self) -> Task: ...
    @property
    def screen_size(self) -> tuple[int, int]: ...
    @property
    def rig(self) -> Rig: ...

    def set_task(self, task: Task): ...
    def play_sound(self, path: str): ...
    def show_image_window(self, image_path: str): ...
    def show_text_window(self, text: str): ...
    def add_foot_mark(self, position: Vector2): ...
    def draw_circle(self, painter, center: Vector2, radius: int, color: str): ...
    def draw_line(self, painter, start: Vector2, end: Vector2, width: int, color: str): ...
```

### 27.4 Loading

Mods load only when `config.enable_mods = True`. Loaded alphabetically. Bad mods log an error and are skipped — never crash the app.

---

## 28. Developer Flags

Three flags in `config.ini` for testing specific behaviors without waiting for them to appear naturally. Edit the file and restart — do not hardcode these in source.

```ini
DEV_ForceTask = collect_window_notepad  ; force a specific task every time (blank to disable)
DEV_ShortWander = True                  ; wander lasts only 3 seconds
DEV_ForceFakeSleep = True               ; always fake sleep instead of 15% chance
```

`DEV_ForceTask` is checked in `_choose_next_task()` — if set, bypasses the deck entirely.
`DEV_ShortWander` is checked in `_get_random_wander_duration()`.
`DEV_ForceFakeSleep` is checked during the SETTLING→SLEEPING transition.

Additionally, when `DEV_ForceTask` is set, the SLEEP task always uses the top-left corner instead of a random corner.

Clear all three before pushing a stable version tag.

---

## 29. Startup Sequence

```
1. Create QApplication
2. Detect platform; if Wayland and no XWayland: show error dialog and exit
3. Load config.ini (create silently with defaults if missing)
4. Create overlay window (transparent, always-on-top, click-through)
5. Size overlay to primary monitor
6. Apply platform-specific click-through (Windows: SetWindowLong)
7. Init sound system (unless SilenceSounds=True)
8. Init goose (TheGoose.__init__):
   a. Set initial position to (-20, 120)
   b. Set initial target to (100, 150)
   c. Init foot positions
   d. Set initial task to WANDER (with honk=False)
9. If EnableMods=True: discover and load mods
10. Start game loop timer
11. QApplication.exec()
```

---

## 30. Platform Notes for Claude Code

### Windows
- Click-through: must call `SetWindowLong` via ctypes after window show.
- Cursor clip: `ClipCursor` via ctypes, `RECT` struct.
- Bring to foreground: `SetForegroundWindow(hwnd)` when goose grabs cursor.

### macOS
- Click-through: `WA_TransparentForMouseEvents` is not enough alone — also call `NSApp.windows()[n].setIgnoresMouseEvents_(True)` via PyObjC after `show()`.
- Accessibility permissions required for cursor move (`QCursor.setPos()`). Check with `Quartz.AXIsProcessTrusted()` on startup and show a dialog if not granted.
- If `pyobjc-framework-Quartz` is not installed, show a dialog on startup telling the user to `pip install pyobjc-framework-Quartz`. Goose still runs without it — mouse stealing just won't work.
- No `ClipCursor` equivalent — simulate by calling `QCursor.setPos()` to the clip rect center each frame.

### Linux
- Check for `DISPLAY` env var; abort with message if not set.
- `pyautogui` uses `python-xlib` — ensure it's in requirements.

---

## 31. Asset Requirements

| File | Description |
|------|-------------|
| Honk1–4.mp3 | Goose honk sounds (4 variants) |
| BITE.mp3 | Cursor grab sound (very quiet, 0.07 volume) |
| MudSquish.mp3 | Mud footstep squish sound |
| Pat1–3.wav | Footstep pat sounds (3 variants) |
| Music.mp3 | Optional background music loop |

App must not crash if sound files are missing — log a warning and continue.

---

## 32. Implementation Checkpoints for Claude Code

| # | Checkpoint | Deliverable |
|---|-----------|-------------|
| 1 | Engine layer | `vector2.py`, `math_utils.py`, `easings.py`, `deck.py`, `rig.py`, `time_keeper.py` — with unit tests |
| 2 | Transparent overlay window | Window covers screen, is transparent, click-through on all 3 platforms. |
| 3 | Goose rig + renderer | Goose drawn correctly at a fixed position. All body parts correct sizes/colors. Crawl/sit pose works. |
| 4 | Physics + wander | Goose walks around screen autonomously. Feet animate. Neck extends at run speed. |
| 5 | Footmarks | TrackMud task works. Brown dots appear and fade. |
| 6 | NabMouse | Cursor gets grabbed and dragged. All 3 platforms. |
| 7 | Notepad window | Window spawns with custom font. Goose drags it. Early close triggers NabMouse. |
| 8 | Meme window | Image/GIF window spawns. GIF animates. |
| 9 | WatchMouse | Goose sits near cursor, bobs, occasionally honks. Petting while sitting has three outcomes. |
| 10 | FollowMouse | Goose follows cursor at preferred distance. Flees if too close. Honk marches. |
| 11 | SneakAttack | Goose creeps in crawl pose, pounces, grabs. |
| 12 | Sleep | Goose circles to corner, settles, sleeps. Fake sleep with eye peeking and freak-out. |
| 13 | PeekBack | Post-freak-out peek sequence with sweep and walk-in. |
| 14 | Sound | All sounds play. Silence mode works. |
| 15 | Config | config.ini loads/saves. Custom colors work. |
| 16 | Quit mechanic | ESC hold progress bar. Correct timing. |
| 17 | Mod API | Loader discovers mods. Example mod runs. Bad mods don't crash app. |
| 18 | Packaging | PyInstaller builds working single-folder distributions for Windows, macOS, Linux. |

---

## 33. Known Deviations from Original

| Feature | Original | PyGoose |
|---------|----------|-----------|
| Donate window | Shows after 480s | Omitted |
| Config file name | `config.goos` | `config.ini` |
| Sound backend | WinMM `mciSendString` | `pygame.mixer` |
| Cursor clip on macOS | Not supported (Windows-only) | Simulated with `QCursor.setPos()` each frame; requires Accessibility permission |
| Mod format | C# DLLs | Python plugins |
| First UX sequence | TrackMud → Meme hardcoded | Same behavior, cleaner implementation |
| Linux support | None | X11 supported |
| New tasks | None | WatchMouse, FollowMouse, SneakAttack, Sleep/FakeSleep, PeekBack |
| Config missing | Show messagebox | Create silently |
| Notepad font | System default | Custom handwriting font from assets/fonts/ |

---

## 34. Packaging — Standalone Executable (PyInstaller)

The goal is a double-click-to-run experience for users who have no Python installed. PyInstaller bundles the interpreter, all dependencies, and assets into a self-contained output.

### 34.1 Output mode

**Windows and Linux:** Use **one-folder** (`--onedir`):

- A folder containing the executable plus DLLs, Qt platform plugins, and the assets tree
- Startup is instant (no extraction step)
- User zips the folder and shares it, or just hands over the folder

**macOS:** Use **one-file** (`--onefile`):

- Produces a single `PyGoose` binary
- macOS Gatekeeper quarantines each file individually in a one-folder build, requiring the user to approve every DLL and dylib. A single binary means one approval and it runs.
- Trade-off: each launch extracts ~80MB to a temp directory (~2–3 second delay on first launch after a cold boot). Acceptable for macOS given the Gatekeeper UX problem it solves.

The `PyGoose.spec` is platform-aware: `is_mac = sys.platform == 'darwin'` gates which output mode is used.

### 34.2 Asset path resolution

When PyInstaller bundles a one-folder build, the working directory at runtime is not the same as where the exe lives. All asset paths must go through a helper:

```python
import sys, os

def resource_path(relative: str) -> str:
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)
```

Every place in the code that opens a file from `assets/` must use `resource_path("assets/...")` instead of a bare relative path. This applies to: sound loading, font loading, meme images, notepad text files.

### 34.3 `config.ini` placement

`config.ini` must **not** be bundled inside the PyInstaller package — it needs to live next to the exe so users can edit it. At startup, resolve the config path relative to the exe's actual location, not `_MEIPASS`:

```python
def config_path() -> str:
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle — config lives next to the exe
        return os.path.join(os.path.dirname(sys.executable), 'config.ini')
    else:
        # Running from source
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
```

Similarly, `assets/text/notepad_messages/` and `assets/images/memes/` are user-drop folders — they should also live next to the exe, not inside the bundle, so users can add their own content without re-packaging. Two separate path roots: `resource_path()` for read-only bundled assets (sounds, fonts), and `user_data_path()` (exe-relative) for user-editable content (config, memes, notes).

### 34.4 PyInstaller spec file

A `.spec` file should be committed to the repo rather than relying on CLI flags. Key entries:

```python
# PyGoose.spec (sketch)
a = Analysis(
    ['main.py'],
    datas=[
        ('assets/sounds',  'assets/sounds'),
        ('assets/fonts',   'assets/fonts'),
        # memes and notepad_messages are user-side — do NOT bundle them
    ],
    hiddenimports=[
        'pygame',
        'PyQt6.sip',
    ],
)
```

Qt platform plugins (specifically `qwindows.dll` / `qcocoa.dylib` / `qxcb.so`) must be included or the window will not open. PyInstaller's PyQt6 hook usually handles this automatically, but verify in testing.

### 34.5 Known packaging gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| Blank screen / no window | Qt platform plugin missing | Ensure `platforms/` folder is in the bundle; add `--collect-all PyQt6` if needed |
| No sound | pygame SDL DLLs missing | `--collect-all pygame` or manually include `SDL2.dll` |
| Assets not found | Bare relative paths | Replace all asset opens with `resource_path()` |
| Config resets on every run | config.ini inside bundle (read-only) | Use `config_path()` pointing to exe directory |
| Antivirus flags the exe | PyInstaller one-file signature | Use one-folder build; code-sign the exe for distribution |
| Slow startup | One-file extraction | Switch to one-folder |

### 34.6 Build script

A simple `build.py` or `build.bat` at the repo root should encapsulate the build command so it's repeatable:

```bat
:: build.bat
pyinstaller PyGoose.spec --noconfirm --clean
```

Output lands in `dist/PyGoose/`. The build script should also copy a blank `config.ini` (with defaults) and empty `assets/images/memes/` and `assets/text/notepad_messages/` folders into `dist/PyGoose/` so the distribution is ready to use out of the box.

### 34.7 Code changes required before packaging works

- [ ] Replace all bare `open("assets/...")` calls with `resource_path()`
- [ ] Add `config_path()` helper and thread it through `GooseConfig`
- [ ] Add `user_data_path()` helper for memes and notepad messages
- [ ] Write `PyGoose.spec`
- [ ] Write `build.bat` / `build.sh`
- [ ] Test on a clean Windows machine with no Python installed

---

## 35. Future Feature Ideas / Backlog

Feature backlog is maintained in `CLAUDE.md` (local only, not in git). Items move here once implemented.

### 35.1 Window cleanup (two-window limit with eviction drag) — **Implemented in 0.33**

The goose keeps up to 2 notepad and 2 meme windows on screen (per type, independent pools). When a 3rd would be added, a random existing window of that type is evicted first — the goose walks to its edge, grabs it, drags it offscreen, and then fetches the new window normally. See §15 for full implementation details.

---

### 35.2 Standalone prop design tool

The debug visualization system built into PyGoose (§12.6.10) will eventually be extracted into its own standalone Python GUI application — a prop design tool that runs independently from PyGoose. The goal is to make adding new props accessible without requiring an AI or deep familiarity with the codebase.

**Motivation:** The current process (edit Python, restart goose, iterate visually) works well but has friction. A dedicated tool could offer: a live canvas where you draw and adjust shapes, sliders for carry offset and collision radius, instant preview of the prop at all 8 compass directions, export of the generated render code and PropDef registry entry directly into PyGoose's prop files.

**When to build:** after several props have been implemented together and the patterns are fully understood. Each new prop implementation adds to the knowledge of what the tool needs to handle. The tool should be built from experience, not speculation.

**What it replaces:** `_render_debug_box`, `_render_compass_box`, and the `DEV_ForceSpawnProp` flow — those become the reference implementation that the standalone tool is modeled on.

---

## 36. Development Workflow Guardrails

See `CLAUDE.md` → **Pending fixes** → "Git push hook" for the planned `PreToolUse` hook that will enforce the no-unauthorized-push rule at the harness level.

---

## 37. Known Issues / Needs Investigation

Active bug tracking lives in `CLAUDE.md` → **Pending fixes**. Items move here once resolved.

### 37.1 macOS window appear/disappear asymmetry — see CLAUDE.md

### 37.2 ESC quit unreliable in packaged exe — see CLAUDE.md
