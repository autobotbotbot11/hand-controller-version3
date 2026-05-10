from __future__ import annotations

import time
import threading
import traceback
from typing import TYPE_CHECKING

import cv2

from ..config.settings import AppConfig
from ..controllers.keyboard_controller import KeyboardPointer, KeyboardUpdate
from ..gestures import MouseClickGestureState
from ..ml import MLPrediction, MLPredictor
from ..runtime.control_engine import LiveControlEngine
from ..runtime.diagnostics import diagnostics_enabled, diagnostics_log_path, log_diagnostic
from ..runtime.state import RuntimeState
from ..ui.payloads import (
    OverlayKeyRect,
    OverlayOwnershipGuide,
    OverlayPayload,
    OverlayPointer,
    OverlaySkeletonLine,
)
from ..vision.camera import Camera
from ..vision.hand_tracker import HandTracker
from ..vision.models import DetectedHand, SelectedHands, VisionResult

if TYPE_CHECKING:
    from ..ui.main_window import MainWindow
    from ..ui.signals import OverlaySignalBus


_UI_LIVE_WARMUP_LOCK = threading.Lock()
_UI_LIVE_WARMUP_STARTED = False
_THUMB_TIP_IDX = 4
_INDEX_TIP_IDX = 8


def _screen_xy(x_norm: float, y_norm: float, screen_width: int, screen_height: int) -> tuple[int, int]:
    return int(x_norm * screen_width), int(y_norm * screen_height)


def _build_skeleton_lines(
    vision: VisionResult,
    tracker: HandTracker,
    screen_width: int,
    screen_height: int,
    trusted_hands: tuple[DetectedHand, ...],
) -> tuple[OverlaySkeletonLine, ...]:
    trusted_ids = {id(hand) for hand in trusted_hands}
    lines: list[OverlaySkeletonLine] = []
    for hand in vision.hands:
        trusted = id(hand) in trusted_ids
        for start_idx, end_idx in tracker.connections:
            start = hand.landmark(start_idx)
            end = hand.landmark(end_idx)
            x1, y1 = _screen_xy(start.x, start.y, screen_width, screen_height)
            x2, y2 = _screen_xy(end.x, end.y, screen_width, screen_height)
            lines.append(OverlaySkeletonLine(x1=x1, y1=y1, x2=x2, y2=y2, trusted=trusted))
    return tuple(lines)


def _build_keyboard_keys(keyboard_update: KeyboardUpdate) -> tuple[OverlayKeyRect, ...]:
    return tuple(
        OverlayKeyRect(
            label=key.label,
            x1=key.x1,
            y1=key.y1,
            x2=key.x2,
            y2=key.y2,
        )
        for key in keyboard_update.layout
    )


def _pointer_over_key(pointer: KeyboardPointer, keyboard_update: KeyboardUpdate) -> bool:
    return any(key.x1 <= pointer.x <= key.x2 and key.y1 <= pointer.y <= key.y2 for key in keyboard_update.layout)


def _build_pointer_payload(keyboard_update: KeyboardUpdate) -> tuple[OverlayPointer, ...]:
    pointers: list[OverlayPointer] = []
    for pointer in keyboard_update.pointers:
        if not _pointer_over_key(pointer, keyboard_update):
            continue
        pointers.append(
            OverlayPointer(
                x=pointer.x,
                y=pointer.y,
                hand_label=_overlay_hand_label(pointer.hand_label),
                thumb_x=pointer.thumb_x,
                thumb_y=pointer.thumb_y,
                index_x=pointer.index_x,
                index_y=pointer.index_y,
            )
        )
    return tuple(pointers)


def _overlay_hand_label(label: str) -> str:
    return "L" if label == "Left" else "R" if label == "Right" else label


def _build_mouse_pointer_payload(
    selected: SelectedHands,
    screen_width: int,
    screen_height: int,
) -> tuple[OverlayPointer, ...]:
    hand = selected.primary
    if hand is None:
        return ()

    thumb = hand.landmark(_THUMB_TIP_IDX)
    index = hand.landmark(_INDEX_TIP_IDX)
    thumb_x, thumb_y = _screen_xy(thumb.x, thumb.y, screen_width, screen_height)
    index_x, index_y = _screen_xy(index.x, index.y, screen_width, screen_height)
    return (
        OverlayPointer(
            x=int(round((thumb_x + index_x) / 2.0)),
            y=int(round((thumb_y + index_y) / 2.0)),
            hand_label="",
            thumb_x=thumb_x,
            thumb_y=thumb_y,
            index_x=index_x,
            index_y=index_y,
            show_dot=False,
        ),
    )


def _build_ownership_guide_payload(
    guide,
    screen_width: int,
    screen_height: int,
) -> OverlayOwnershipGuide:
    x1, y1, x2, y2 = guide.zone
    return OverlayOwnershipGuide(
        visible=guide.visible,
        text=guide.text,
        progress=guide.progress,
        x1=int(round(x1 * screen_width)),
        y1=int(round(y1 * screen_height)),
        x2=int(round(x2 * screen_width)),
        y2=int(round(y2 * screen_height)),
        locked_count=guide.locked_count,
        max_count=guide.max_count,
    )


