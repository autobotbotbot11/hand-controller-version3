from __future__ import annotations

from ..config.settings import AppConfig
from ..gestures import is_palm_facing_thumb_pinky
from ..vision.camera import Camera
from ..vision.hand_selector import HandSelector
from ..vision.hand_tracker import HandTracker
from ..vision.models import VisionResult


def _draw_hands(frame_bgr, vision: VisionResult, tracker: HandTracker, *, selector: HandSelector, mirrored_input: bool) -> None:
    import cv2

    height, width = frame_bgr.shape[:2]
    selected = selector.select(vision.hands, width, height)

    for hand in vision.hands:
        is_primary = selected.primary is hand
        palm_facing = is_palm_facing_thumb_pinky(hand, mirrored_input=mirrored_input)
        line_color = (0, 180, 255) if is_primary else (0, 220, 120)

        for start_idx, end_idx in tracker.connections:
            start = hand.landmark(start_idx)
            end = hand.landmark(end_idx)
            x1 = int(start.x * width)
            y1 = int(start.y * height)
            x2 = int(end.x * width)
            y2 = int(end.y * height)
            cv2.line(frame_bgr, (x1, y1), (x2, y2), line_color, 2)

        for point in hand.landmarks:
            px = int(point.x * width)
            py = int(point.y * height)
            cv2.circle(frame_bgr, (px, py), 4, (255, 255, 255), -1)

        wrist = hand.landmark(0)
        wx = int(wrist.x * width)
        wy = int(wrist.y * height)
        cv2.putText(
            frame_bgr,
            f"{hand.label} {hand.score:.2f} palm={'yes' if palm_facing else 'no'}{' active' if is_primary else ''}",
            (wx + 10, wy - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (50, 255, 255),
            2,
            cv2.LINE_AA,
        )

    status_parts = [
        f"hands={len(vision.hands)}",
        f"active={selected.primary.label if selected.primary else '-'}",
    ]
    if selected.primary is not None:
        status_parts.append(
            f"palm={'yes' if is_palm_facing_thumb_pinky(selected.primary, mirrored_input=mirrored_input) else 'no'}"
        )
    status_parts.append("press q to quit")
    status_line = "  ".join(status_parts)
    cv2.putText(
        frame_bgr,
        status_line,
        (16, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def run_vision_smoke(config: AppConfig) -> None:
    import cv2

    with Camera(
        index=config.camera.index,
        width=config.camera.width,
        height=config.camera.height,
    ) as camera, HandTracker(
        max_num_hands=config.tracker.max_num_hands,
        min_detection_confidence=config.tracker.min_detection_confidence,
        min_tracking_confidence=config.tracker.min_tracking_confidence,
    ) as tracker:
        selector = HandSelector(config.selector)

        if not camera.is_opened():
            raise RuntimeError("Unable to open the configured camera.")

        window_name = "Hand Controller Rewrite - Phase 3 Vision Smoke"

        while True:
            ok, frame_bgr = camera.read()
            if not ok:
                continue

            if config.tracker.mirror_input:
                frame_bgr = cv2.flip(frame_bgr, 1)

            vision = tracker.track_bgr_frame(frame_bgr)
            debug_frame = frame_bgr.copy()
            _draw_hands(
                debug_frame,
                vision,
                tracker,
                selector=selector,
                mirrored_input=config.tracker.mirror_input,
            )

            cv2.imshow(window_name, debug_frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

        cv2.destroyAllWindows()
