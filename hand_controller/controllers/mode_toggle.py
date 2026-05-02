from __future__ import annotations

from dataclasses import dataclass

from ..config.settings import KeyboardConfig
from ..gestures.hand_pinches import HandPinchState
from ..runtime.state import RuntimeState
from ..vision.models import DetectedHand


@dataclass(frozen=True, slots=True)
class KeyboardOverlayToggleUpdate:
    toggled: bool
    keyboard_visible: bool
    status: str


class KeyboardOverlayToggleController:
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
    ) -> KeyboardOverlayToggleUpdate:
        if not state.control_enabled:
            self.reset()
            return KeyboardOverlayToggleUpdate(
                toggled=False,
                keyboard_visible=state.keyboard_visible,
                status="control off",
            )

        if not self.settings.virtual_keyboard_enabled:
            state.keyboard_visible = False
            self.reset()
            return KeyboardOverlayToggleUpdate(toggled=False, keyboard_visible=False, status="keyboard disabled")

        if active_hand is None or pinch_state is None:
            self.reset()
            return KeyboardOverlayToggleUpdate(
                toggled=False,
                keyboard_visible=state.keyboard_visible,
                status="toggle idle",
            )

        hand_label = active_hand.label
        if pinch_state.hand_label != hand_label:
            self.reset()
            return KeyboardOverlayToggleUpdate(
                toggled=False,
                keyboard_visible=state.keyboard_visible,
                status="toggle idle",
            )

        eligible = pinch_state.ring.pressed and not pinch_state.index.pressed
        if self.settings.require_palm_facing_for_toggle and not palm_facing:
            eligible = False

        if not eligible:
            self.reset()
            return KeyboardOverlayToggleUpdate(
                toggled=False,
                keyboard_visible=state.keyboard_visible,
                status="toggle idle",
            )

        if self._tracking_hand_label != hand_label or self._hold_started_at is None:
            self._tracking_hand_label = hand_label
            self._hold_started_at = now
            self._hold_consumed = False

        held_for = max(0.0, now - self._hold_started_at)
        if self._hold_consumed:
            return KeyboardOverlayToggleUpdate(
                toggled=False,
                keyboard_visible=state.keyboard_visible,
                status="toggle armed",
            )

        if held_for < self.settings.mode_toggle_hold_seconds:
            return KeyboardOverlayToggleUpdate(
                toggled=False,
                keyboard_visible=state.keyboard_visible,
                status=f"toggle hold {held_for:.2f}/{self.settings.mode_toggle_hold_seconds:.2f}s",
            )

        cooldown_remaining = self.settings.mode_toggle_cooldown_seconds - (now - self._last_toggle_time)
        if cooldown_remaining > 0.0:
            return KeyboardOverlayToggleUpdate(
                toggled=False,
                keyboard_visible=state.keyboard_visible,
                status=f"toggle cooldown {cooldown_remaining:.2f}s",
            )

        state.keyboard_visible = not state.keyboard_visible
        self._last_toggle_time = now
        self._hold_consumed = True
        status = f"keyboard={'visible' if state.keyboard_visible else 'hidden'} | toggled"
        return KeyboardOverlayToggleUpdate(
            toggled=True,
            keyboard_visible=state.keyboard_visible,
            status=status,
        )


ModeToggleUpdate = KeyboardOverlayToggleUpdate
KeyboardModeToggleController = KeyboardOverlayToggleController
