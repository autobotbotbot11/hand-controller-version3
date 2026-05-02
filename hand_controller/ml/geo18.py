from __future__ import annotations

from typing import Iterable
import math

from ..vision.models import DetectedHand


EPS = 1e-9


def _vector(point: Iterable[float]) -> tuple[float, float, float]:
    x, y, z = point
    return float(x), float(y), float(z)


def _sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def _norm(vec: tuple[float, float, float]) -> float:
    return math.sqrt((vec[0] * vec[0]) + (vec[1] * vec[1]) + (vec[2] * vec[2]))


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return _norm(_sub(a, b))


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return (a[0] * b[0]) + (a[1] * b[1]) + (a[2] * b[2])


def _calculate_angle(a: tuple[float, float, float], b: tuple[float, float, float], c: tuple[float, float, float]) -> float:
    ba = _sub(a, b)
    bc = _sub(c, b)
    denom = _norm(ba) * _norm(bc)
    if denom < EPS:
        return 0.0
    cosang = _dot(ba, bc) / denom
    cosang = max(-1.0, min(1.0, cosang))
    return math.degrees(math.acos(cosang))


def extract_geo18(hand: DetectedHand) -> list[float]:
    raw = [_vector((point.x, point.y, point.z)) for point in hand.landmarks]
    wrist = raw[0]
    normalized = [_sub(point, wrist) for point in raw]

    palm_width = _distance(normalized[5], normalized[17])
    if palm_width < 1e-6:
        palm_width = 1.0

    extensions = [_distance(normalized[0], normalized[i]) / palm_width for i in (4, 8, 12, 16, 20)]
    thumb_tip = normalized[4]
    pinches = [_distance(thumb_tip, normalized[i]) / palm_width for i in (8, 12, 16, 20)]
    spreads = [
        _distance(normalized[i], normalized[j]) / palm_width
        for i, j in ((8, 12), (12, 16), (16, 20))
    ]
    thumb_to_pinky_base = _distance(normalized[4], normalized[17]) / palm_width
    angles = [
        _calculate_angle(normalized[1], normalized[2], normalized[3]) / 180.0,
        _calculate_angle(normalized[5], normalized[6], normalized[7]) / 180.0,
        _calculate_angle(normalized[9], normalized[10], normalized[11]) / 180.0,
        _calculate_angle(normalized[13], normalized[14], normalized[15]) / 180.0,
        _calculate_angle(normalized[17], normalized[18], normalized[19]) / 180.0,
    ]
    return [float(value) for value in (extensions + pinches + spreads + [thumb_to_pinky_base] + angles)]
