from __future__ import annotations

from dataclasses import dataclass
import math

from ..config.settings import MouseClickConfig, MouseMotionConfig
from ..gestures import MouseClickGestureState
from .actions import Action, Click, DoubleClick, MouseDown, MouseUp, MoveTo


@dataclass(slots=True)
class MouseMotionState:
    prev_x: float | None = None
    prev_y: float | None = None
    filtered_x: float | None = None
    filtered_y: float | None = None
    last_seen: float = 0.0
    motion_awake: bool = False
    last_left_click: float = 0.0
    last_right_click: float = 0.0
    left_press_started: float | None = None
    left_second_tap_active: bool = False
    drag_active: bool = False
    aim_lock_x: float | None = None
    aim_lock_y: float | None = None
    mapping_offset_x: float = 0.0
    mapping_offset_y: float = 0.0
    clutch_active: bool = False
    clutch_lock_x: float | None = None
    clutch_lock_y: float | None = None


class MouseController:
    """Mouse controller for absolute pointer movement, click taps, and drag."""

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
        self.state = MouseMotionState()

    def _reset_motion(self) -> None:
        self.state.prev_x = None
        self.state.prev_y = None
        self.state.filtered_x = None
        self.state.filtered_y = None
        self.state.last_seen = 0.0
        self.state.motion_awake = False
        self._clear_aim_lock()
        self._clear_clutch_lock()

    def _clear_aim_lock(self) -> None:
        self.state.aim_lock_x = None
        self.state.aim_lock_y = None

    def _clear_clutch_lock(self) -> None:
        self.state.clutch_active = False
        self.state.clutch_lock_x = None
        self.state.clutch_lock_y = None

    def _mapping_offset_active(self) -> bool:
        return math.hypot(self.state.mapping_offset_x, self.state.mapping_offset_y) >= 0.5

    def _mapping_status(self) -> str:
        return "mapping=offset" if self._mapping_offset_active() else "mapping=direct"

    def _clear_mapping_offset(self) -> None:
        self.state.mapping_offset_x = 0.0
        self.state.mapping_offset_y = 0.0

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

    def _screen_target(self, pointer_norm: tuple[float, float]) -> tuple[int, int]:
        x_norm = max(0.0, min(1.0, pointer_norm[0]))
        y_norm = max(0.0, min(1.0, pointer_norm[1]))
        max_x = max(0, self.screen_w - 1)
        max_y = max(0, self.screen_h - 1)
        return (
            max(0, min(max_x, int(round(x_norm * max_x)))),
            max(0, min(max_y, int(round(y_norm * max_y)))),
        )

    def _mapped_target(self, pointer_norm: tuple[float, float]) -> tuple[int, int]:
        raw_x, raw_y = self._screen_target(pointer_norm)
        return self._clamp_screen_point(
            raw_x + self.state.mapping_offset_x,
            raw_y + self.state.mapping_offset_y,
        )

    def _clamp_screen_point(self, x: float, y: float) -> tuple[int, int]:
        max_x = max(0, self.screen_w - 1)
        max_y = max(0, self.screen_h - 1)
        return (
            max(0, min(max_x, int(round(x)))),
            max(0, min(max_y, int(round(y)))),
        )

    def _current_cursor_target(self, pointer_norm: tuple[float, float]) -> tuple[int, int]:
        if self.state.prev_x is not None and self.state.prev_y is not None:
            return self._clamp_screen_point(self.state.prev_x, self.state.prev_y)
        if self.state.filtered_x is not None and self.state.filtered_y is not None:
            return self._clamp_screen_point(self.state.filtered_x, self.state.filtered_y)
        return self._mapped_target(pointer_norm)

    def _set_stationary_cursor_state(self, x: int, y: int, now: float) -> None:
        self.state.prev_x = float(x)
        self.state.prev_y = float(y)
        self.state.filtered_x = float(x)
        self.state.filtered_y = float(y)
        self.state.last_seen = now
        self.state.motion_awake = False

    def _reset_mapping_to_direct(self, pointer_norm: tuple[float, float], now: float) -> MoveTo:
        self._clear_mapping_offset()
        self._clear_aim_lock()
        self._clear_clutch_lock()
        x, y = self._screen_target(pointer_norm)
        self._set_stationary_cursor_state(x, y, now)
        return MoveTo(x, y)

    def _ensure_clutch_lock(self, pointer_norm: tuple[float, float], now: float) -> MoveTo | None:
        emit_move = False
        if self.state.clutch_lock_x is None or self.state.clutch_lock_y is None:
            lock_x, lock_y = self._current_cursor_target(pointer_norm)
            if self.state.prev_x is None or self.state.prev_y is None:
                emit_move = True
            self.state.clutch_lock_x = float(lock_x)
            self.state.clutch_lock_y = float(lock_y)
        else:
            lock_x, lock_y = self._clamp_screen_point(self.state.clutch_lock_x, self.state.clutch_lock_y)

        self.state.clutch_active = True
        self._set_stationary_cursor_state(lock_x, lock_y, now)
        return MoveTo(lock_x, lock_y) if emit_move else None

    def _commit_clutch_offset(self, pointer_norm: tuple[float, float], now: float) -> bool:
        if not self.state.clutch_active:
            return False

        if self.state.clutch_lock_x is None or self.state.clutch_lock_y is None:
            self._clear_clutch_lock()
            return False

        lock_x, lock_y = self._clamp_screen_point(self.state.clutch_lock_x, self.state.clutch_lock_y)
        raw_x, raw_y = self._screen_target(pointer_norm)
        offset_x = float(lock_x - raw_x)
        offset_y = float(lock_y - raw_y)
        offset_applied = False
        min_offset = max(8.0, self.motion_settings.wake_threshold_px * 2.0)
        if math.hypot(offset_x, offset_y) < min_offset:
            self._clear_mapping_offset()
        else:
            self.state.mapping_offset_x = offset_x
            self.state.mapping_offset_y = offset_y
            offset_applied = True

        self._set_stationary_cursor_state(lock_x, lock_y, now)
        self._clear_clutch_lock()
        return offset_applied

    def _ensure_aim_lock(self, pointer_norm: tuple[float, float], now: float) -> MoveTo | None:
        emit_move = False

        if self.state.aim_lock_x is None or self.state.aim_lock_y is None:
            lock_x, lock_y = self._current_cursor_target(pointer_norm)
            if self.state.prev_x is None or self.state.prev_y is None:
                emit_move = True
            self.state.aim_lock_x = float(lock_x)
            self.state.aim_lock_y = float(lock_y)
        else:
            lock_x, lock_y = self._clamp_screen_point(self.state.aim_lock_x, self.state.aim_lock_y)

        self._set_stationary_cursor_state(lock_x, lock_y, now)
        return MoveTo(lock_x, lock_y) if emit_move else None

    def _filter_target(self, x: float, y: float) -> tuple[float, float]:
        alpha = max(0.0, min(1.0, self.motion_settings.ema_alpha))
        if self.state.filtered_x is None or self.state.filtered_y is None or alpha >= 0.999:
            self.state.filtered_x = x
            self.state.filtered_y = y
        else:
            self.state.filtered_x = alpha * x + (1.0 - alpha) * self.state.filtered_x
            self.state.filtered_y = alpha * y + (1.0 - alpha) * self.state.filtered_y
        return self.state.filtered_x, self.state.filtered_y

    def _should_emit_move(self, x: int, y: int) -> bool:
        if self.state.prev_x is None or self.state.prev_y is None:
            self.state.motion_awake = True
            return True

        distance = math.hypot(x - self.state.prev_x, y - self.state.prev_y)
        if self.state.motion_awake:
            if distance <= self.motion_settings.sleep_threshold_px:
                self.state.motion_awake = False
                return False
            return True

        if distance < self.motion_settings.wake_threshold_px:
            return False
        self.state.motion_awake = True
        return True

    def _build_status(
        self,
        *,
        base: str,
        dragging: bool,
        moving: bool,
    ) -> str:
        parts = [base]
        parts.append(self._mapping_status())
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
                self.state.left_second_tap_active = True
                self.state.left_press_started = now
                status = "Mouse | double click ready"
            else:
                self.state.left_press_started = now
                self.state.left_second_tap_active = False

        if (
            click_state.left_pressed
            and self.state.left_press_started is not None
            and not self.state.drag_active
            and (now - self.state.left_press_started) >= self.click_settings.left_hold_drag_seconds
        ):
            actions.append(MouseDown(button="left"))
            self.state.drag_active = True
            self.state.left_second_tap_active = False
            self.state.last_left_click = 0.0
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
                actions.append(DoubleClick())
                self.state.last_left_click = now
                status = "Mouse | double click"
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
        pointer_norm: tuple[float, float] | None,
        control_enabled: bool,
        movement_allowed: bool,
        click_enabled: bool,
        clutch_active: bool = False,
        reset_mapping: bool = False,
        press_activation_allowed: bool = True,
        right_click_allowed: bool = True,
        click_state: MouseClickGestureState | None,
        now: float,
    ) -> tuple[list[Action], str]:
        actions: list[Action] = []
        click_state = click_state or MouseClickGestureState()

        if pointer_norm is None:
            released_drag = self._release_drag_if_needed(actions)
            self._cancel_left_press()
            self._reset_motion()
            return actions, "Mouse | drag release" if released_drag else "Mouse | no active hand"

        if not control_enabled:
            released_drag = self._release_drag_if_needed(actions)
            self._cancel_left_press()
            self._reset_motion()
            return actions, "Mouse | drag release" if released_drag else "Mouse | control off"

        if reset_mapping:
            actions.append(self._reset_mapping_to_direct(pointer_norm, now))
            return actions, f"Mouse | cursor reset | {self._mapping_status()}"

        if clutch_active:
            released_drag = self._release_drag_if_needed(actions)
            self._cancel_left_press()
            lock_move = self._ensure_clutch_lock(pointer_norm, now)
            if lock_move is not None:
                actions.insert(0, lock_move)
            return actions, (
                f"Mouse | drag release | {self._mapping_status()}"
                if released_drag
                else f"Mouse | clutch | {self._mapping_status()}"
            )

        clutch_repositioned = False
        if self.state.clutch_active:
            clutch_repositioned = self._commit_clutch_offset(pointer_norm, now)

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
            lock_move = self._ensure_aim_lock(pointer_norm, now)
            if lock_move is not None:
                actions.insert(0, lock_move)
            return actions, click_status or "Mouse | click ready"

        self._clear_aim_lock()

        if not movement_allowed:
            self._reset_motion()
            return actions, click_status or "Mouse | movement frozen"

        if self.state.last_seen > 0.0 and (now - self.state.last_seen) > self.motion_settings.move_timeout:
            self._reset_motion()

        target_x, target_y = self._mapped_target(pointer_norm)
        filtered_x, filtered_y = self._filter_target(float(target_x), float(target_y))
        self.state.last_seen = now
        max_x = max(0, self.screen_w - 1)
        max_y = max(0, self.screen_h - 1)
        move_x = max(0, min(max_x, int(round(filtered_x))))
        move_y = max(0, min(max_y, int(round(filtered_y))))

        if self._should_emit_move(move_x, move_y):
            actions.append(MoveTo(move_x, move_y))
            self.state.prev_x = float(move_x)
            self.state.prev_y = float(move_y)

        if click_status is not None:
            base_status = click_status
        elif clutch_repositioned:
            base_status = "Mouse | hand repositioned"
        elif self.state.drag_active or self.state.motion_awake:
            base_status = "Mouse"
        else:
            base_status = "Mouse | ready"

        return actions, self._build_status(
            base=base_status,
            dragging=self.state.drag_active,
            moving=self.state.motion_awake,
        )
