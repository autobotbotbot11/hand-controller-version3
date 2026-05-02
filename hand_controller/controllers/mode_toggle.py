from __future__ import annotations

from dataclasses import dataclass

from ..config.settings import KeyboardConfig
from ..gestures.hand_pinches import HandPinchState
from ..runtime.state import Mode, RuntimeState
from ..vision.models import DetectedHand


@dataclass(frozen=True, slots=True)
class ModeToggleUpdate:
    toggled: bool
    mode: Mode
    status: str


class KeyboardModeToggleController:
    def __init__(self, settings: KeyboardConfig | None = None) -> None:
        self.settings = settings or KeyboardConfig()
        self._tracking_hand_label: str | None = None
        self._hold_started_at: float | None = None
        self._hold_consumed = False
        self._last_toggle_time = -1e9

    def reset(self) -> None:
        self._tracking_hand_label = None
        self._hold_started_at = None
        self._hold_consumed = False

    def update(
        self,
        *,
        state: RuntimeState,
        active_hand: DetectedHand | None,
        palm_facing: bool,
        pinch_state: HandPinchState | None,
        now: float,
    ) -> ModeToggleUpdate:
        if not state.control_enabled:
            self.reset()
            return ModeToggleUpdate(toggled=False, mode=state.mode, status="control off")

        if not self.settings.virtual_keyboard_enabled:
            if state.mode == Mode.KEYBOARD:
                state.mode = Mode.MOUSE
            self.reset()
            return ModeToggleUpdate(toggled=False, mode=state.mode, status="keyboard disabled")

        if active_hand is None or pinch_state is None:
            self.reset()
            return ModeToggleUpdate(toggled=False, mode=state.mode, status="toggle idle")

        hand_label = active_hand.label
        if pinch_state.hand_label != hand_label:
            self.reset()
            return ModeToggleUpdate(toggled=False, mode=state.mode, status="toggle idle")

        eligible = pinch_state.ring.pressed and not pinch_state.index.pressed
        if self.settings.require_palm_facing_for_toggle and not palm_facing:
            eligible = False

        if not eligible:
            self.reset()
            return ModeToggleUpdate(toggled=False, mode=state.mode, status="toggle idle")

        if self._tracking_hand_label != hand_label or self._hold_started_at is None:
            self._tracking_hand_label = hand_label
            self._hold_started_at = now
            self._hold_consumed = False

        held_for = max(0.0, now - self._hold_started_at)
        if self._hold_consumed:
            return ModeToggleUpdate(toggled=False, mode=state.mode, status="toggle armed")

        if held_for < self.settings.mode_toggle_hold_seconds:
            return ModeToggleUpdate(
                toggled=False,
                mode=state.mode,
                status=f"toggle hold {held_for:.2f}/{self.settings.mode_toggle_hold_seconds:.2f}s",
            )

        cooldown_remaining = self.settings.mode_toggle_cooldown_seconds - (now - self._last_toggle_time)
        if cooldown_remaining > 0.0:
            return ModeToggleUpdate(
                toggled=False,
                mode=state.mode,
                status=f"toggle cooldown {cooldown_remaining:.2f}s",
            )

        state.mode = Mode.KEYBOARD if state.mode == Mode.MOUSE else Mode.MOUSE
        self._last_toggle_time = now
        self._hold_consumed = True
        return ModeToggleUpdate(toggled=True, mode=state.mode, status=f"mode={state.mode.value} | toggled")
