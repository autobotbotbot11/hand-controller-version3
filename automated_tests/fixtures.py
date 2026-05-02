from __future__ import annotations

from hand_controller.gestures.hand_pinches import HandPinchState, PinchSignal
from hand_controller.vision.models import DetectedHand, LandmarkPoint


DEFAULT_HAND_POINTS = [
    (0.50, 0.80, 0.00),
    (0.42, 0.72, 0.00),
    (0.36, 0.65, 0.00),
    (0.30, 0.58, 0.00),
    (0.24, 0.52, 0.00),
    (0.34, 0.55, 0.00),
    (0.33, 0.45, 0.00),
    (0.32, 0.35, 0.00),
    (0.31, 0.25, 0.00),
    (0.50, 0.52, 0.00),
    (0.50, 0.40, 0.00),
    (0.50, 0.29, 0.00),
    (0.50, 0.18, 0.00),
    (0.62, 0.55, 0.00),
    (0.64, 0.45, 0.00),
    (0.66, 0.35, 0.00),
    (0.68, 0.25, 0.00),
    (0.74, 0.58, 0.00),
    (0.78, 0.50, 0.00),
    (0.81, 0.42, 0.00),
    (0.84, 0.34, 0.00),
]


def make_hand(
    *,
    label: str = "Right",
    score: float = 0.99,
    overrides: dict[int, tuple[float, float, float]] | None = None,
) -> DetectedHand:
    points = list(DEFAULT_HAND_POINTS)
    for index, value in (overrides or {}).items():
        points[index] = value

    landmarks = tuple(
        LandmarkPoint(x=float(x), y=float(y), z=float(z))
        for x, y, z in points
    )
    return DetectedHand(label=label, score=score, landmarks=landmarks)


def make_box_hand(
    *,
    label: str,
    center_x: float,
    center_y: float,
    spread_x: float,
    spread_y: float,
    score: float = 0.99,
) -> DetectedHand:
    points: list[LandmarkPoint] = []
    for index in range(21):
        col = index % 5
        row = index // 5
        x = center_x + spread_x * ((col - 2) / 2.0)
        y = center_y + spread_y * ((row - 2) / 2.0)
        points.append(LandmarkPoint(x=x, y=y, z=0.0))
    return DetectedHand(label=label, score=score, landmarks=tuple(points))


def make_pinch_state(
    *,
    hand_label: str,
    index_down: bool = False,
    middle_down: bool = False,
    ring_down: bool = False,
    pinky_down: bool = False,
) -> HandPinchState:
    return HandPinchState(
        hand_label=hand_label,
        index=PinchSignal(pressed=index_down, down=index_down),
        middle=PinchSignal(pressed=middle_down, down=middle_down),
        ring=PinchSignal(pressed=ring_down, down=ring_down),
        pinky=PinchSignal(pressed=pinky_down, down=pinky_down),
    )
