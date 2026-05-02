from __future__ import annotations

from dataclasses import dataclass
import math

from ..vision.models import DetectedHand

WRIST_IDX = 0
INDEX_MCP_IDX = 5
MIDDLE_MCP_IDX = 9
PINKY_MCP_IDX = 17

PRESS_SAFE_WIDTH_RATIO_HOLD = 0.34
PRESS_SAFE_WIDTH_RATIO_REENABLE = 0.40
PRESS_SAFE_DEPTH_SKEW_HOLD = 0.95
PRESS_SAFE_DEPTH_SKEW_REENABLE = 0.80
PRESS_SAFE_MIN_WIDTH_FALLBACK = 0.26


@dataclass(frozen=True, slots=True)
class HandViewSafety:
    ordering_ok: bool
    palm_width_ratio: float
    palm_depth_skew: float
    press_safe: bool
    status: str


def _distance_2d_norm(hand: DetectedHand, start_idx: int, end_idx: int) -> float:
    start = hand.landmark(start_idx)
    end = hand.landmark(end_idx)
    return math.hypot(start.x - end.x, start.y - end.y)


def is_palm_facing_thumb_pinky(hand: DetectedHand, *, mirrored_input: bool) -> bool:
    """Detect palm-facing using thumb/pinky x ordering.

    The rule depends on whether the camera frame is mirrored before processing.
    With mirrored input, the x-axis behaves like a selfie preview.
    """

    thumb_x = hand.landmark(4).x
    pinky_x = hand.landmark(20).x
    label = hand.label.lower()

    if mirrored_input:
        if label == "right":
            return thumb_x < pinky_x
        return thumb_x > pinky_x

    if label == "right":
        return thumb_x > pinky_x
    return thumb_x < pinky_x


def analyze_hand_view_safety(
    hand: DetectedHand,
    *,
    mirrored_input: bool,
    previously_safe: bool = False,
) -> HandViewSafety:
    ordering_ok = is_palm_facing_thumb_pinky(hand, mirrored_input=mirrored_input)

    palm_width = _distance_2d_norm(hand, INDEX_MCP_IDX, PINKY_MCP_IDX)
    palm_length = max(_distance_2d_norm(hand, WRIST_IDX, MIDDLE_MCP_IDX), 1e-6)
    palm_width_ratio = palm_width / palm_length

    index_mcp = hand.landmark(INDEX_MCP_IDX)
    pinky_mcp = hand.landmark(PINKY_MCP_IDX)
    palm_depth_skew = abs(index_mcp.z - pinky_mcp.z) / palm_length

    width_threshold = PRESS_SAFE_WIDTH_RATIO_HOLD if previously_safe else PRESS_SAFE_WIDTH_RATIO_REENABLE
    depth_threshold = PRESS_SAFE_DEPTH_SKEW_HOLD if previously_safe else PRESS_SAFE_DEPTH_SKEW_REENABLE

    width_safe = palm_width_ratio >= width_threshold
    width_fallback_safe = palm_width_ratio >= PRESS_SAFE_MIN_WIDTH_FALLBACK
    depth_safe = palm_depth_skew <= depth_threshold

    # Palm width is the reliable first signal in this app. Depth only helps when the
    # width ratio is borderline, because MediaPipe z can vary more across devices.
    press_safe = ordering_ok and (width_safe or (width_fallback_safe and depth_safe))

    status = (
        f"presssafe={'yes' if press_safe else 'no'} "
        f"palm={'yes' if ordering_ok else 'no'} "
        f"ratio={palm_width_ratio:.2f} "
        f"depth={palm_depth_skew:.2f}"
    )
    return HandViewSafety(
        ordering_ok=ordering_ok,
        palm_width_ratio=palm_width_ratio,
        palm_depth_skew=palm_depth_skew,
        press_safe=press_safe,
        status=status,
    )
