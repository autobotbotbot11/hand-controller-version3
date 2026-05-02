from __future__ import annotations


ML_LABEL_IDLE = "idle"
ML_LABEL_HOLD = "hold"
ML_LABEL_TOGGLE = "toggle"
ML_LABEL_UNDO = "undo"
ML_LABEL_REDO = "redo"

ML_LABEL_LEFT_CLICK = "left_click"
ML_LABEL_RIGHT_CLICK = "right_click"

ACTIVE_ACTION_LABELS = (
    ML_LABEL_TOGGLE,
    ML_LABEL_HOLD,
    ML_LABEL_UNDO,
    ML_LABEL_REDO,
)

IGNORED_BEHAVIOR_LABELS = (
    ML_LABEL_LEFT_CLICK,
    ML_LABEL_RIGHT_CLICK,
    ML_LABEL_IDLE,
)


def canonicalize_label(label: str | None) -> str:
    raw = (label or ML_LABEL_IDLE).strip().lower()
    raw = raw.replace("-", " ").replace("__", "_")
    raw = " ".join(raw.split())

    special = {
        "left click": ML_LABEL_LEFT_CLICK,
        "right click": ML_LABEL_RIGHT_CLICK,
        "double click": ML_LABEL_LEFT_CLICK,
        "double left click": ML_LABEL_LEFT_CLICK,
        "2 fast left click": ML_LABEL_LEFT_CLICK,
        "2_fast_left_click": ML_LABEL_LEFT_CLICK,
        "leftclick": ML_LABEL_LEFT_CLICK,
        "rightclick": ML_LABEL_RIGHT_CLICK,
        "redo": ML_LABEL_REDO,
        "undo": ML_LABEL_UNDO,
        "toggle": ML_LABEL_TOGGLE,
        "hold": ML_LABEL_HOLD,
        "idle": ML_LABEL_IDLE,
    }
    if raw in special:
        return special[raw]

    raw = raw.replace(" ", "_")
    if raw in special:
        return special[raw]
    if "left" in raw and "click" in raw:
        return ML_LABEL_LEFT_CLICK
    if "right" in raw and "click" in raw:
        return ML_LABEL_RIGHT_CLICK
    return raw
