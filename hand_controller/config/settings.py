from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


def _runtime_bundle_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass).resolve()
    return REPO_ROOT


def _runtime_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return REPO_ROOT


RUNTIME_BUNDLE_ROOT = _runtime_bundle_root()
RUNTIME_APP_DIR = _runtime_app_dir()
DEFAULT_TUNING_PATH = RUNTIME_APP_DIR / "tuning.local.json"
DEFAULT_ARTIFACTS_DIR = RUNTIME_BUNDLE_ROOT / "artifacts"
DEFAULT_FALLBACK_ARTIFACTS_DIR = (
    REPO_ROOT.parent / "touch-v15" / "hand_controller" / "artifacts"
    if not getattr(sys, "frozen", False)
    else DEFAULT_ARTIFACTS_DIR
)


@dataclass(slots=True, frozen=True)
class GeneralConfig:
    language: str = "English"
    theme: str = "Dark"
    minimize_after_launch: bool = True


@dataclass(slots=True, frozen=True)
class CameraConfig:
    enabled: bool = True
    index: int = 0
    width: int = 640
    height: int = 480


@dataclass(slots=True, frozen=True)
class MouseMotionConfig:
    sensitivity: float = 0.95
    smoothing_window: int = 2
    anchor_alpha: float = 1.0
    ema_alpha: float = 0.58
    wake_threshold_px: float = 3.20
    sleep_threshold_px: float = 1.25
    micro_jitter_px: float = 0.90
    gain_exponent: float = 1.02
    accel_start_px: float = 5.0
    fast_gain: float = 1.10
    spike_clamp_px: float = 48.0
    reanchor_distance_px: float = 140.0
    max_step_px: float = 30.0
    move_timeout: float = 0.35


@dataclass(slots=True, frozen=True)
class MouseClickConfig:
    left_pinch_threshold_px: float = 35.0
    left_press_multiplier: float = 0.72
    left_release_multiplier: float = 1.02
    right_pinch_threshold_px: float = 46.0
    right_press_multiplier: float = 0.88
    right_release_multiplier: float = 1.12
    click_cooldown: float = 0.08
    double_click_interval: float = 0.60
    double_click_assist_window: float = 0.38
    left_hold_drag_seconds: float = 0.38
    drag_lost_grace_seconds: float = 0.45


