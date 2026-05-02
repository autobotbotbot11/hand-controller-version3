from __future__ import annotations

import time

from ..config.settings import AppConfig
from ..controllers import get_screen_size
from ..controllers.keyboard_controller import KeyboardUpdate
from ..gestures import MouseClickGestureState, is_palm_facing_thumb_pinky
from ..ml import MLPrediction
from ..runtime.control_engine import LiveControlEngine
from ..runtime.state import Mode, RuntimeState
from ..vision.camera import Camera
from ..vision.hand_tracker import HandTracker
from ..vision.models import DetectedHand, SelectedHands, VisionResult


VISUAL_CURSOR_IDX = 8


def _visual_cursor_px(hand: DetectedHand, frame_width: int, frame_height: int) -> tuple[int, int]:
    point = hand.landmark(VISUAL_CURSOR_IDX)
    return int(point.x * frame_width), int(point.y * frame_height)


def _anchor_px(hand: DetectedHand, frame_width: int, frame_height: int) -> tuple[int, int]:
    point = hand.landmark(5)
    return int(point.x * frame_width), int(point.y * frame_height)


def _draw_keyboard_overlay(frame_bgr, *, keyboard_update: KeyboardUpdate, control_enabled: bool) -> None:
    import cv2

    for key in keyboard_update.layout:
        hovered = key.label in keyboard_update.highlight_labels
        fill = (40, 60, 90) if not hovered else (0, 155, 255)
        if not control_enabled:
            fill = (35, 35, 35)
        border = (255, 255, 255) if hovered else (120, 120, 120)
        cv2.rectangle(frame_bgr, (key.x1, key.y1), (key.x2, key.y2), fill, -1)
        cv2.rectangle(frame_bgr, (key.x1, key.y1), (key.x2, key.y2), border, 2)

        label = "SPC" if key.label == "SPACE" else key.label
        text_scale = 0.7 if len(label) == 1 else 0.55
        text_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, text_scale, 2)
        text_x = key.x1 + max(8, ((key.x2 - key.x1) - text_size[0]) // 2)
        text_y = key.y1 + max(text_size[1] + 6, ((key.y2 - key.y1) + text_size[1]) // 2)
        cv2.putText(
            frame_bgr,
            label,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            text_scale,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

    for pointer in keyboard_update.pointers:
        if (
            pointer.thumb_x is not None
            and pointer.thumb_y is not None
            and pointer.index_x is not None
            and pointer.index_y is not None
        ):
            cv2.line(
                frame_bgr,
                (pointer.thumb_x, pointer.thumb_y),
                (pointer.index_x, pointer.index_y),
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
        cv2.circle(frame_bgr, (pointer.x, pointer.y), 12, (80, 255, 80), 2)
        cv2.putText(
            frame_bgr,
            pointer.hand_label,
            (pointer.x + 12, pointer.y - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (80, 255, 80),
            2,
            cv2.LINE_AA,
        )


def _wrap_text_lines(
    *,
    text: str,
    max_width: int,
    font,
    scale: float,
    thickness: int,
) -> list[str]:
    import cv2

    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        width, _ = cv2.getTextSize(candidate, font, scale, thickness)[0]
        if width <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _draw_wrapped_text(
    frame_bgr,
    *,
    text: str,
    x: int,
    y: int,
    max_width: int,
    scale: float,
    color: tuple[int, int, int],
    thickness: int,
    line_gap: int = 8,
) -> int:
    import cv2

    font = cv2.FONT_HERSHEY_SIMPLEX
    text_height = cv2.getTextSize("Ag", font, scale, thickness)[0][1]
    cursor_y = y
    for line in _wrap_text_lines(
        text=text,
        max_width=max_width,
        font=font,
        scale=scale,
        thickness=thickness,
    ):
        cv2.putText(
            frame_bgr,
            line,
            (x, cursor_y),
            font,
            scale,
            color,
            thickness,
            cv2.LINE_AA,
        )
        cursor_y += text_height + line_gap
    return cursor_y


def _draw_control_smoke(
    frame_bgr,
    *,
    vision: VisionResult,
    tracker: HandTracker,
    selected: SelectedHands,
    mirrored_input: bool,
    movement_status: str,
    movement_enabled: bool,
    click_state: MouseClickGestureState,
    click_freeze: bool,
    drag_active: bool,
    runtime_state: RuntimeState,
    ml_prediction: MLPrediction,
    ml_status: str,
    ml_available: bool,
    ml_reason: str | None,
    mode_toggle_status: str,
    keyboard_update: KeyboardUpdate,
    pre_hold_right_suppressed: bool,
    press_gestures_safe: bool,
    press_safety_status: str,
) -> None:
    import cv2

    height, width = frame_bgr.shape[:2]

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
            cv2.circle(frame_bgr, (px, py), 3, (255, 255, 255), -1)

        wrist = hand.landmark(0)
        wx = int(wrist.x * width)
        wy = int(wrist.y * height)
        cv2.putText(
            frame_bgr,
            f"{hand.label} palm={'yes' if palm_facing else 'no'}{' active' if is_primary else ''}",
            (wx + 10, wy - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (50, 255, 255),
            2,
            cv2.LINE_AA,
        )

    if runtime_state.mode == Mode.MOUSE and selected.primary is not None:
        anchor_x, anchor_y = _anchor_px(selected.primary, width, height)
        cursor_x, cursor_y = _visual_cursor_px(selected.primary, width, height)
        cv2.circle(frame_bgr, (anchor_x, anchor_y), 10, (0, 140, 255), 2)
        cv2.circle(frame_bgr, (cursor_x, cursor_y), 10, (255, 255, 0), 2)
        cv2.putText(
            frame_bgr,
            "anchor",
            (anchor_x + 12, anchor_y + 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 140, 255),
            2,
            cv2.LINE_AA,
        )

    if runtime_state.control_enabled and runtime_state.mode == Mode.KEYBOARD:
        _draw_keyboard_overlay(
            frame_bgr,
            keyboard_update=keyboard_update,
            control_enabled=runtime_state.control_enabled,
        )

    pinch_line = "pinch idx={idx} {idx_dist:.1f}px  mid={mid} {mid_dist:.1f}px".format(
        idx="down" if click_state.left_pressed else "up",
        idx_dist=click_state.left_distance_px or 0.0,
        mid="down" if click_state.right_pressed else "up",
        mid_dist=click_state.right_distance_px or 0.0,
    )
    cv2.putText(
        frame_bgr,
        pinch_line,
        (16, height - 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    common_parts = [
        f"hands={len(vision.hands)}",
        f"active={selected.primary.label if selected.primary else '-'}",
        f"mode={runtime_state.mode.value}",
        f"control={'on' if runtime_state.control_enabled else 'off'}",
    ]
    if runtime_state.mode == Mode.MOUSE:
        status_parts = [
            *common_parts,
            f"hold={'yes' if runtime_state.hold_active else 'no'}",
            f"clicks={'on' if runtime_state.control_enabled and not runtime_state.hold_active else 'off'}",
            f"presssafe={'yes' if press_gestures_safe else 'no'}",
            f"prehold_r={'on' if pre_hold_right_suppressed else 'off'}",
            f"movement={'on' if movement_enabled else 'off'}",
            f"freeze={'yes' if click_freeze else 'no'}",
            f"drag={'yes' if drag_active else 'no'}",
            movement_status,
            mode_toggle_status,
            "press q to quit",
        ]
    else:
        status_parts = [
            *common_parts,
            f"shift={'on' if keyboard_update.shift_armed else 'off'}",
            keyboard_update.status,
            mode_toggle_status,
            "press q to quit",
        ]

    next_y = _draw_wrapped_text(
        frame_bgr,
        text="  ".join(status_parts),
        x=16,
        y=32,
        max_width=max(120, width - 32),
        scale=0.65,
        color=(255, 255, 255),
        thickness=2,
    )
    ml_line = "  ".join(
        [
            f"ml={'on' if ml_available else 'off'}",
            f"raw={ml_prediction.raw_label}",
            f"stable={runtime_state.latest_ml_label}",
            f"p1={ml_prediction.p1:.2f}" if ml_prediction.p1 is not None else "p1=-",
            f"margin={ml_prediction.margin:.2f}" if ml_prediction.margin is not None else "margin=-",
            f"ml_status={ml_status}",
        ]
    )
    next_y = _draw_wrapped_text(
        frame_bgr,
        text=ml_line,
        x=16,
        y=next_y,
        max_width=max(120, width - 32),
        scale=0.60,
        color=(255, 255, 255),
        thickness=2,
    )
    next_y = _draw_wrapped_text(
        frame_bgr,
        text=press_safety_status,
        x=16,
        y=next_y,
        max_width=max(120, width - 32),
        scale=0.55,
        color=(160, 220, 255) if press_gestures_safe else (0, 180, 255),
        thickness=2,
    )
    if not ml_available and ml_reason:
        _draw_wrapped_text(
            frame_bgr,
            text=f"ml_reason={ml_reason}",
            x=16,
            y=next_y,
            max_width=max(120, width - 32),
            scale=0.55,
            color=(0, 200, 255),
            thickness=2,
        )


def run_mouse_smoke(config: AppConfig) -> None:
    import cv2

    screen_w, screen_h = get_screen_size()
    engine = LiveControlEngine(config, screen_width=screen_w, screen_height=screen_h)

    with Camera(
        index=config.camera.index,
        width=config.camera.width,
        height=config.camera.height,
    ) as camera, HandTracker(
        max_num_hands=config.tracker.max_num_hands,
        min_detection_confidence=config.tracker.min_detection_confidence,
        min_tracking_confidence=config.tracker.min_tracking_confidence,
    ) as tracker:
        if not camera.is_opened():
            raise RuntimeError("Unable to open the configured camera.")

        window_name = "Hand Controller Rewrite - Phase 8 Control Smoke"

        while True:
            ok, frame_bgr = camera.read()
            if not ok:
                continue

            if config.tracker.mirror_input:
                frame_bgr = cv2.flip(frame_bgr, 1)

            vision = tracker.track_bgr_frame(frame_bgr)
            now = time.time()
            frame_result = engine.process_frame(
                vision,
                layout_width=vision.frame_width,
                layout_height=vision.frame_height,
                now=now,
            )

            debug_frame = frame_bgr.copy()
            _draw_control_smoke(
                debug_frame,
                vision=frame_result.vision,
                tracker=tracker,
                selected=frame_result.selected,
                mirrored_input=config.tracker.mirror_input,
                movement_status=frame_result.movement_status,
                movement_enabled=frame_result.movement_enabled,
                click_state=frame_result.click_state,
                click_freeze=frame_result.click_freeze,
                drag_active=frame_result.drag_active,
                runtime_state=frame_result.runtime_state,
                ml_prediction=frame_result.ml_prediction,
                ml_status=frame_result.ml_status,
                ml_available=frame_result.ml_available,
                ml_reason=frame_result.ml_reason,
                mode_toggle_status=frame_result.mode_toggle_status,
                keyboard_update=frame_result.keyboard_update,
                pre_hold_right_suppressed=frame_result.pre_hold_right_suppressed,
                press_gestures_safe=frame_result.press_gestures_safe,
                press_safety_status=frame_result.press_safety_status,
            )

            cv2.imshow(window_name, debug_frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

        cv2.destroyAllWindows()
