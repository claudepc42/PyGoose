import os
import configparser
from dataclasses import dataclass
from PyQt6.QtWidgets import QMessageBox

from pygoose.paths import user_data_path
CONFIG_VERSION = 1


@dataclass
class GooseConfig:
    version: int = CONFIG_VERSION
    enable_mods: bool = False
    silence_sounds: bool = False
    silence_music: bool = False
    task_can_attack_mouse: bool = True
    attack_randomly: bool = False
    use_custom_colors: bool = False
    goose_color_body: str = "#ffffff"
    goose_color_underbody: str = "#d3d3d3"
    goose_color_beak: str = "#ffa500"
    min_wandering_time_seconds: float = 20.0
    max_wandering_time_seconds: float = 40.0
    first_wander_time_seconds: float = 20.0
    notepad_font_size: int = 32 if __import__('sys').platform == "darwin" else 25
    dev_force_task: str = ""
    dev_short_wander: bool = False
    dev_skip_wander: bool = False
    dev_force_fake_sleep: bool = False
    dev_force_spawn_prop: str = ""  # e.g. "knife" — spawns that prop PLACED at screen center with debug white box
    dev_hide_goose: bool = False    # suppress goose rendering entirely (physics still ticks); for prop visual design


def _warn(msg: str):
    box = QMessageBox()
    box.setWindowTitle("PyGoose")
    box.setText(msg)
    box.exec()


def _write_defaults(path: str) -> GooseConfig:
    cfg = GooseConfig()
    _save(cfg, path)
    return cfg


def _save(cfg: GooseConfig, path: str):
    parser = configparser.ConfigParser()
    parser["Goose"] = {
        "Version":                  str(cfg.version),
        "EnableMods":               str(cfg.enable_mods),
        "SilenceSounds":            str(cfg.silence_sounds),
        "SilenceMusic":             str(cfg.silence_music),
        "Task_CanAttackMouse":      str(cfg.task_can_attack_mouse),
        "AttackRandomly":           str(cfg.attack_randomly),
        "UseCustomColors":          str(cfg.use_custom_colors),
        "GooseColorBody":           cfg.goose_color_body,
        "GooseColorUnderbody":      cfg.goose_color_underbody,
        "GooseColorBeak":           cfg.goose_color_beak,
        "MinWanderingTimeSeconds":  str(cfg.min_wandering_time_seconds),
        "MaxWanderingTimeSeconds":  str(cfg.max_wandering_time_seconds),
        "FirstWanderTimeSeconds":   str(cfg.first_wander_time_seconds),
        "NotepadFontSize":          str(cfg.notepad_font_size),
    }
    if cfg.dev_force_task:
        parser["Goose"]["DEV_ForceTask"] = cfg.dev_force_task
    if cfg.dev_short_wander:
        parser["Goose"]["DEV_ShortWander"] = str(cfg.dev_short_wander)
    if cfg.dev_skip_wander:
        parser["Goose"]["DEV_SkipWander"] = str(cfg.dev_skip_wander)
    if cfg.dev_force_fake_sleep:
        parser["Goose"]["DEV_ForceFakeSleep"] = str(cfg.dev_force_fake_sleep)
    if cfg.dev_force_spawn_prop:
        parser["Goose"]["DEV_ForceSpawnProp"] = cfg.dev_force_spawn_prop
    if cfg.dev_hide_goose:
        parser["Goose"]["DEV_HideGoose"] = str(cfg.dev_hide_goose)
    with open(path, "w") as f:
        parser.write(f)


def load_config() -> GooseConfig:
    path = user_data_path("config.ini")

    if not os.path.exists(path):
        return _write_defaults(path)

    parser = configparser.ConfigParser()
    try:
        parser.read(path)
        g = parser["Goose"]

        version = int(g.get("Version", CONFIG_VERSION))
        if version != CONFIG_VERSION:
            _warn(f"config.ini version mismatch (found {version}, expected {CONFIG_VERSION}). Resetting to defaults.")
            os.remove(path)
            return _write_defaults(path)

        return GooseConfig(
            version=version,
            enable_mods=g.getboolean("EnableMods", False),
            silence_sounds=g.getboolean("SilenceSounds", False),
            silence_music=g.getboolean("SilenceMusic", False),
            task_can_attack_mouse=g.getboolean("Task_CanAttackMouse", True),
            attack_randomly=g.getboolean("AttackRandomly", False),
            use_custom_colors=g.getboolean("UseCustomColors", False),
            goose_color_body=g.get("GooseColorBody", "#ffffff"),
            goose_color_underbody=g.get("GooseColorUnderbody", "#d3d3d3"),
            goose_color_beak=g.get("GooseColorBeak", "#ffa500"),
            min_wandering_time_seconds=float(g.get("MinWanderingTimeSeconds", 20.0)),
            max_wandering_time_seconds=float(g.get("MaxWanderingTimeSeconds", 40.0)),
            first_wander_time_seconds=float(g.get("FirstWanderTimeSeconds", 20.0)),
            notepad_font_size=int(g.get("NotepadFontSize", 25)),
            dev_force_task=g.get("DEV_ForceTask", "").strip(),
            dev_short_wander=g.getboolean("DEV_ShortWander", False),
            dev_skip_wander=g.getboolean("DEV_SkipWander", False),
            dev_force_fake_sleep=g.getboolean("DEV_ForceFakeSleep", False),
            dev_force_spawn_prop=g.get("DEV_ForceSpawnProp", "").strip(),
            dev_hide_goose=g.getboolean("DEV_HideGoose", False),
        )

    except Exception as e:
        _warn(f"config.ini could not be parsed ({e}). Resetting to defaults.")
        try:
            os.remove(path)
        except Exception:
            pass
        return _write_defaults(path)
