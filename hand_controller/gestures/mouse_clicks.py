from __future__ import annotations

from dataclasses import dataclass
import math

from ..config.settings import MouseClickConfig
from ..vision.models import DetectedHand


THUMB_TIP_IDX = 4
INDEX_TIP_IDX = 8
MIDDLE_TIP_IDX = 12


def _distance_px(
    hand: DetectedHand,
    frame_width: int,
    frame_height: int,
    start_idx: int,
    end_idx: int,
) -> float:
    start = hand.landmark(start_idx)
    end = hand.landmark(end_idx)
    dx = (start.x - end.x) * frame_width
    dy = (start.y - end.y) * frame_height
    return math.hypot(dx, dy)


def _update_press_state(*, prev_pressed: bool, distance_px: float, press_threshold: float, release_threshold: float) -> bool:
    if prev_pressed:
        return distance_px <= release_threshold
    return distance_px <= press_threshold


@dataclass(frozen=True, slots=True)
class MouseClickGestureState:
    left_pressed: bool = False
    left_down: bool = False
    left_up: bool = False
    right_pressed: bool = False
    right_down: bool = False
    right_up: bool = False
    left_distance_px: float | None = None
    right_distance_px: float | None = None

    @property
    def freeze_active(self) -> bool:
        return self.left_pressed or self.right_pressed


class MouseClickDetector:
    def __init__(self, settings: MouseClickConfig | None = None) -> None:
        self.settings = settings or MouseClickConfig()
        self._index_pressed: dict[str, bool] = {}
        self._middle_pressed: dict[str, bool] = {}
        self._blocked_until_release: dict[str, dict[str, bool]] = {}

    def reset(self) -> None:
        self._index_pressed.clear()
        self._middle_pressed.clear()
        self._blocked_until_release.clear()

    def analyze(
        self,
        *,
        active_hand: DetectedHand | None,
        frame_width: int,
        frame_height: int,
        activation_allowed: bool = True,
    ) -> MouseClickGestureState:
        if active_hand is None:
            self.reset()
            return MouseClickGestureState()

        label = active_hand.label
        left_press_threshold = self.settings.left_pinch_threshold_px * self.settings.left_press_multiplier
        left_release_threshold = self.settings.left_pinch_threshold_px * self.settings.left_release_multiplier
        right_press_threshold = self.settings.right_pinch_threshold_px * self.settings.right_press_multiplier
        right_release_threshold = self.settings.right_pinch_threshold_px * self.settings.right_release_multiplier

        left_distance = _distance_px(
            active_hand,
            frame_width,
            frame_height,
            THUMB_TIP_IDX,
            INDEX_TIP_IDX,
        )
        right_distance = _distance_px(
            active_hand,
            frame_width,
            frame_height,
            THUMB_TIP_IDX,
            MIDDLE_TIP_IDX,
        )

        if not activation_allowed:
            self._index_pressed = {label: False}
            self._middle_pressed = {label: False}
            self._blocked_until_release = {label: {"index": True, "middle": True}}
            return MouseClickGestureState(
                left_distance_px=left_distance,
                right_distance_px=right_distance,
            )

        blocked = dict(self._blocked_until_release.get(label, {}))
        left_pressed, left_down, left_up, blocked_left = self._resolve_press_signal(
            prev_pressed=bool(self._index_pressed.get(label, False)),
            distance_px=left_distance,
            press_threshold=left_press_threshold,
            release_threshold=left_release_threshold,
            blocked=bool(blocked.get("index", False)),
        )
        right_pressed, right_down, right_up, blocked_right = self._resolve_press_signal(
            prev_pressed=bool(self._middle_pressed.get(label, False)),
            distance_px=right_distance,
            press_threshold=right_press_threshold,
            release_threshold=right_release_threshold,
            blocked=bool(blocked.get("middle", False)),
        )

        self._index_pressed = {label: left_pressed}
        self._middle_pressed = {label: right_pressed}
        self._blocked_until_release = {
            label: {
                "index": blocked_left,
                "middle": blocked_right,
            }
        }

        return MouseClickGestureState(
            left_pressed=left_pressed,
            left_down=left_down,
            left_up=left_up,
            right_pressed=right_pressed,
            right_down=right_down,
            right_up=right_up,
            left_distance_px=left_distance,
            right_distance_px=right_distance,
        )

    def _resolve_press_signal(
        self,
        *,
        prev_pressed: bool,
        distance_px: float,
        press_threshold: float,
        release_threshold: float,
        blocked: bool,
    ) -> tuple[bool, bool, bool, bool]:
        if blocked:
            if distance_px <= release_threshold:
                return False, False, False, True
            return False, False, False, False

        pressed = _update_press_state(
            prev_pressed=prev_pressed,
            distance_px=distance_px,
            press_threshold=press_threshold,
            release_threshold=release_threshold,
        )
        down = pressed and not prev_pressed
        up = prev_pressed and not pressed
        return pressed, down, up, False
