from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Mode(str, Enum):
    MOUSE = "mouse"
    KEYBOARD = "keyboard"


@dataclass(slots=True)
class RuntimeState:
    control_enabled: bool = True
    mode: Mode = Mode.MOUSE
    latest_ml_label: str = "idle"
    active_hand_label: str | None = None
    palm_facing: bool = False
    hold_active: bool = False
    movement_frozen: bool = False
