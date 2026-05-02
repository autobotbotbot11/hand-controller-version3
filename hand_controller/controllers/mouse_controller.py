from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math

from ..config.settings import MouseClickConfig, MouseMotionConfig
from ..gestures import MouseClickGestureState
from .actions import Action, Click, MouseDown, MouseUp, MoveRelative


@dataclass(slots=True)
class MouseMotionState:
    prev_x: float | None = None
    prev_y: float | None = None
    filtered_x: float | None = None
    filtered_y: float | None = None
    last_seen: float = 0.0
    deltas: deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=2))
    smooth_dx: float = 0.0
    smooth_dy: float = 0.0
    motion_awake: bool = False
    last_left_click: float = 0.0
    last_right_click: float = 0.0
    left_press_started: float | None = None
    left_second_tap_active: bool = False
    drag_active: bool = False


class MouseController:
    """Mouse controller for Phase 5.5: movement, click taps, and drag."""

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        motion_settings: MouseMotionConfig | None = None,
        click_settings: MouseClickConfig | None = None,
    ) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.motion_settings = motion_settings or MouseMotionConfig()
        self.click_settings = click_settings or MouseClickConfig()
        self.state = MouseMotionState(deltas=deque(maxlen=self.motion_settings.smoothing_window))

    def _reset_motion(self) -> None:
        self.state.prev_x = None
        self.state.prev_y = None
        self.state.filtered_x = None
        self.state.filtered_y = None
        self.state.last_seen = 0.0
        self.state.deltas.clear()
        self.state.smooth_dx = 0.0
        self.state.smooth_dy = 0.0
        self.state.motion_awake = False

    def _cancel_left_press(self) -> None:
        self.state.left_press_started = None
        self.state.left_second_tap_active = False

    def _release_drag_if_needed(self, actions: list[Action]) -> bool:
        if self.state.drag_active:
            actions.append(MouseUp(button="left"))
            self.state.drag_active = False
            self._cancel_left_press()
            return True
        return False

    def _filter_anchor(self, x: float, y: float) -> tuple[float, float]:
        alpha = self.motion_settings.anchor_alpha
        if self.state.filtered_x is None or self.state.filtered_y is None or alpha >= 0.999:
            self.state.filtered_x = x
            self.state.filtered_y = y
        else:
            self.state.filtered_x = alpha * x + (1.0 - alpha) * self.state.filtered_x
            self.state.filtered_y = alpha * y + (1.0 - alpha) * self.state.filtered_y
        return self.state.filtered_x, self.state.filtered_y

    def _apply_motion_gate(self, dx: float, dy: float) -> tuple[float, float]:
        magnitude = math.hypot(dx, dy)

        if self.state.motion_awake:
            if magnitude <= self.motion_settings.sleep_threshold_px:
                self.state.motion_awake = False
                self.state.smooth_dx = 0.0
                self.state.smooth_dy = 0.0
                self.state.deltas.clear()
                return 0.0, 0.0
        else:
            if magnitude < self.motion_settings.wake_threshold_px:
                return 0.0, 0.0
            self.state.motion_awake = True

        if abs(dx) < self.motion_settings.micro_jitter_px:
            dx = 0.0
        if abs(dy) < self.motion_settings.micro_jitter_px:
            dy = 0.0

        return dx, dy

    def _shape_delta(self, dx: float, dy: float) -> tuple[float, float]:
        magnitude = math.hypot(dx, dy)
        if magnitude <= 1e-6:
            return 0.0, 0.0

        if magnitude > self.motion_settings.spike_clamp_px:
            scale = self.motion_settings.spike_clamp_px / magnitude
            dx *= scale
            dy *= scale
            magnitude = self.motion_settings.spike_clamp_px

        shaped_magnitude = magnitude ** self.motion_settings.gain_exponent
        if magnitude >= self.motion_settings.accel_start_px:
            shaped_magnitude *= self.motion_settings.fast_gain

        scale = shaped_magnitude / magnitude
        return dx * scale, dy * scale

    def _build_status(
        self,
        *,
        base: str,
        dragging: bool,
        moving: bool,
    ) -> str:
        parts = [base]
        if dragging:
            parts.append("dragging")
        if moving:
            parts.append("moving")
        return " | ".join(parts)

    def _handle_click_state(
        self,
        click_state: MouseClickGestureState,
        now: float,
        *,
        right_click_allowed: bool,
    ) -> tuple[list[Action], str | None, bool]:
        actions: list[Action] = []
        status: str | None = None

        if (
            click_state.left_pressed
            and self.state.left_press_started is None
            and not self.state.drag_active
            and not self.state.left_second_tap_active
        ):
            self.state.left_press_started = now

        if click_state.left_down and not self.state.drag_active:
            if (
                self.state.last_left_click > 0.0
                and (now - self.state.last_left_click) <= min(
                    self.click_settings.double_click_interval,
                    self.click_settings.double_click_assist_window,
                )
                and (now - self.state.last_left_click) >= self.click_settings.click_cooldown
            ):
                actions.append(Click(button="left"))
                self.state.last_left_click = now
                self.state.left_press_started = None
                self.state.left_second_tap_active = True
                status = "Mouse | double click"
            else:
                self.state.left_press_started = now
                self.state.left_second_tap_active = False

        if (
            click_state.left_pressed
            and self.state.left_press_started is not None
            and not self.state.drag_active
            and not self.state.left_second_tap_active
            and (now - self.state.left_press_started) >= self.click_settings.left_hold_drag_seconds
        ):
            actions.append(MouseDown(button="left"))
            self.state.drag_active = True
            status = "Mouse | drag start"

        if click_state.left_up and (
            self.state.left_press_started is not None or self.state.left_second_tap_active
        ):
            press_duration = 0.0
            if self.state.left_press_started is not None:
                press_duration = now - self.state.left_press_started

            if self.state.drag_active:
                actions.append(MouseUp(button="left"))
                self.state.drag_active = False
                status = "Mouse | drag release"
            elif self.state.left_second_tap_active:
                self.state.left_second_tap_active = False
            elif press_duration < self.click_settings.left_hold_drag_seconds:
                if (now - self.state.last_left_click) >= self.click_settings.click_cooldown:
                    actions.append(Click(button="left"))
                    self.state.last_left_click = now
                    status = "Mouse | left click"
            self._cancel_left_press()

        if (
            click_state.right_down
            and right_click_allowed
            and not self.state.drag_active
            and (now - self.state.last_right_click) >= self.click_settings.click_cooldown
        ):
            actions.append(Click(button="right"))
            self.state.last_right_click = now
            if status is None:
                status = "Mouse | right click"

        freeze_for_click = (right_click_allowed and click_state.right_pressed) or (
            click_state.left_pressed and not self.state.drag_active
        )
        return actions, status, freeze_for_click

    def update(
        self,
        *,
        anchor_norm: tuple[float, float] | None,
        control_enabled: bool,
        movement_allowed: bool,
        click_enabled: bool,
        press_activation_allowed: bool = True,
        right_click_allowed: bool = True,
        click_state: MouseClickGestureState | None,
        now: float,
    ) -> tuple[list[Action], str]:
        actions: list[Action] = []
        click_state = click_state or MouseClickGestureState()

        if anchor_norm is None:
            released_drag = self._release_drag_if_needed(actions)
            self._cancel_left_press()
            self._reset_motion()
            return actions, "Mouse | drag release" if released_drag else "Mouse | no active hand"

        if not control_enabled:
            released_drag = self._release_drag_if_needed(actions)
            self._cancel_left_press()
            self._reset_motion()
            return actions, "Mouse | drag release" if released_drag else "Mouse | control off"

        click_status: str | None = None
        freeze_for_click = False

        if not click_enabled:
            released_drag = self._release_drag_if_needed(actions)
            self._cancel_left_press()
            if released_drag:
                click_status = "Mouse | drag release"
        elif not press_activation_allowed:
            if not self.state.drag_active:
                self._cancel_left_press()
        else:
            click_actions, click_status, freeze_for_click = self._handle_click_state(
                click_state,
                now,
                right_click_allowed=right_click_allowed,
            )
            actions.extend(click_actions)

        if freeze_for_click:
            self._reset_motion()
            return actions, click_status or "Mouse | click ready"

        if not movement_allowed:
            self._reset_motion()
            return actions, click_status or "Mouse | movement frozen"

        x, y = anchor_norm

        if self.state.last_seen > 0.0 and (now - self.state.last_seen) > self.motion_settings.move_timeout:
            self._reset_motion()

        filtered_x, filtered_y = self._filter_anchor(x, y)
        self.state.last_seen = now

        if self.state.prev_x is not None and self.state.prev_y is not None:
            raw_dx = (filtered_x - self.state.prev_x) * self.screen_w * self.motion_settings.sensitivity
            raw_dy = (filtered_y - self.state.prev_y) * self.screen_h * self.motion_settings.sensitivity

            jump_magnitude = math.hypot(raw_dx, raw_dy)
            if jump_magnitude >= self.motion_settings.reanchor_distance_px:
                self._reset_motion()
                self.state.prev_x = filtered_x
                self.state.prev_y = filtered_y
                return actions, click_status or self._build_status(
                    base="Mouse | re-anchor",
                    dragging=self.state.drag_active,
                    moving=False,
                )

            gated_dx, gated_dy = self._apply_motion_gate(raw_dx, raw_dy)
            shaped_dx, shaped_dy = self._shape_delta(gated_dx, gated_dy)

            alpha = self.motion_settings.ema_alpha if self.state.motion_awake else 1.0
            self.state.smooth_dx = alpha * shaped_dx + (1.0 - alpha) * self.state.smooth_dx
            self.state.smooth_dy = alpha * shaped_dy + (1.0 - alpha) * self.state.smooth_dy

            self.state.deltas.append((self.state.smooth_dx, self.state.smooth_dy))
            avg_dx = sum(delta[0] for delta in self.state.deltas) / len(self.state.deltas)
            avg_dy = sum(delta[1] for delta in self.state.deltas) / len(self.state.deltas)

            avg_dx = max(-self.motion_settings.max_step_px, min(self.motion_settings.max_step_px, avg_dx))
            avg_dy = max(-self.motion_settings.max_step_px, min(self.motion_settings.max_step_px, avg_dy))

            move_dx = int(round(avg_dx))
            move_dy = int(round(avg_dy))

            if move_dx != 0 or move_dy != 0:
                actions.append(MoveRelative(move_dx, move_dy))

        self.state.prev_x = filtered_x
        self.state.prev_y = filtered_y

        if click_status is not None:
            base_status = click_status
        elif self.state.drag_active or self.state.motion_awake:
            base_status = "Mouse"
        else:
            base_status = "Mouse | ready"

        return actions, self._build_status(
            base=base_status,
            dragging=self.state.drag_active,
            moving=self.state.motion_awake,
        )
