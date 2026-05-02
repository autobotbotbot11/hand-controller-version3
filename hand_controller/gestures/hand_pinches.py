from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math

from ..config.settings import KeyboardConfig
from ..vision.models import DetectedHand


THUMB_TIP_IDX = 4
INDEX_TIP_IDX = 8
MIDDLE_TIP_IDX = 12
RING_TIP_IDX = 16
PINKY_TIP_IDX = 20


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
class PinchSignal:
    pressed: bool = False
    down: bool = False
    up: bool = False
    distance_px: float | None = None
    blocked_until_release: bool = False


@dataclass(frozen=True, slots=True)
class HandPinchState:
    hand_label: str
    index: PinchSignal = PinchSignal()
    middle: PinchSignal = PinchSignal()
    ring: PinchSignal = PinchSignal()
    pinky: PinchSignal = PinchSignal()


class HandPinchDetector:
    def __init__(self, settings: KeyboardConfig | None = None) -> None:
        self.settings = settings or KeyboardConfig()
        self._pressed: dict[str, dict[str, bool]] = {}
        self._blocked_until_release: dict[str, dict[str, bool]] = {}

    def reset(self) -> None:
        self._pressed.clear()
        self._blocked_until_release.clear()

    def analyze(
        self,
        *,
        hands: tuple[DetectedHand, ...] | list[DetectedHand],
        frame_width: int,
        frame_height: int,
        activation_allowed_by_hand: Mapping[str, bool] | None = None,
    ) -> dict[str, HandPinchState]:
        states: dict[str, HandPinchState] = {}
        visible_labels: set[str] = set()

        for hand in hands or ():
            label = hand.label
            visible_labels.add(label)
            prev = self._pressed.get(label, {})
            blocked = self._blocked_until_release.get(label, {})
            activation_allowed = True if activation_allowed_by_hand is None else bool(
                activation_allowed_by_hand.get(label, True)
            )

            index = self._build_signal(
                hand=hand,
                prev_pressed=bool(prev.get("index", False)),
                prev_blocked=bool(blocked.get("index", False)),
                activation_allowed=activation_allowed,
                frame_width=frame_width,
                frame_height=frame_height,
                end_idx=INDEX_TIP_IDX,
                base_threshold=self.settings.index_pinch_threshold_px,
                press_multiplier=self.settings.index_press_multiplier,
                release_multiplier=self.settings.index_release_multiplier,
            )
            middle = self._build_signal(
                hand=hand,
                prev_pressed=bool(prev.get("middle", False)),
                prev_blocked=bool(blocked.get("middle", False)),
                activation_allowed=activation_allowed,
                frame_width=frame_width,
                frame_height=frame_height,
                end_idx=MIDDLE_TIP_IDX,
                base_threshold=self.settings.middle_pinch_threshold_px,
                press_multiplier=self.settings.middle_press_multiplier,
                release_multiplier=self.settings.middle_release_multiplier,
            )
            ring = self._build_signal(
                hand=hand,
                prev_pressed=bool(prev.get("ring", False)),
                prev_blocked=bool(blocked.get("ring", False)),
                activation_allowed=activation_allowed,
                frame_width=frame_width,
                frame_height=frame_height,
                end_idx=RING_TIP_IDX,
                base_threshold=self.settings.ring_pinch_threshold_px,
                press_multiplier=self.settings.ring_press_multiplier,
                release_multiplier=self.settings.ring_release_multiplier,
            )
            pinky = self._build_signal(
                hand=hand,
                prev_pressed=bool(prev.get("pinky", False)),
                prev_blocked=bool(blocked.get("pinky", False)),
                activation_allowed=activation_allowed,
                frame_width=frame_width,
                frame_height=frame_height,
                end_idx=PINKY_TIP_IDX,
                base_threshold=self.settings.pinky_pinch_threshold_px,
                press_multiplier=self.settings.pinky_press_multiplier,
                release_multiplier=self.settings.pinky_release_multiplier,
            )

            self._pressed[label] = {
                "index": index.pressed,
                "middle": middle.pressed,
                "ring": ring.pressed,
                "pinky": pinky.pressed,
            }
            self._blocked_until_release[label] = {
                "index": index.blocked_until_release,
                "middle": middle.blocked_until_release,
                "ring": ring.blocked_until_release,
                "pinky": pinky.blocked_until_release,
            }
            states[label] = HandPinchState(
                hand_label=label,
                index=index,
                middle=middle,
                ring=ring,
                pinky=pinky,
            )

        for label in list(self._pressed):
            if label not in visible_labels:
                self._pressed.pop(label, None)
                self._blocked_until_release.pop(label, None)

        return states

    def _build_signal(
        self,
        *,
        hand: DetectedHand,
        prev_pressed: bool,
        prev_blocked: bool,
        activation_allowed: bool,
        frame_width: int,
        frame_height: int,
        end_idx: int,
        base_threshold: float,
        press_multiplier: float,
        release_multiplier: float,
    ) -> PinchSignal:
        distance = _distance_px(
            hand,
            frame_width,
            frame_height,
            THUMB_TIP_IDX,
            end_idx,
        )
        release_threshold = base_threshold * release_multiplier

        if not activation_allowed:
            return PinchSignal(
                distance_px=distance,
                blocked_until_release=True,
            )

        if prev_blocked:
            if distance <= release_threshold:
                return PinchSignal(
                    distance_px=distance,
                    blocked_until_release=True,
                )
            prev_pressed = False

        pressed = _update_press_state(
            prev_pressed=prev_pressed,
            distance_px=distance,
            press_threshold=base_threshold * press_multiplier,
            release_threshold=release_threshold,
        )
        return PinchSignal(
            pressed=pressed,
            down=pressed and not prev_pressed,
            up=prev_pressed and not pressed,
            distance_px=distance,
            blocked_until_release=False,
        )
