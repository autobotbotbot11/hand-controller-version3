from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class OverlayKeyRect:
    label: str
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True, slots=True)
class OverlayPointer:
    x: int
    y: int
    hand_label: str = ""
    thumb_x: int | None = None
    thumb_y: int | None = None
    index_x: int | None = None
    index_y: int | None = None
    show_dot: bool = True


@dataclass(frozen=True, slots=True)
class OverlayPayload:
    mode: str = "mouse"
    control_enabled: bool = True
    keyboard_visible: bool = False
    keyboard_dimmed: bool = False
    keyboard_keys: tuple[OverlayKeyRect, ...] = ()
    highlight_labels: frozenset[str] = frozenset()
    finger_points: tuple[OverlayPointer, ...] = ()
    skeleton_lines: tuple[tuple[int, int, int, int], ...] = ()
    mouse_status: str = ""
    keyboard_status: str = ""
    profile_label: str = ""
    footer_hint: str = ""
    selfie_frame: object | None = None
    gesture_command_text: str = ""
    helper_hint_text: str = ""
    debug_tags: tuple[str, ...] = field(default_factory=tuple)