@dataclass(slots=True, frozen=True)
class KeyboardConfig:
    virtual_keyboard_enabled: bool = True
    tap_cooldown_seconds: float = 0.15
    height_ratio: float = 0.36
    side_margin_px: int = 20
    bottom_margin_px: int = 20
    key_gap_px: int = 6
    row_gap_px: int = 6
    show_skeleton: bool = True
    show_pointers: bool = True
    show_selfie: bool = True
    selfie_position: str = "top_left"
    selfie_custom_x_ratio: float | None = None
    selfie_custom_y_ratio: float | None = None
    selfie_width_px: int = 320
    selfie_height_px: int = 240
    show_gesture_command: bool = True
    gesture_command_position: str = "top"
    gesture_command_hold_seconds: float = 0.85
    key_label_font_px: int = 14
    pointer_label_font_px: int = 10
    header_font_px: int = 14
    status_font_px: int = 12
    footer_font_px: int = 11
    pointer_radius_px: int = 9
    pointer_stroke_px: int = 2
    skeleton_stroke_px: int = 2
    key_border_px: int = 2
    key_hover_border_px: int = 3
    status_panel_max_width_px: int = 880
    status_line_height_px: int = 22
    quick_toolbar_edge: str = "right"
    quick_toolbar_offset_ratio: float = 0.5
    layout_rows: tuple[tuple[str, ...], ...] = field(
        default_factory=lambda: (
            ("ESC", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"),
            ("TAB", "A", "S", "D", "F", "G", "H", "J", "K", "L"),
            ("SHIFT", "Z", "X", "C", "V", "B", "N", "M", "BACKSPACE"),
            ("PAGE_SYMBOLS", "CAPS", "SPACE", "ENTER"),
        )
    )
    symbol_layout_rows: tuple[tuple[str, ...], ...] = field(
        default_factory=lambda: (
            ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"),
            ("SEMICOLON", "COLON", "APOSTROPHE", "DOUBLE_QUOTE", "COMMA", "PERIOD", "SLASH", "BACKSLASH", "MINUS", "UNDERSCORE"),
            ("QUESTION", "EXCLAMATION", "LPAREN", "RPAREN", "BACKSPACE"),
            ("PAGE_ALPHA", "SPACE", "ENTER"),
        )
    )
    key_width_units: dict[str, float] = field(
        default_factory=lambda: {
            "ESC": 1.20,
            "BACKSPACE": 1.90,
            "TAB": 1.40,
            "ENTER": 1.80,
            "SHIFT": 1.80,
            "CAPS": 1.60,
            "PAGE_SYMBOLS": 1.50,
            "PAGE_ALPHA": 1.50,
            "SPACE": 4.60,
            "MINUS": 1.10,
            "UNDERSCORE": 1.10,
            "QUESTION": 1.10,
            "EXCLAMATION": 1.10,
            "LPAREN": 1.10,
            "RPAREN": 1.10,
            "BACKSLASH": 1.10,
        }
    )
    index_pinch_threshold_px: float = 35.0
    index_press_multiplier: float = 0.72
    index_release_multiplier: float = 1.02
    middle_pinch_threshold_px: float = 46.0
    middle_press_multiplier: float = 0.88
    middle_release_multiplier: float = 1.12
    ring_pinch_threshold_px: float = 42.0
    ring_press_multiplier: float = 0.84
    ring_release_multiplier: float = 1.10
    pinky_pinch_threshold_px: float = 52.0
    pinky_press_multiplier: float = 0.92
    pinky_release_multiplier: float = 1.14
    mode_toggle_hold_seconds: float = 0.35
    mode_toggle_cooldown_seconds: float = 0.80
    require_palm_facing_for_toggle: bool = True


@dataclass(slots=True, frozen=True)
class HandTrackerConfig:
    max_num_hands: int = 2
    min_detection_confidence: float = 0.7
    min_tracking_confidence: float = 0.7
    mirror_input: bool = True


@dataclass(slots=True, frozen=True)
class HandSelectorConfig:
    switch_margin: float = 0.18
    lost_grace_seconds: float = 0.30
    centroid_switch_px: float = 85.0


@dataclass(slots=True, frozen=True)
class HandOwnershipConfig:
    enabled: bool = True
    max_trusted_hands: int = 2
    calibration_hold_seconds: float = 0.60
    guide_no_hand_grace_seconds: float = 0.50
    reacquire_grace_seconds: float = 1.00
    max_travel_px: float = 150.0
    pending_match_px: float = 90.0
    zone_x1_ratio: float = 0.34
    zone_y1_ratio: float = 0.30
    zone_x2_ratio: float = 0.66
    zone_y2_ratio: float = 0.70
    require_press_safe_for_lock: bool = True


@dataclass(slots=True, frozen=True)
class MLConfig:
    enabled: bool = True
    accepted_action_labels: tuple[str, ...] = ("toggle", "hold", "undo")
    ignored_behavior_labels: tuple[str, ...] = ("left_click", "right_click", "idle")
    scaler_path: str = field(
        default_factory=lambda: str(DEFAULT_ARTIFACTS_DIR / "validator_scaler.joblib")
    )
    label_encoder_path: str = field(
        default_factory=lambda: str(DEFAULT_ARTIFACTS_DIR / "validator_label_encoder.joblib")
    )
    model_path: str = field(
        default_factory=lambda: str(DEFAULT_ARTIFACTS_DIR / "validator_MLP.joblib")
    )
    fallback_scaler_path: str = field(
        default_factory=lambda: str(DEFAULT_FALLBACK_ARTIFACTS_DIR / "validator_scaler.joblib")
    )
    fallback_label_encoder_path: str = field(
        default_factory=lambda: str(DEFAULT_FALLBACK_ARTIFACTS_DIR / "validator_label_encoder.joblib")
    )
    fallback_model_path: str = field(
        default_factory=lambda: str(DEFAULT_FALLBACK_ARTIFACTS_DIR / "validator_MLP.joblib")
    )
    gate_min_p1: float = 0.42
    gate_min_margin: float = 0.05
    stability_window: int = 4
    confirm_frames: int = 2
    toggle_hold_seconds: float = 0.45
    toggle_cooldown: float = 0.80
    shortcut_cooldown: float = 0.60
    pre_hold_right_click_suppression: bool = True
    pre_hold_min_p1: float = 0.55


@dataclass(slots=True, frozen=True)
class AppConfig:
    python_version: str
    general: GeneralConfig
    camera: CameraConfig
    tracker: HandTrackerConfig
    selector: HandSelectorConfig
    ownership: HandOwnershipConfig
    mouse_motion: MouseMotionConfig
    mouse_click: MouseClickConfig
    keyboard: KeyboardConfig
    ml: MLConfig
    tuning_path: str | None = None


def _replace_dataclass(config_obj: Any, overrides: dict[str, Any], *, section_name: str) -> Any:
    valid_field_names = {field.name for field in fields(config_obj)}
    unknown = sorted(set(overrides) - valid_field_names)
    if unknown:
        names = ", ".join(unknown)
        raise ValueError(f"Unknown fields in tuning section '{section_name}': {names}")
    return replace(config_obj, **overrides)


def _load_tuning_overrides(tuning_path: str | Path | None) -> tuple[dict[str, Any], str | None]:
    candidate = Path(tuning_path) if tuning_path else DEFAULT_TUNING_PATH
    candidate = candidate.expanduser().resolve()

    if not candidate.exists():
        return {}, None

    data = json.loads(candidate.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Tuning file must contain a top-level JSON object.")

    return data, str(candidate)


def _merge_config(base: AppConfig, overrides: dict[str, Any], tuning_path: str | None) -> AppConfig:
    remaining = dict(overrides)

    general = base.general
    camera = base.camera
    tracker = base.tracker
    selector = base.selector
    ownership = base.ownership
    mouse_motion = base.mouse_motion
    mouse_click = base.mouse_click
    keyboard = base.keyboard
    ml = base.ml

    section_map = {
        "general": general,
        "camera": camera,
        "tracker": tracker,
        "selector": selector,
        "ownership": ownership,
        "mouse_motion": mouse_motion,
        "mouse_click": mouse_click,
        "keyboard": keyboard,
        "ml": ml,
    }

    for section_name, section_obj in section_map.items():
        section_overrides = remaining.pop(section_name, None)
        if section_overrides is None:
            continue
        if not isinstance(section_overrides, dict):
            raise ValueError(f"Tuning section '{section_name}' must be a JSON object.")
        section_map[section_name] = _replace_dataclass(section_obj, section_overrides, section_name=section_name)

    if remaining:
        unknown = ", ".join(sorted(remaining))
        raise ValueError(f"Unknown top-level tuning sections: {unknown}")

    return AppConfig(
        python_version=base.python_version,
        general=section_map["general"],
        camera=section_map["camera"],
        tracker=section_map["tracker"],
        selector=section_map["selector"],
        ownership=section_map["ownership"],
        mouse_motion=section_map["mouse_motion"],
        mouse_click=section_map["mouse_click"],
        keyboard=section_map["keyboard"],
        ml=section_map["ml"],
        tuning_path=tuning_path,
    )


def build_default_config(tuning_path: str | Path | None = None) -> AppConfig:
    base = AppConfig(
        python_version="3.11",
        general=GeneralConfig(),
        camera=CameraConfig(),
        tracker=HandTrackerConfig(),
        selector=HandSelectorConfig(),
        ownership=HandOwnershipConfig(),
        mouse_motion=MouseMotionConfig(),
        mouse_click=MouseClickConfig(),
        keyboard=KeyboardConfig(),
        ml=MLConfig(),
        tuning_path=None,
    )
    overrides, resolved_path = _load_tuning_overrides(tuning_path)
    return _merge_config(base, overrides, resolved_path)


def build_factory_default_config() -> AppConfig:
    return AppConfig(
        python_version="3.11",
        general=GeneralConfig(),
        camera=CameraConfig(),
        tracker=HandTrackerConfig(),
        selector=HandSelectorConfig(),
        ownership=HandOwnershipConfig(),
        mouse_motion=MouseMotionConfig(),
        mouse_click=MouseClickConfig(),
        keyboard=KeyboardConfig(),
        ml=MLConfig(),
        tuning_path=None,
    )


def tuning_snapshot(config: AppConfig) -> dict[str, Any]:
    return {
        "tuning_path": config.tuning_path,
        "general": asdict(config.general),
        "camera": asdict(config.camera),
        "ownership": asdict(config.ownership),
        "mouse_click": asdict(config.mouse_click),
        "keyboard": asdict(config.keyboard),
        "mouse_motion": asdict(config.mouse_motion),
        "ml": {
            "enabled": config.ml.enabled,
            "accepted_action_labels": config.ml.accepted_action_labels,
            "gate_min_p1": config.ml.gate_min_p1,
            "gate_min_margin": config.ml.gate_min_margin,
            "stability_window": config.ml.stability_window,
            "confirm_frames": config.ml.confirm_frames,
            "toggle_hold_seconds": config.ml.toggle_hold_seconds,
            "toggle_cooldown": config.ml.toggle_cooldown,
            "shortcut_cooldown": config.ml.shortcut_cooldown,
            "pre_hold_right_click_suppression": config.ml.pre_hold_right_click_suppression,
            "pre_hold_min_p1": config.ml.pre_hold_min_p1,
            "scaler_path": config.ml.scaler_path,
            "label_encoder_path": config.ml.label_encoder_path,
            "model_path": config.ml.model_path,
        },
    }
