from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from ..config.settings import MLConfig
from ..controllers.actions import Action, Hotkey
from ..runtime.state import Mode, RuntimeState
from .labels import ML_LABEL_HOLD, ML_LABEL_IDLE, ML_LABEL_REDO, ML_LABEL_TOGGLE, ML_LABEL_UNDO
from .predictor import MLPrediction


@dataclass(frozen=True, slots=True)
class MLControlUpdate:
    stable_label: str
    actions: tuple[Action, ...]
    control_enabled: bool
    hold_active: bool
    status: str


class MLControlAdapter:
    def __init__(self, config: MLConfig) -> None:
        self.config = config
        self._memory: deque[str] = deque(maxlen=config.stability_window)
        self._prev_stable_label = ML_LABEL_IDLE
        self._toggle_started_at: float | None = None
        self._toggle_fired_for_hold = False
        self._last_toggle_time = 0.0
        self._last_shortcut_time = 0.0

    def _is_confirmed(self, label: str) -> bool:
        if label == ML_LABEL_IDLE:
            return False
        needed = max(1, self.config.confirm_frames)
        if len(self._memory) < needed:
            return False
        recent = list(self._memory)[-needed:]
        return all(entry == label for entry in recent)

    def update(self, prediction: MLPrediction, state: RuntimeState, now: float) -> MLControlUpdate:
        current_label = prediction.label if prediction.available else ML_LABEL_IDLE
        self._memory.append(current_label)

        if self._is_confirmed(ML_LABEL_TOGGLE):
            stable_label = ML_LABEL_TOGGLE
        elif self._is_confirmed(ML_LABEL_HOLD):
            stable_label = ML_LABEL_HOLD
        elif self._is_confirmed(ML_LABEL_UNDO):
            stable_label = ML_LABEL_UNDO
        elif self._is_confirmed(ML_LABEL_REDO):
            stable_label = ML_LABEL_REDO
        else:
            stable_label = ML_LABEL_IDLE

        actions: list[Action] = []
        toggled = False
        toggle_hold_progress: float | None = None

        if stable_label == ML_LABEL_TOGGLE:
            if self._toggle_started_at is None:
                self._toggle_started_at = now
                self._toggle_fired_for_hold = False
            toggle_hold_progress = max(0.0, now - self._toggle_started_at)
            if (
                not self._toggle_fired_for_hold
                and toggle_hold_progress >= self.config.toggle_hold_seconds
                and (now - self._last_toggle_time) >= self.config.toggle_cooldown
            ):
                state.control_enabled = not state.control_enabled
                self._last_toggle_time = now
                self._toggle_fired_for_hold = True
                toggled = True
        else:
            self._toggle_started_at = None
            self._toggle_fired_for_hold = False

        if state.control_enabled and state.mode == Mode.MOUSE:
            if (
                stable_label == ML_LABEL_UNDO
                and self._prev_stable_label != ML_LABEL_UNDO
                and (now - self._last_shortcut_time) >= self.config.shortcut_cooldown
            ):
                actions.append(Hotkey(keys=("ctrl", "z")))
                self._last_shortcut_time = now
            elif (
                stable_label == ML_LABEL_REDO
                and self._prev_stable_label != ML_LABEL_REDO
                and (now - self._last_shortcut_time) >= self.config.shortcut_cooldown
            ):
                actions.append(Hotkey(keys=("ctrl", "y")))
                self._last_shortcut_time = now

        hold_active = state.control_enabled and state.mode == Mode.MOUSE and stable_label == ML_LABEL_HOLD

        state.latest_ml_label = stable_label
        state.hold_active = hold_active
        self._prev_stable_label = stable_label

        if not prediction.available:
            status = prediction.reason or "ML unavailable"
        else:
            status = stable_label
            if stable_label == ML_LABEL_TOGGLE and toggle_hold_progress is not None and not toggled:
                status += f" | hold {toggle_hold_progress:.2f}/{self.config.toggle_hold_seconds:.2f}s"
            if toggled:
                status += " | toggled"

        return MLControlUpdate(
            stable_label=stable_label,
            actions=tuple(actions),
            control_enabled=state.control_enabled,
            hold_active=hold_active,
            status=status,
        )