def _build_selfie_frame(frame_bgr, *, width: int, height: int) -> object | None:
    try:
        return cv2.resize(frame_bgr, (width, height))
    except Exception:
        return None


def _build_debug_tags(
    *,
    selected: SelectedHands,
    runtime_state: RuntimeState,
    movement_enabled: bool,
    click_state: MouseClickGestureState,
    drag_active: bool,
    ml_prediction: MLPrediction,
    ml_status: str,
    keyboard_toggle_status: str,
    ml_available: bool,
    ml_reason: str | None,
    pre_hold_right_suppressed: bool,
    press_gestures_safe: bool,
    press_safety_status: str,
    ownership_status: str,
) -> tuple[str, ...]:
    active_label = selected.primary.label if selected.primary is not None else "-"
    ml_line = "  ".join(
        [
            f"active={active_label}",
            f"ml={'on' if ml_available else 'off'}",
            f"raw={ml_prediction.raw_label}",
            f"stable={runtime_state.latest_ml_label}",
            f"p1={ml_prediction.p1:.2f}" if ml_prediction.p1 is not None else "p1=-",
            f"margin={ml_prediction.margin:.2f}" if ml_prediction.margin is not None else "margin=-",
            f"ml_status={ml_status}",
        ]
    )
    mouse_line = "  ".join(
        [
            f"hold={'yes' if runtime_state.hold_active else 'no'}",
            f"presssafe={'yes' if press_gestures_safe else 'no'}",
            f"prehold_r={'on' if pre_hold_right_suppressed else 'off'}",
            f"movement={'on' if movement_enabled else 'off'}",
            f"drag={'yes' if drag_active else 'no'}",
            f"click_idx={'down' if click_state.left_pressed else 'up'}",
            f"click_mid={'down' if click_state.right_pressed else 'up'}",
            keyboard_toggle_status,
            ownership_status,
        ]
    )
    tags = [ml_line, mouse_line, press_safety_status]
    if not ml_available and ml_reason:
        tags.append(f"ml_reason={ml_reason}")
    return tuple(tags)


def _build_overlay_payload(
    *,
    runtime_state: RuntimeState,
    keyboard_update: KeyboardUpdate,
    mouse_pointers: tuple[OverlayPointer, ...],
    skeleton_lines: tuple[OverlaySkeletonLine, ...],
    selfie_frame,
    mouse_status: str,
    movement_enabled: bool,
    gesture_command_text: str,
    helper_hint_text: str,
    ownership_guide: OverlayOwnershipGuide,
    debug_tags: tuple[str, ...],
) -> OverlayPayload:
    keyboard_visible = runtime_state.control_enabled and runtime_state.keyboard_visible
    mouse_visible = runtime_state.control_enabled
    if keyboard_visible:
        finger_points = _build_pointer_payload(keyboard_update)
    elif mouse_visible:
        finger_points = mouse_pointers
    else:
        finger_points = ()

    return OverlayPayload(
        mode="keyboard" if keyboard_visible else "mouse",
        control_enabled=runtime_state.control_enabled,
        keyboard_visible=keyboard_visible,
        keyboard_dimmed=False,
        keyboard_keys=_build_keyboard_keys(keyboard_update) if keyboard_visible else (),
        highlight_labels=keyboard_update.highlight_labels if keyboard_visible else frozenset(),
        finger_points=finger_points,
        skeleton_lines=skeleton_lines,
        mouse_status=mouse_status,
        keyboard_status=keyboard_update.status if keyboard_visible else "",
        profile_label="live-overlay",
        footer_hint="Live overlay path | close the control panel window to stop",
        selfie_frame=selfie_frame,
        gesture_command_text=gesture_command_text,
        helper_hint_text=helper_hint_text,
        ownership_guide=ownership_guide,
        debug_tags=debug_tags,
    )


def run_ui_live_worker(
    overlay_bus,
    stop_event,
    config: AppConfig,
    screen_width: int,
    screen_height: int,
) -> None:
    try:
        log_diagnostic("worker=start")
        engine = LiveControlEngine(config, screen_width=screen_width, screen_height=screen_height)

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

            while not stop_event.is_set():
                ok, frame_bgr = camera.read()
                if not ok:
                    continue

                if config.tracker.mirror_input:
                    frame_bgr = cv2.flip(frame_bgr, 1)

                vision = tracker.track_bgr_frame(frame_bgr)
                now = time.time()
                frame_result = engine.process_frame(
                    vision,
                    layout_width=screen_width,
                    layout_height=screen_height,
                    now=now,
                )

                payload = _build_overlay_payload(
                    runtime_state=frame_result.runtime_state,
                    keyboard_update=frame_result.keyboard_update,
                    mouse_pointers=_build_mouse_pointer_payload(
                        frame_result.selected,
                        screen_width,
                        screen_height,
                    ),
                    skeleton_lines=_build_skeleton_lines(
                        frame_result.vision,
                        tracker,
                        screen_width,
                        screen_height,
                        frame_result.trusted_hands,
                    ),
                    selfie_frame=_build_selfie_frame(
                        frame_bgr,
                        width=config.keyboard.selfie_width_px,
                        height=config.keyboard.selfie_height_px,
                    ),
                    mouse_status=frame_result.movement_status,
                    movement_enabled=frame_result.movement_enabled,
                    gesture_command_text=frame_result.gesture_command_text,
                    helper_hint_text=frame_result.helper_hint_text,
                    ownership_guide=_build_ownership_guide_payload(
                        frame_result.ownership_guide,
                        screen_width,
                        screen_height,
                    ),
                    debug_tags=_build_debug_tags(
                        selected=frame_result.selected,
                        runtime_state=frame_result.runtime_state,
                        movement_enabled=frame_result.movement_enabled,
                        click_state=frame_result.click_state,
                        drag_active=frame_result.drag_active,
                        ml_prediction=frame_result.ml_prediction,
                        ml_status=frame_result.ml_status,
                        keyboard_toggle_status=frame_result.keyboard_toggle_status,
                        ml_available=frame_result.ml_available,
                        ml_reason=frame_result.ml_reason,
                        pre_hold_right_suppressed=frame_result.pre_hold_right_suppressed,
                        press_gestures_safe=frame_result.press_gestures_safe,
                        press_safety_status=frame_result.press_safety_status,
                        ownership_status=frame_result.ownership_status,
                    ),
                )
                try:
                    overlay_bus.update_overlay.emit(payload)
                except Exception:
                    return
    except Exception as exc:
        error_payload = OverlayPayload(
            mode="error",
            control_enabled=False,
            keyboard_visible=False,
            mouse_status="worker failed",
            keyboard_status="",
            profile_label="live-overlay",
            footer_hint="See terminal traceback. Close the control panel window to stop.",
            debug_tags=(
                f"worker_error={exc}",
                traceback.format_exc(limit=3).replace("\n", " | "),
            ),
        )
        try:
            log_diagnostic(f"worker=error detail={exc}")
            overlay_bus.update_overlay.emit(error_payload)
        except Exception:
            pass
        raise


def _prewarm_ui_live_components(config: AppConfig) -> None:
    try:
        MLPredictor.try_create(config.ml)
    except Exception:
        pass

    try:
        tracker = HandTracker(
            max_num_hands=config.tracker.max_num_hands,
            min_detection_confidence=config.tracker.min_detection_confidence,
            min_tracking_confidence=config.tracker.min_tracking_confidence,
        )
    except Exception:
        return

    try:
        tracker.close()
    except Exception:
        pass


def _start_ui_live_warmup(config: AppConfig) -> None:
    global _UI_LIVE_WARMUP_STARTED
    with _UI_LIVE_WARMUP_LOCK:
        if _UI_LIVE_WARMUP_STARTED:
            return
        _UI_LIVE_WARMUP_STARTED = True

    thread = threading.Thread(
        target=_prewarm_ui_live_components,
        args=(config,),
        name="ui-live-prewarm",
        daemon=True,
    )
    thread.start()


def run_ui_live_control(config: AppConfig) -> None:
    log_diagnostic(
        "ui_live=start "
        f"tuning={config.tuning_path or 'defaults'} "
        f"camera={config.camera.width}x{config.camera.height}@{config.camera.index} "
        f"theme={config.general.theme} "
        f"log={diagnostics_log_path()}"
    )
    try:
        import mediapipe  # noqa: F401
    except Exception as exc:
        log_diagnostic(f"ui_live=mediapipe_import_fail detail={exc}")
        raise RuntimeError(
            "MediaPipe failed to initialize before the Qt UI startup. On this Windows setup, mediapipe must load before PyQt5."
        ) from exc

    try:
        from PyQt5.QtWidgets import QApplication
        from ..ui.main_window import MainWindow
    except ModuleNotFoundError as exc:
        log_diagnostic(f"ui_live=pyqt_import_fail detail={exc}")
        raise RuntimeError(
            "PyQt5 is required for --ui-live. Install requirements.txt first."
        ) from exc

    app = QApplication.instance() or QApplication([])
    window = MainWindow(
        config=config,
        worker_fn=run_ui_live_worker,
        ui_mode_label="Live Control",
        start_button_label="LAUNCH",
        stop_button_label="STOP",
        info_text=(
            ""
        ),
    )
    _start_ui_live_warmup(config)
    window.show()
    if diagnostics_enabled():
        log_diagnostic("ui_live=window_shown")
    app.exec_()
    log_diagnostic("ui_live=exit")
